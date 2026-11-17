#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_stability.py — 连续执行 N 次（默认 3 次）pytest，判定脚本稳定性。

判定口径：
  - STABLE     ：N 次全部 passed
  - FLAKY      ：有时通过有时失败（不稳定，必须修）
  - BROKEN     ：N 次全部失败（必现失败）
  - SKIPPED    ：N 次全部跳过

失败会按报错文本自动分类（元素未找到/超时/连接/鉴权/断言/数据依赖/依赖缺失/环境配置等），
并给出修复方向，详见 references/failure_playbook.md。

用法：
  python verify_stability.py --target tests/test_login.py --count 3 \
      [--project D:/proj/autotest] [--report-dir ./.stability] [--pytest-args "-p no:randomly"] \
      [--interp "py -3.11"]

退出码：0 = 全部稳定；1 = 存在 FLAKY/BROKEN；2 = 执行异常。
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

# 顺序敏感：越具体的规则放前面
RULES = [
    ("依赖缺失", ["ModuleNotFoundError", "ImportError", "No module named", "cannot import name"],
     "安装缺失依赖（pip install），或修正 import 路径；确认在工程虚拟环境中执行。"),
    ("fixture错误", ["fixture '", "fixture not found", "FixtureLookupError"],
     "fixture 名写错或未在 conftest.py 中定义；核对 style_guide.md 里的 fixture 清单。"),
    ("元素未找到", ["waiting for selector", "wait_for_selector", "no such element",
                   "NoSuchElementException", "ElementNotFound", "Timeout .*exceeded while waiting",
                   "strict mode violation", "not visible", "元素未找到"],
     "定位方式不稳定：换用更稳的选择器（data-testid/文本/role），或增加显式等待而不是固定 sleep。"),
    ("超时", ["TimeoutError", "Timeout", "timed out", "timeout"],
     "适当调大超时；UI 用 wait_for_selector 显式等待，API 调大 timeout；排查被测服务是否慢。"),
    ("连接失败", ["ConnectionError", "Connection refused", "Max retries exceeded",
                  "NewConnectionError", "SSLError", "Errno 10061", "Errno 11001", "Name or service not known"],
     "被测服务未启动/地址写错；把 base_url、host 走环境变量注入，并在用例前做健康检查。"),
    ("鉴权失败", ["401", "403", "Unauthorized", "Forbidden", "token", "登录失效", "未登录"],
     "补充/刷新登录态：用 session 级 fixture 统一获取 token，避免用例间互相失效。"),
    ("数据库错误", ["pymysql", "OperationalError", "ProgrammingError", "InterfaceError",
                    "Unknown database", "Access denied for user", "You have an error in your SQL syntax"],
     "检查 DB 连接串与 SQL 语法；DB 用例建议自带数据准备与清理，避免依赖历史数据。"),
    ("数据依赖", ["已存在", "duplicate", "Duplicate", "not found", "不存在", "无数据", "数据为空"],
     "用例缺少前置数据或产生脏数据：在 fixture 中创建专属测试数据并在 teardown 清理，保证可重复执行。"),
    ("环境配置", ["KeyError", "NoneType", "环境变量", "AttributeError: 'NoneType'", "env"],
     "配置项缺失：检查 .env/配置文件是否加载，给 getenv 提供合理默认值并加断言提示。"),
    ("断言失败", ["assert", "AssertionError", "!=", "Expected", "expected"],
     "确认预期结果是否写错，或断言对象取错（字段路径/编码/类型）；把实际值打印进断言消息。"),
]


def extract_error_text(message: str) -> str:
    """从 pytest 的失败文本里取出真正的报错，去掉源码回显。

    pytest 的长回显会把出错行附近的源码也打出来（例如 `timeout=15,`），
    直接拿全文做关键词匹配会把「断言失败」误判成「超时」。
    """
    lines = [ln[2:] for ln in (message or "").splitlines() if ln.startswith("E ")]
    if lines:
        return "\n".join(lines)
    head = (message or "").strip().splitlines()
    return "\n".join(head[:5])


def classify(message: str) -> Tuple[str, str]:
    text = extract_error_text(message)[:4000]
    for name, keys, advice in RULES:
        for k in keys:
            try:
                if re.search(k, text, re.I):
                    return name, advice
            except re.error:
                if k.lower() in text.lower():
                    return name, advice
    return "未分类", "人工阅读完整 traceback 定位；把报错原文贴出再分析。"


def _pytest_ok(interp: List[str]) -> bool:
    try:
        p = subprocess.run(interp + ["-m", "pytest", "--version"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return p.returncode == 0
    except Exception:
        return False


def resolve_interp(user_interp: Optional[str]) -> List[str]:
    """确定用哪个解释器执行 pytest：装了 pytest 的那个优先。

    优先级：--interp > 环境变量 TESTCASE_PYTHON > sys.executable > python3.7/python3/python/py。
    目标工程多为 Python 3.7，若默认解释器没装 pytest，可提前 export TESTCASE_PYTHON=python3.7。
    """
    candidates: List[List[str]] = []
    if user_interp:
        candidates.append(user_interp.split())
    for env_key in ("TESTCASE_PYTHON", "PYTHON_37", "PYTHON_BIN"):
        v = os.environ.get(env_key)
        if v:
            candidates.append(v.split())
    candidates += [[sys.executable], ["python3.7"], ["python3"], ["python"],
                   ["py", "-3.7"], ["py"]]
    seen = set()
    for c in candidates:
        key = tuple(c)
        if key in seen:
            continue
        seen.add(key)
        if _pytest_ok(c):
            return c
    print("[verify][warn] 未找到安装了 pytest 的解释器，请用 --interp 指定 "
          "（例如 --interp python3.7）。", file=sys.stderr)
    return candidates[0]


def run_once(project: Path, target: str, junit_path: Path, extra_args: List[str], idx: int,
             interp: List[str]) -> dict:
    cmd = interp + ["-m", "pytest", target, "-q", f"--junitxml={junit_path}"] + extra_args
    proc = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return {
        "index": idx,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def parse_junit(path: Path) -> Dict[str, dict]:
    """返回 {nodeid: {status, message, time}}"""
    if not path.exists():
        return {}
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return {}
    result: Dict[str, dict] = {}
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        suites = root.findall("testsuite")
    else:
        suites = [suite]
    for s in suites:
        for tc in s.iter("testcase"):
            cls = tc.get("classname") or ""
            name = tc.get("name") or ""
            nodeid = f"{cls}::{name}" if cls else name
            status = "passed"
            message = ""
            for child in tc:
                if child.tag in ("failure", "error"):
                    status = "failed"
                    message = (child.get("message") or "") + "\n" + (child.text or "")
                elif child.tag == "skipped":
                    status = "skipped"
                    message = child.get("message") or ""
            result[nodeid] = {
                "status": status,
                "message": message.strip()[:3000],
                "time": float(tc.get("time") or 0),
            }
    return result


def main():
    ap = argparse.ArgumentParser(description="连跑 N 次验证脚本稳定性")
    ap.add_argument("--target", required=True, help="测试文件/目录/节点，如 tests/test_login.py")
    ap.add_argument("--project", default=".", help="pytest 执行工作目录（自动化工程根）")
    ap.add_argument("--count", type=int, default=3, help="连续执行次数，默认 3")
    ap.add_argument("--report-dir", default=None, help="报告输出目录，默认 <project>/.stability")
    ap.add_argument("--pytest-args", default="", help="附加 pytest 参数，如 '-p no:cacheprovider -m smoke'")
    ap.add_argument("--interp", default=None,
                    help="执行 pytest 的解释器，如 'py -3.11'；默认自动挑一个装了 pytest 的")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        sys.exit(f"[verify] 工程目录不存在: {project}")
    report_dir = Path(args.report_dir).expanduser().resolve() if args.report_dir else project / ".stability"
    report_dir.mkdir(parents=True, exist_ok=True)

    extra = [a for a in args.pytest_args.split() if a]

    runs: List[dict] = []
    per_run: List[Dict[str, dict]] = []
    tmpdir = Path(tempfile.mkdtemp(prefix="stability_"))
    try:
        interp = resolve_interp(args.interp)
        print(f"[verify] 解释器：{' '.join(interp)}")
        for i in range(1, args.count + 1):
            junit = tmpdir / f"run{i}.xml"
            info = run_once(project, args.target, junit, extra, i, interp)
            parsed = parse_junit(junit)
            per_run.append(parsed)
            runs.append({k: v for k, v in info.items() if k != "stdout_tail"})
            runs[-1]["cases"] = len(parsed)
            runs[-1]["passed"] = sum(1 for v in parsed.values() if v["status"] == "passed")
            runs[-1]["failed"] = sum(1 for v in parsed.values() if v["status"] == "failed")
            runs[-1]["skipped"] = sum(1 for v in parsed.values() if v["status"] == "skipped")
            print(f"[verify] 第 {i}/{args.count} 次："
                  f"通过 {runs[-1]['passed']}，失败 {runs[-1]['failed']}，跳过 {runs[-1]['skipped']}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    all_nodes = sorted({n for r in per_run for n in r})
    summary = []
    for node in all_nodes:
        statuses = [r.get(node, {}).get("status", "missing") for r in per_run]
        ok = sum(1 for s in statuses if s == "passed")
        fail = sum(1 for s in statuses if s == "failed")
        skip = sum(1 for s in statuses if s == "skipped")
        missing = sum(1 for s in statuses if s == "missing")
        if missing == len(statuses):
            verdict = "MISSING"
        elif ok == len(statuses):
            verdict = "STABLE"
        elif fail == len(statuses):
            verdict = "BROKEN"
        elif skip == len(statuses):
            verdict = "SKIPPED"
        elif ok > 0 and fail > 0:
            verdict = "FLAKY"
        else:
            verdict = "UNKNOWN"
        msg = ""
        for r in per_run:
            if r.get(node, {}).get("status") == "failed":
                msg = r[node]["message"]
                break
        cat, advice = classify(msg) if msg else ("", "")
        summary.append({
            "nodeid": node, "verdict": verdict, "statuses": statuses,
            "passed": ok, "failed": fail, "skipped": skip,
            "category": cat, "advice": advice,
            "error": (extract_error_text(msg) or msg)[:1200],
            "first_error": msg[:1200],
        })

    stable = [s for s in summary if s["verdict"] == "STABLE"]
    flaky = [s for s in summary if s["verdict"] == "FLAKY"]
    broken = [s for s in summary if s["verdict"] == "BROKEN"]
    other = [s for s in summary if s["verdict"] not in ("STABLE", "FLAKY", "BROKEN")]

    # JSON
    payload = {
        "target": args.target, "project": str(project), "count": args.count,
        "runs": runs, "cases": summary,
        "counts": {"stable": len(stable), "flaky": len(flaky), "broken": len(broken),
                   "other": len(other), "total": len(summary)},
    }
    (report_dir / "stability_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    L = ["# 稳定性验收报告", "",
         f"- 目标：`{args.target}`",
         f"- 工程：`{project}`",
         f"- 连续执行：{args.count} 次",
         f"- 结论：**{'通过（全部稳定）' if not flaky and not broken else '未通过'}**",
         "",
         "| 分类 | 数量 |", "|------|------|",
         f"| STABLE | {len(stable)} |",
         f"| FLAKY | {len(flaky)} |",
         f"| BROKEN | {len(broken)} |",
         f"| 其他(SKIPPED/MISSING) | {len(other)} |",
         "",
         "## 用例明细", "",
         "| 用例 | 判定 | 各轮结果 | 失败分类 | 建议 |", "|------|------|----------|----------|------|"]
    for s in summary:
        L.append(f"| `{s['nodeid']}` | **{s['verdict']}** | {'/'.join(s['statuses'])} "
                 f"| {s['category'] or '-'} | {s['advice'] or '-'} |")
    L.append("")
    for s in flaky + broken:
        if s.get("error") or s["first_error"]:
            L.append(f"### {s['nodeid']}（{s['verdict']} / {s['category'] or '未分类'}）")
            L.append("")
            L.append("```")
            L.append(s.get("error") or s["first_error"])
            L.append("```")
            L.append("")
    (report_dir / "stability_report.md").write_text("\n".join(L), encoding="utf-8")

    print(f"[verify] 报告：{report_dir / 'stability_report.md'}")
    print(f"[verify] 判定：STABLE {len(stable)} / FLAKY {len(flaky)} / BROKEN {len(broken)} / 其他 {len(other)}")
    if flaky or broken:
        print("[verify] 存在不稳定用例，请按 references/failure_playbook.md 修复后重跑。")
        sys.exit(1)
    print("[verify] 全部用例连续 %d 次通过，稳定性达标。" % args.count)
    sys.exit(0)


if __name__ == "__main__":
    main()
