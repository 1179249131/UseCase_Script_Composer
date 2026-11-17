#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 定位稳定性体检：给脚本/用例里的每个选择器打分，D 级必须改掉才能连跑验收。

评分规则见 references/locator_guide.md §3：
  A 契约属性(testid) +3  B 语义定位 +2  C 表现/文本 +1~0  D 结构/动态 -1~-3

用法：
  python locator_check.py --files testcases/test_login.py [更多文件...]
  python locator_check.py --dir testcases
  python locator_check.py --cases cases.json          # 只查用例表里 UI 步骤写的元素
  python locator_check.py --dir testcases --out locator_report.md
  python locator_check.py --dir testcases --strict    # C 级也判不通过

退出码：0 = 通过（无 D 级）；1 = 存在 D 级（需修复）；2 = 参数错误。
"""
from __future__ import annotations  # Python 3.7+：注解不求值

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# 规则表
# --------------------------------------------------------------------------- #

R_TESTID = re.compile(r"data-testid|data-cy|data-test\b|test_id\s*=")
R_SEMANTIC = re.compile(
    r"get_by_role|get_by_label|get_by_placeholder|get_by_alt_text|get_by_title"
    r"|aria-label|\[name\s*=|\[id\s*=|\[placeholder\s*=|\[aria-label\s*="
    r"|^#[A-Za-z][A-Za-z_-]*$")

# 语义型调用（Playwright get_by_* 家族）
SEMANTIC_CALLS = {"get_by_role", "get_by_label", "get_by_placeholder",
                  "get_by_alt_text", "get_by_title", "get_by_test_id"}

BLACK: List[Tuple[re.Pattern, int, str, str]] = [
    (re.compile(r"^\s*/html/|/\s*html\s*/"), -3, "绝对 XPath，DOM 层级一变就挂",
     "改成 data-testid，或 role/label 语义定位"),
    (re.compile(r"\.nth\(\s*\d+\s*\)|\.eq\(\s*\d+\s*\)|\[\s*\d+\s*\]"), -3, "纯索引定位",
     "用 filter(has_text=...) 或给目标元素加 testid"),
    (re.compile(r"click\s*\(\s*\d+\s*,|mouse\s*\.\s*click\s*\(\s*\d+"), -3, "坐标点击",
     "禁止；改用元素定位"),
    (re.compile(r":nth-child|:nth-of-type|following-sibling|preceding-sibling|ancestor::"), -1,
     "依赖 DOM 顺序或相对结构", "换成 testid / role 定位"),
    (re.compile(r"css-[0-9a-z]{4,}|sc-[A-Za-z]{4,}|jsx-\d+|data-v-[0-9a-f]{4,}"), -1,
     "构建生成的 class/scope id，每次发版都可能变", "让前端加 data-testid"),
    (re.compile(r"ember\d+|rc-[a-z]+-\d+|ant-[a-z]+-\d+"), -1,
     "框架自动生成的 id/class", "改用稳定属性或 testid"),
    (re.compile(r"(?:id|class)\s*=\s*[\"'][^\"']*\d{3,}"), -1,
     "id/class 含大段数字，疑似动态生成", "确认是否每次渲染都变；是则换 testid"),
    (re.compile(r"(?:^|[^>])>.*>.*>"), -1, "三层以上子代链，结构耦合强",
     "缩短为单层语义定位或 testid"),
]

# page.click("x") / driver.find_element(By.ID, "x") / page.get_by_role("button", name="x")
CALL_RE = re.compile(
    r"(?:page|self\.page|driver|context|_p|locator|element)\s*\.\s*"
    r"(click|fill|hover|dblclick|check|uncheck|select_option|wait_for_selector|wait_for|"
    r"locator|query_selector|inner_text|text_content|set_input_files|"
    r"find_element|find_elements|"
    r"get_by_role|get_by_label|get_by_placeholder|get_by_text|get_by_test_id|"
    r"get_by_alt_text|get_by_title)\s*\(\s*"
    r"(?:By\.\w+\s*,\s*)?"
    r"([\"'])((?:\\.|(?!\2).)*)\2", re.S)

BY_RE = re.compile(r"By\.(\w+)")
NAME_RE = re.compile(r"name\s*=\s*([\"'])((?:\\.|(?!\1).)*)\1")
CONST_RE = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*=\s*([\"'])((?:\\.|(?!\2).)*)\2\s*$", re.M)
# URL、模板占位符、纯路径（如 /login）都不是选择器
SKIP_RE = re.compile(r"^(https?:)?//|^www\.|^\{[^\}]*\}|^\$|^/[A-Za-z0-9_\-/\.]*$|^\s*$")


def unescape(s: str) -> str:
    """还原字符串里的转义；非 ASCII 先转成 \\uXXXX 再解，避免中文被 latin-1 打乱。"""
    if "\\" not in s:
        return s
    try:
        return s.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except Exception:
        return s


def looks_like_selector(s: str) -> bool:
    """判断是否像选择器；否则认为用例表里写的是中文描述。"""
    if SKIP_RE.search(s.strip()):
        return False
    if re.search(r"[一-鿿]", s) and not re.search(r"[#\.\[\]=/]", s):
        return False
    return True


def score(sel: str, call: str = "", by: str = "") -> Tuple[int, str, List[str], str]:
    """返回 (分值, 等级, 问题列表, 建议)。"""
    s = sel.strip()
    reasons: List[str] = []

    if not looks_like_selector(s):
        return -3, "D", ["不是选择器（疑似中文描述或占位值）"], \
               "替换为 data-testid / get_by_role 等稳定写法，见 references/locator_guide.md §5"

    sc = 0
    if call == "get_by_test_id" or R_TESTID.search(s):
        sc += 3
    elif call in SEMANTIC_CALLS or R_SEMANTIC.search(s) or by in ("ID", "NAME", "LINK_TEXT"):
        sc += 2
    elif call == "get_by_text" or re.match(r"^text\s*=", s) or "has_text" in s:
        sc += 1
    elif by == "XPATH":
        sc += 0

    worst: Optional[Tuple[int, str, str]] = None
    for pat, val, why, fix in BLACK:
        if pat.search(s):
            sc += val
            reasons.append(why)
            if worst is None or val < worst[0]:
                worst = (val, why, fix)

    if worst:
        advice = worst[2]
    elif sc >= 3:
        advice = "保持"
    elif sc >= 2:
        advice = "可申请补 data-testid 更稳"
    else:
        advice = "建议改为 data-testid 或 get_by_role/get_by_label 语义定位"

    # 与 references/locator_guide.md §3 对齐：+1 的文本定位仍属 C 档
    if sc >= 3:
        level = "A"
    elif sc >= 2:
        level = "B"
    elif sc >= 0:
        level = "C"
    else:
        level = "D"
    return sc, level, reasons, advice


# --------------------------------------------------------------------------- #
# 采集
# --------------------------------------------------------------------------- #

def strip_comments(src: str) -> str:
    out = []
    for ln in src.splitlines():
        out.append(re.sub(r"(?<!['\"])#.*$", "", ln))
    return "\n".join(out)


def collect_from_py(path: Path) -> List[Tuple[str, int, str, str]]:
    """返回 [(选择器, 行号, 调用名, By 类型)]。"""
    src = path.read_text(encoding="utf-8")
    try:
        ast.parse(src, filename=str(path), feature_version=(3, 7))
    except SyntaxError:
        pass
    plain = strip_comments(src)
    found: List[Tuple[str, int, str, str]] = []
    for i, ln in enumerate(plain.splitlines(), 1):
        by_m = BY_RE.search(ln)
        by = by_m.group(1).upper() if by_m else ""
        for m in CALL_RE.finditer(ln):
            call, raw = m.group(1), unescape(m.group(3))
            if call.startswith("get_by_"):  # 显示成完整调用，报告更可读
                nm = NAME_RE.search(ln)
                raw = ('%s("%s", name="%s")' % (call, raw, unescape(nm.group(2)))
                       if nm else '%s("%s")' % (call, raw))
            found.append((raw, i, call, by))
        m2 = CONST_RE.match(ln)
        if m2 and looks_like_selector(unescape(m2.group(3))):
            found.append((unescape(m2.group(3)), i, "CONST", ""))
    return found


def collect_from_cases(path: Path) -> List[Tuple[str, int, str, str]]:
    """从用例 JSON 的 UI 步骤里取 @ 后的元素描述。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", data if isinstance(data, list) else [])
    found: List[Tuple[str, int, str, str]] = []
    for c in cases:
        if str(c.get("type", "")).lower() not in ("ui", "web", "页面", "界面"):
            continue
        for n, ln in enumerate(str(c.get("steps", "")).splitlines(), 1):
            if "@" not in ln:
                continue
            seg = ln.split("@", 1)[1].strip()
            seg = re.split(r"[|，,]", seg)[0].strip()
            if seg:
                found.append((seg, n, "STEP", ""))
    return found


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #

def render(rows: List[Dict], out: Optional[Path]) -> int:
    order = {"D": 0, "C": 1, "B": 2, "A": 3}
    rows.sort(key=lambda r: (order[r["level"]], r["score"]))
    counts = {k: sum(1 for r in rows if r["level"] == k) for k in "ABCD"}

    lines = ["# UI 定位稳定性体检报告", "",
             "| 等级 | 数量 |", "|------|------|"]
    for k, desc in (("A", "契约属性 testid"), ("B", "语义定位"),
                    ("C", "表现/文本"), ("D", "需修复")):
        lines.append("| %s %s | %d |" % (k, desc, counts[k]))
    lines += ["", "| 位置 | 选择器 | 等级 | 分值 | 问题 | 建议 |",
              "|------|--------|------|------|------|------|"]
    for r in rows:
        loc = "%s:%d" % (r["file"], r["line"]) if r["line"] else r["file"]
        problems = "; ".join(r["reasons"]) or "-"
        lines.append("| %s | `%s` | %s | %d | %s | %s |"
                     % (loc, r["selector"].replace("|", "\\|"), r["level"],
                        r["score"], problems, r["advice"]))
    lines += ["", "判定：**%s**" % ("通过（无 D 级）" if counts["D"] == 0
                                   else "不通过，%d 个 D 级定位需修复后再连跑" % counts["D"])]

    text = "\n".join(lines)
    print(text)
    if out:
        out.write_text(text, encoding="utf-8")
        print("\n[locator] 报告已写入：%s" % out)
    return 0 if counts["D"] == 0 else 1


def main() -> int:
    try:  # Windows 控制台默认 GBK，中文报告会乱码
        if hasattr(sys.stdout, "reconfigure"):
            enc = (sys.stdout.encoding or "").lower().replace("-", "")
            if enc != "utf8":
                sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="UI 定位稳定性体检")
    ap.add_argument("--files", nargs="*", default=[], help="要检查的 .py 文件")
    ap.add_argument("--dir", default="", help="要检查的目录（递归 *.py）")
    ap.add_argument("--cases", default="", help="用例 JSON（检查 UI 步骤里写的元素）")
    ap.add_argument("--out", default="", help="报告落盘路径（markdown）")
    ap.add_argument("--strict", action="store_true", help="C 级也判不通过")
    args = ap.parse_args()

    found: List[Tuple[str, int, str, str, str]] = []  # (sel, line, call, by, file)

    files: List[Path] = [Path(f) for f in args.files]
    if args.dir:
        files += sorted(Path(args.dir).rglob("*.py"))
    for f in files:
        if not f.is_file():
            print("[locator][warn] 文件不存在：%s" % f, file=sys.stderr)
            continue
        for sel, ln, call, by in collect_from_py(f):
            found.append((sel, ln, call, by, str(f)))

    if args.cases:
        p = Path(args.cases)
        if not p.is_file():
            print("[locator][warn] 用例文件不存在：%s" % p, file=sys.stderr)
        else:
            for sel, ln, call, by in collect_from_cases(p):
                found.append((sel, ln, call, by, str(p)))

    if not found:
        print("[locator] 未发现可检查的选择器。请确认 --files/--dir/--cases 参数，"
              "或该文件里没有 UI 操作。")
        return 0

    rows: List[Dict] = []
    seen = set()
    for sel, ln, call, by, f in found:
        if SKIP_RE.search(sel.strip()):  # URL / 模板占位符，不是选择器
            continue
        key = (f, ln, sel, call)
        if key in seen:
            continue
        seen.add(key)
        sc, level, reasons, advice = score(sel, call, by)
        if args.strict and level == "C":
            level = "D"
            advice = "--strict 模式：C 级不允许，请改为 testid 或语义定位"
        rows.append({"file": f, "line": ln, "selector": sel, "level": level,
                     "score": sc, "reasons": reasons, "advice": advice})

    return render(rows, Path(args.out) if args.out else None)


if __name__ == "__main__":
    sys.exit(main())
