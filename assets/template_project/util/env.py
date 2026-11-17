# -*- coding: utf-8 -*-
"""环境配置读取（集中入口）。

规范：任何环境相关值（URL、账号、引擎、超时）一律经本模块从环境变量读取，
禁止在用例/PO/封装层硬编码。默认值仅用于本地开发兜底。
"""

import os

DEFAULTS = {
    "BASE_URL": "http://127.0.0.1:8765",
    "BROWSER_ENGINE": "playwright",   # playwright | selenium
    "HEADLESS": "true",
    "LOG_LEVEL": "INFO",
    "DEMO_USER": "admin",
    "DEMO_PASSWORD": "123456",
    "DEFAULT_TIMEOUT_MS": "10000",
}


def get_env(key, default=None):
    """读取环境变量；未设置时回落到 DEFAULTS，再回落到显式 default。"""
    val = os.getenv(key)
    if val is not None and val != "":
        return val
    if key in DEFAULTS:
        return DEFAULTS[key]
    return default


def get_timeout_ms():
    """统一超时（毫秒）。非法值回退默认。"""
    try:
        return int(get_env("DEFAULT_TIMEOUT_MS"))
    except (TypeError, ValueError):
        return 10000


def is_headless():
    # strip()：Windows 下 `set HEADLESS=false && ...` 会把尾随空格写进变量值
    return get_env("HEADLESS").strip().lower() not in ("false", "0", "no")
