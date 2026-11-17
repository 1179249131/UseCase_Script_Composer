#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""learn_style.py — 扫描公司现有 pytest 自动化工程，归纳脚本风格约定。

产出两个文件：
  1) references/style_guide.md   —— 给人/AI 读的风格规范（生成脚本前必读）
  2) references/style_config.json —— 给 generate.py 读的机器可读配置

用法：
  python learn_style.py --project D:/xxx/autotest \
      [--out-md  <skill>/references/style_guide.md] \
      [--out-json <skill>/references/style_config.json] \
      [--stdout]        # 只打印到控制台，不写文件
  python learn_style.py --project D:/xxx/autotest --print-json   # 只打印 JSON

已存在的 style_guide.md 中「## 人工补充约定」章节会被自动保留并追加到新文档末尾。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules", ".idea",
    ".pytest_cache", ".mypy_cache", "dist", "build", ".tox", "htmlcov",
    "allure-results", "allure-report", "reports", "report", "logs", "log",
    ".workbuddy",
}

LAYER_KEYWORDS = {
    "case_dir": ["testcases", "test_case", "test_cases", "cases", "case", "testcase", "tests", "test"],
    "api_dir": ["api", "apis", "interface", "interfaces", "request", "requests", "service", "services"],
    "page_dir": ["page", "pages", "pageobject", "pageobjects", "page_object", "po", "ui", "web"],
    "util_dir": ["common", "commons", "utils", "util", "tools", "helpers", "lib", "libs", "base"],
    "config_dir": ["config", "conf", "settings", "setting"],
    "data_dir": ["data", "testdata", "test_data", "datas", "test_datas"],
}

THIRD_PARTY_HINTS = {
    "requests": "HTTP 客户端: requests",
    "httpx": "HTTP 客户端: httpx",
    "urllib3": "HTTP 客户端: urllib3",
    "playwright": "UI 驱动: Playwright",
    "selenium": "UI 驱动: Selenium",
    "pymysql": "数据库驱动: PyMySQL",
    "psycopg2": "数据库驱动: psycopg2",
    "cx_Oracle": "数据库驱动: cx_Oracle",
    "sqlalchemy": "ORM: SQLAlchemy",
    "allure": "报告: allure-pytest",
    "allure_commons": "报告: allure-pytest",
    "assertpy": "断言库: assertpy",
    "hamcrest": "断言库: hamcrest",
    "jsonschema": "校验: jsonschema",
    "jsonpath": "提取: jsonpath",
    "jsonpath_ng": "提取: jsonpath-ng",
    "loguru": "日志: loguru",
    "ddt": "数据驱动: ddt",
    "yaml": "配置: PyYAML",
    "dotenv": "配置: python-dotenv",
    "redis": "中间件: redis",
    "kafka": "中间件: kafka",
}


# --------------------------------------------------------------------------- #
# 扫描
# --------------------------------------------------------------------------- #
def iter_py_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def is_test_path(p: Path) -> bool:
    name = p.name
    return name.startswith("test_") or name.endswith("_test.py")


def decorator_name(deco: ast.AST) -> str:
    """把装饰器节点还原成可读字符串，如 pytest.fixture / pytest.mark.smoke / allure.story。"""
    node = deco.func if isinstance(deco, ast.Call) else deco
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def unparse_node(node: ast.AST) -> str:
    """把 AST 节点还原成源码文本。

    `ast.unparse` 是 Python 3.9+ 才有的 API，3.7/3.8 上必须走兜底实现。
    """
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        val = ast.literal_eval(node)
        return val if isinstance(val, str) else repr(val)
    except Exception:
        pass
    if isinstance(node, ast.Attribute):
        return "%s.%s" % (unparse_node(node.value), node.attr)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return "%s[%s]" % (unparse_node(node.value), unparse_node(node.slice))
    if isinstance(node, ast.Index):  # 3.8 及以下
        return unparse_node(node.value)
    if isinstance(node, ast.Call):
        return "%s(...)" % unparse_node(node.func)
    return "<expr>"


def keyword_of(deco: ast.AST, key: str):
    if isinstance(deco, ast.Call):
        for kw in deco.keywords:
            if kw.arg == key:
                try:
                    return ast.literal_eval(kw.value)
                except Exception:
                    return unparse_node(kw.value)
    return None


def scan_project(root: Path) -> dict:
    py_files = list(iter_py_files(root))
    test_files = [p for p in py_files if is_test_path(p)]
    conftests = [p for p in py_files if p.name == "conftest.py"]

    stats = {
        "root": str(root),
        "py_file_count": len(py_files),
        "test_file_count": len(test_files),
        "conftest_files": [str(p.relative_to(root)) for p in conftests],
        "imports": Counter(),
        "decorators": Counter(),
        "fixtures": [],          # {name, scope, params, file}
        "markers": Counter(),
        "allure_decorators": Counter(),
        "class_names": [],
        "test_func_names": [],
        "assert_count": 0,
        "assertpy_count": 0,
        "parametrize_count": 0,
        "dirs": [],
        "config_files": [],
        "config_access": Counter(),
        "logging_style": Counter(),
        "readme": "",
        "reusable": {k: [] for k in ("api", "page", "db", "cli", "util", "other")},
    }

    # 目录清单（相对路径，深度 <= 3）
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) <= 3:
            stats["dirs"].append(rel.as_posix())

    # 配置文件
    for name in ("pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml", "conftest.py",
                 "requirements.txt", "config.ini", "config.yaml", "config.yml", "env.ini", ".env"):
        p = root / name
        if p.exists():
            stats["config_files"].append(name)

    for p in py_files:
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        rel = p.relative_to(root).as_posix()

        for node in ast.walk(tree):
            # imports
            if isinstance(node, ast.Import):
                for a in node.names:
                    stats["imports"][a.name.split(".")[0]] += 1
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    stats["imports"][node.module.split(".")[0]] += 1
            # asserts
            elif isinstance(node, ast.Assert):
                stats["assert_count"] += 1
            elif isinstance(node, ast.Call):
                fname = decorator_name(node) if isinstance(node.func, (ast.Attribute, ast.Name)) else ""
                if fname in ("assert_that", "assertThat", "expect"):
                    stats["assertpy_count"] += 1
                if "getLogger" in fname:
                    stats["logging_style"]["logging.getLogger"] += 1
                if fname.startswith("logger.") or fname.startswith("log."):
                    stats["logging_style"]["logger/log 对象"] += 1
                if fname == "print":
                    stats["logging_style"]["print"] += 1
                if "getenv" in fname:
                    stats["config_access"]["os.getenv"] += 1
                if fname in ("safe_load", "load"):
                    stats["config_access"]["yaml 配置"] += 1

        # 顶层 + 类内函数
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decos = [decorator_name(d) for d in node.decorator_list]
            is_fixture = any(d.startswith("pytest.fixture") or d == "fixture" for d in decos)
            if is_fixture:
                scope = None
                params = None
                for d in node.decorator_list:
                    scope = scope or keyword_of(d, "scope")
                    params = params or keyword_of(d, "params")
                stats["fixtures"].append({
                    "name": node.name,
                    "scope": scope or "function",
                    "params": params,
                    "file": rel,
                })
            for d in decos:
                stats["decorators"][d.split("(")[0]] += 1
                if d.startswith("pytest.mark."):
                    stats["markers"][d.split(".")[-1].split("(")[0]] += 1
                if d.startswith("allure."):
                    stats["allure_decorators"][d.split(".")[-1].split("(")[0]] += 1
                if "parametrize" in d:
                    stats["parametrize_count"] += 1
            if is_test_path(p) or node.name.startswith("test"):
                stats["test_func_names"].append(node.name)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                stats["class_names"].append((node.name, rel))

        # 可复用方法清单：只收非测试文件里的公共函数与类方法
        if not is_test_path(p) and p.name != "conftest.py":
            collect_reusable(tree, rel, root, p, stats["reusable"])

    return stats


# --------------------------------------------------------------------------- #
# 可复用方法清单（复用优先的核心依据）
# --------------------------------------------------------------------------- #
KIND_RULES = (
    ("api", ("api", "apis", "request", "requests", "client", "http", "https", "interface")),
    ("page", ("page", "pages", "po", "ui", "web", "element", "elements")),
    ("db", ("db", "dao", "sql", "mysql", "database", "orm", "redis")),
    ("cli", ("cli", "cmd", "command", "commands", "shell", "runner", "exec")),
    ("util", ("util", "utils", "common", "helper", "helpers", "tools", "base", "lib", "libs")),
)

MAX_PER_KIND = 30


def module_name_for(root: Path, rel: str) -> str:
    parts = rel.split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def kind_of(rel: str, extra: str = "") -> str:
    """按路径/文件名/方法名判定所属层。分隔符含 `/ . _ -`，并去掉 .py 后缀，
    否则 `db_util.py` 会被当成一整段而认不出 db 层。
    """
    low = re.sub(r"\.py$", "", (rel + "/" + extra).lower())
    segs = set(re.split(r"[/. _\-]", low))
    for kind, keys in KIND_RULES:
        if segs & set(keys):
            return kind
    return "other"


def signature_of(node) -> str:
    """渲染函数签名，兼容 Python 3.7 的 AST 结构。"""
    a = node.args
    parts: List[str] = []
    pos = [x.arg for x in a.args]
    defaults: List = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for name, d in zip(pos, defaults):
        if d is None:
            parts.append(name)
        else:
            try:
                parts.append("%s=%s" % (name, unparse_node(d)))
            except Exception:
                parts.append(name + "=...")
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    for x, d in zip(a.kwonlyargs, a.kw_defaults):
        parts.append(x.arg if d is None else "%s=%s" % (x.arg, unparse_node(d) if d else "None"))
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return "(" + ", ".join(parts) + ")"


def collect_reusable(tree: ast.AST, rel: str, root: Path, path: Path, bucket: dict) -> None:
    """把工程里可复用的公共函数/类方法登记到 bucket[kind]。"""
    mod = module_name_for(root, rel)
    kind_file = kind_of(rel)

    def add(name, cls, sig, doc, kind):
        if len(bucket.get(kind, [])) >= MAX_PER_KIND:
            return
        bucket.setdefault(kind, []).append({
            "module": mod, "file": rel, "cls": cls, "name": name,
            "signature": sig, "doc": (doc or "").strip().splitlines()[0][:60] if doc else "",
        })

    def skip(node) -> bool:
        if node.name.startswith("_") or node.name.startswith("test"):
            return True
        return any(decorator_name(d) in ("property", "staticmethod", "classmethod", "abstractmethod")
                   for d in node.decorator_list)

    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if skip(node):
                continue
            decos = [decorator_name(d) for d in node.decorator_list]
            if any("fixture" in d for d in decos):
                continue
            add(node.name, "", signature_of(node), ast.get_docstring(node),
                kind_of(rel, node.name))
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            cls_kind = kind_of(rel, node.name)
            if cls_kind == "other":
                cls_kind = kind_file
            for sub in node.body:
                if not isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if skip(sub) or sub.name == "__init__":
                    continue
                add(sub.name, node.name, signature_of(sub), ast.get_docstring(sub), cls_kind)


def infer_config(stats: dict, root: Path) -> dict:
    imports = stats["imports"]

    # 文件命名
    test_prefix = sum(1 for p in stats.get("_test_files_preview", []))  # 占位
    file_prefix = "test_"
    # 通过目录里真实文件名判断（重新扫一次更准，这里用简单启发式）
    try:
        names = [p.name for p in iter_py_files(root) if is_test_path(p)]
        if names:
            n_start = sum(1 for n in names if n.startswith("test_"))
            n_end = sum(1 for n in names if n.endswith("_test.py"))
            if n_end > n_start:
                file_prefix = "_test"
    except Exception:
        pass

    # 类名
    test_classes = [c for c, _ in stats["class_names"] if c.startswith("Test")]
    use_class = len(test_classes) > 0

    # 函数命名：是否 snake_case、是否带用例编号
    funcs = stats["test_func_names"]
    snake = sum(1 for f in funcs if re.fullmatch(r"[a-z0-9_]+", f))
    has_case_id = sum(1 for f in funcs if re.search(r"(?<=_)\d{2,}|case_?\d+", f, re.I))
    func_pattern = "test_{case_id}" if funcs and has_case_id > len(funcs) * 0.3 else "test_{title_slug}"

    # 分层目录
    layers = {}
    dirs = stats["dirs"]
    for key, kws in LAYER_KEYWORDS.items():
        best = None
        for d in sorted(dirs, key=lambda x: (len(x.split("/")), x)):
            last = d.split("/")[-1].lower()
            if last in kws:
                best = d
                break
        layers[key] = best  # 可能为 None

    # 第三方库
    third_party = {}
    for mod, desc in THIRD_PARTY_HINTS.items():
        if imports.get(mod):
            third_party[mod] = {"desc": desc, "count": imports[mod]}

    http_client = "requests"
    for cand in ("requests", "httpx", "urllib3"):
        if imports.get(cand):
            http_client = cand
            break

    ui_driver = "none"
    if imports.get("playwright"):
        ui_driver = "playwright"
    elif imports.get("selenium"):
        ui_driver = "selenium"

    db_driver = "none"
    for cand in ("pymysql", "psycopg2", "cx_Oracle", "sqlalchemy"):
        if imports.get(cand):
            db_driver = cand
            break

    assert_style = "assertpy" if stats["assertpy_count"] > stats["assert_count"] * 0.3 else "assert"

    fixture_names = sorted({f["name"] for f in stats["fixtures"]})
    top_imports = [m for m, _ in imports.most_common(25)]

    cfg = {
        "project_root": str(root),
        "file_naming": {
            "prefix": file_prefix,
            "pattern": "test_{module}.py",
            "aggregation": "module",  # module | case
        },
        "class_naming": {
            "use_class": use_class,
            "pattern": "Test{Module}",
        },
        "func_naming": {
            "pattern": func_pattern,
            "snake_case": bool(funcs) and snake > len(funcs) * 0.6,
            "lowercase": True,
        },
        "fixtures": {
            "available": fixture_names,
            "api": guess_fixture(fixture_names, ["api", "client", "session", "request", "http", "token", "login"]),
            "db": guess_fixture(fixture_names, ["db", "sql", "conn", "mysql", "database", "cursor"]),
            "browser": guess_fixture(fixture_names, ["page", "browser", "driver", "ui", "web"]),
            "cli": guess_fixture(fixture_names, ["cli", "cmd", "shell", "command", "runner"]),
        },
        "markers": [m for m, _ in stats["markers"].most_common(10)],
        "allure": bool(stats["allure_decorators"]),
        "allure_decorators": [d for d, _ in stats["allure_decorators"].most_common(6)],
        "parametrize_used": stats["parametrize_count"] > 0,
        "assert_style": assert_style,
        "http_client": http_client,
        "ui_driver": ui_driver,
        "db_driver": db_driver,
        "third_party": third_party,
        "top_imports": top_imports,
        "layers": layers,
        "reusable": stats.get("reusable", {}),
        "reuse_preferred": {
            "api": pick_preferred(stats.get("reusable", {}).get("api", []),
                                  ("request", "send", "call", "do", "http", "post", "get")),
            "page": pick_preferred(stats.get("reusable", {}).get("page", []),
                                  ("open", "goto", "login", "click", "fill", "input", "submit", "search")),
            "db": pick_preferred(stats.get("reusable", {}).get("db", []),
                                 ("query", "select", "execute", "fetch", "run", "get")),
            "cli": pick_preferred(stats.get("reusable", {}).get("cli", []),
                                 ("run", "exec", "execute", "cmd", "shell", "command")),
            "util": pick_preferred(stats.get("reusable", {}).get("util", []),
                                  ("get", "read", "load", "build", "make", "init")),
        },
        "conftest_files": stats["conftest_files"],
        "config_files": stats["config_files"],
        "config_access": [k for k, _ in stats["config_access"].most_common(3)],
        "logging": [k for k, _ in stats["logging_style"].most_common(3)],
        "custom": {
            "header_imports": [],
            "base_class": "",
            "module_docstring": True,
            "notes": [],
        },
    }
    return cfg


def guess_fixture(names, keywords):
    """按「整段匹配 > 首尾匹配 > 子串匹配」的优先级挑最合适的 fixture。

    避免把 api_client 误判成 CLI fixture（'client' 里含 'cli'）。
    """
    best = ""
    best_score = 0
    for n in names:
        segs = [s.lower() for s in n.split("_")]
        score = 0
        for k in keywords:
            if k in segs:
                score = max(score, 3)
            elif any(s == k or s.startswith(k) or s.endswith(k) for s in segs):
                score = max(score, 2) if len(k) >= 5 else max(score, 1)
            elif any(k in s for s in segs):
                score = max(score, 1)
        if score > best_score:
            best, best_score = n, score
    # 只认「整段命中 / 长关键字首尾命中」，避免 client→cli 这类误判
    return best if best_score >= 2 else ""


def pick_preferred(items: List[dict], keywords) -> str:
    """挑出该层最该复用的入口方法，形如 `module.Class.method` 或 `module.func`。"""
    if not items:
        return ""

    def full(it: dict) -> str:
        return "%s.%s%s" % (it["module"], (it["cls"] + ".") if it["cls"] else "", it["name"])

    lowered = [(it, it["name"].lower()) for it in items]
    for k in keywords:
        for it, low in lowered:
            if k in low:
                return full(it)
    return full(items[0])


# --------------------------------------------------------------------------- #
# 渲染 Markdown
# --------------------------------------------------------------------------- #
def render_markdown(stats: dict, cfg: dict) -> str:
    L = []
    A = L.append
    A("# 自动化脚本风格规范（由 learn_style.py 自动生成）")
    A("")
    A(f"> 来源工程：`{cfg['project_root']}`")
    A(f"> 扫描统计：Python 文件 {stats['py_file_count']} 个，其中测试文件 {stats['test_file_count']} 个。")
    A("")
    A("**使用约定**：本文件由脚本自动归纳，结论可能有偏差。**「## 人工补充约定」章节由人工维护，"
      "优先级最高**，重新执行 learn_style.py 时该章节会被自动保留。")
    A("")

    A("## 1. 工程结构")
    A("")
    A("```")
    for d in sorted(stats["dirs"], key=lambda x: (len(x.split("/")), x))[:40]:
        A(d if d != "." else ".")
    A("```")
    A("")
    A("识别出的分层目录：")
    A("")
    A("| 角色 | 目录 |")
    A("|------|--------|")
    for key in ("case_dir", "api_dir", "page_dir", "util_dir", "config_dir", "data_dir"):
        A(f"| {key} | `{cfg['layers'].get(key) or '（未识别，需人工确认）'}` |")
    A("")

    A("## 2. 文件与命名")
    A("")
    A(f"- 测试文件命名：`{cfg['file_naming']['pattern']}`（前缀 `{cfg['file_naming']['prefix']}`），"
      f"聚合粒度：{cfg['file_naming']['aggregation']}")
    A(f"- 是否使用测试类：**{'是' if cfg['class_naming']['use_class'] else '否'}**，"
      f"类名形如 `{cfg['class_naming']['pattern']}`")
    A(f"- 测试函数命名：`{cfg['func_naming']['pattern']}`"
      f"（snake_case: {'是' if cfg['func_naming']['snake_case'] else '否'}）")
    A(f"- 参数化使用：{'是' if cfg['parametrize_used'] else '否'}")
    A("")

    A("## 3. Fixture 与依赖注入")
    A("")
    if cfg["fixtures"]["available"]:
        A("工程内已定义的 fixture（**优先直接复用，不要自己 new 客户端**）：")
        A("")
        A("| fixture | scope | 定义位置 |")
        A("|---------|-------|----------|")
        seen = set()
        for f in stats["fixtures"]:
            if f["name"] in seen:
                continue
            seen.add(f["name"])
            A(f"| `{f['name']}` | {f['scope']} | `{f['file']}` |")
        A("")
        A("按类型推荐的 fixture：")
        A("")
        for k in ("api", "db", "browser", "cli"):
            A(f"- {k}: `{cfg['fixtures'][k] or '（未识别，生成时需在测试内自建并加 TODO）'}`")
    else:
        A("未扫描到 `@pytest.fixture`，生成脚本时在测试函数内自行构造客户端。")
    A("")

    A("## 4. 断言与标记")
    A("")
    A(f"- 断言风格：`{cfg['assert_style']}`"
      + ("（检测到 assert_that）" if cfg["assert_style"] == "assertpy" else "（原生 assert）"))
    A(f"- pytest 标记（markers）：{', '.join('`%s`' % m for m in cfg['markers']) or '（无）'}")
    A(f"- allure：{'启用' if cfg['allure'] else '未启用'}"
      + (f"，常用装饰器：{', '.join(cfg['allure_decorators'])}" if cfg["allure"] else ""))
    A("")

    A("## 5. 依赖与技术选型")
    A("")
    A("| 类别 | 选型 |")
    A("|------|------|")
    A(f"| HTTP | {cfg['http_client']} |")
    A(f"| UI | {cfg['ui_driver']} |")
    A(f"| DB | {cfg['db_driver']} |")
    A(f"| 断言 | {cfg['assert_style']} |")
    A("")
    if cfg["third_party"]:
        A("高频第三方库：")
        A("")
        for mod, info in list(cfg["third_party"].items())[:15]:
            A(f"- `{mod}` — {info['desc']}（引用 {info['count']} 次）")
        A("")

    A("## 6. 配置与日志")
    A("")
    A(f"- 配置文件：{', '.join(cfg['config_files']) or '（未识别）'}")
    A(f"- 配置读取方式：{', '.join(cfg['config_access']) or '（未识别）'}")
    A(f"- 日志方式：{', '.join(cfg['logging']) or '（未识别）'}")
    A("- conftest.py 位置：" + (", ".join(f"`{c}`" for c in cfg["conftest_files"]) or "（无）"))
    A("")

    A("## 7. 可复用方法清单（**优先复用，不要重复造轮子**）")
    A("")
    A("> **写脚本前先查本节。** 能调用已有方法就直接调用；确认确实没有再自己实现，"
      "而且新实现要放进对应层（`api` / `page` / `db` / `cli` / `util`），供后续用例复用。")
    A("")
    reusable = cfg.get("reusable", {})
    kind_title = {"api": "接口封装", "page": "页面对象 / UI 操作", "db": "数据库操作",
                  "cli": "命令行执行", "util": "公共工具", "other": "其他"}
    for kind in ("api", "page", "db", "cli", "util", "other"):
        items = reusable.get(kind, [])
        if not items:
            continue
        A(f"### {kind} — {kind_title.get(kind, kind)}")
        A("")
        A("| 方法 | 签名 | 位置（文件） | 说明 |")
        A("|------|------|--------------|------|")
        for it in items[:15]:
            ref = "`%s.%s%s`" % (it["module"], (it["cls"] + ".") if it["cls"] else "", it["name"])
            A("| %s | `%s` | `%s` | %s |" % (ref, it["signature"], it["file"], it["doc"] or ""))
        if len(items) > 15:
            A("")
            A(f"（共 {len(items)} 个，此处列出前 15 个）")
        A("")
    if not any(reusable.get(k) for k in reusable):
        A("未识别到工程内的封装方法。生成时会自建客户端；**自建实现请顺手抽到对应层**，"
          "下次 `learn_style.py` 就会把它登记进来。")
        A("")
    A("推荐入口（生成脚本时优先调用的那一层）：")
    A("")
    A("| 类别 | 优先调用 |")
    A("|------|----------|")
    for k, label in (("api", "接口"), ("page", "页面"), ("db", "数据库"),
                     ("cli", "命令行"), ("util", "工具")):
        pref = cfg.get("reuse_preferred", {}).get(k, "")
        A(f"| {label} | `{pref or '（无，需自建并抽到该层）'}` |")
    A("")
    A("**复用判定**：出现下面这些裸调用，而本节有对应封装时，就是重复造轮子——必须改成调用封装：")
    A("")
    A("- 接口：`requests.get/post/request(...)` 直连")
    A("- UI：`webdriver.Chrome()`、重复写 `page.click(...)` 而 PO 里已有对应方法")
    A("- DB：`pymysql.connect(...)` 直连")
    A("- CLI：`subprocess.run(...)` 裸调")
    A("")

    A("## 8. 生成脚本时的硬性要求")
    A("")
    A("1. **优先复用已有方法**：先查第 3 节的 fixture 与第 7 节的可复用清单，"
      "能调用就调用，禁止在用例里重写已有的请求/页面/数据库/命令封装。")
    A("2. 函数与文件命名严格遵循第 2 节的规则。")
    A("3. 断言遵循第 3/4 节风格，断言消息写清楚「期望 X，实际 Y」。")
    A("4. 环境相关值（URL、账号、DB 连接）一律从配置/环境变量读取，禁止硬编码。")
    A("5. 每个用例函数保留 docstring：用例编号 + 标题 + 前置条件 + 步骤 + 预期。")
    A("")

    A("## 人工补充约定")
    A("")
    A("<!-- 本节由人工维护，重新执行 learn_style.py 时会自动保留。请把团队口头约定、"
      "代码里看不出来的规范写在这里。 -->")
    A("")
    A("- （待补充）")
    return "\n".join(L)


def preserve_manual_section(old_path: Path) -> str:
    if not old_path.exists():
        return ""
    try:
        text = old_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(r"^## 人工补充约定\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return ""
    body = m.group(1).strip()
    # 去掉仍是占位的内容
    body = re.sub(r"^<!--.*?-->\s*$", "", body, flags=re.M | re.S).strip()
    body = re.sub(r"^- （待补充）\s*$", "", body, flags=re.M).strip()
    return body


def main():
    ap = argparse.ArgumentParser(description="归纳 pytest 自动化工程风格")
    ap.add_argument("--project", required=True, help="自动化工程根目录")
    ap.add_argument("--out-md", default=None, help="风格规范 markdown 输出路径")
    ap.add_argument("--out-json", default=None, help="机器可读风格配置输出路径")
    ap.add_argument("--stdout", action="store_true", help="只打印 markdown，不写文件")
    ap.add_argument("--print-json", action="store_true", help="只打印 JSON，不写文件")
    args = ap.parse_args()

    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"[learn_style] 目录不存在: {root}")

    stats = scan_project(root)
    cfg = infer_config(stats, root)
    md = render_markdown(stats, cfg)

    here = Path(__file__).resolve().parent.parent
    out_md = Path(args.out_md) if args.out_md else here / "references" / "style_guide.md"
    out_json = Path(args.out_json) if args.out_json else here / "references" / "style_config.json"

    if args.print_json:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return
    if args.stdout:
        print(md)
        return

    manual = preserve_manual_section(out_md)
    if manual:
        md = md.rstrip() + "\n\n" + manual + "\n"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")

    # JSON 合并：保留已有 custom 段落中的人工配置
    if out_json.exists():
        try:
            old = json.loads(out_json.read_text(encoding="utf-8"))
            cfg["custom"] = old.get("custom", cfg["custom"])
        except Exception:
            pass
    out_json.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[learn_style] 已扫描 {stats['py_file_count']} 个 Python 文件（测试文件 {stats['test_file_count']} 个）")
    print(f"[learn_style] 风格规范 -> {out_md}")
    print(f"[learn_style] 风格配置 -> {out_json}")
    print("[learn_style] 请人工复核 style_guide.md，并在「## 人工补充约定」补充口头约定。")


if __name__ == "__main__":
    main()
