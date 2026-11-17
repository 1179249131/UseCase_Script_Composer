# -*- coding: utf-8 -*-
"""pytest 公共夹具。

- session：函数级浏览器会话（每个用例独立上下文，用例间无状态泄漏）。
- 引擎/地址/账号等全部经 util.env 从环境变量读取，禁止硬编码。
"""

import os
import sys

import pytest

# 保证工程根目录在 sys.path（从任意目录执行 pytest 均可运行）
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from util.browser import create_session  # noqa: E402
from util.env import is_headless  # noqa: E402
from util.logger import get_logger  # noqa: E402

log = get_logger("conftest")


@pytest.fixture()
def session():
    log.info("创建浏览器会话（headless=%s）", is_headless())
    s = create_session()
    try:
        yield s
    finally:
        s.close()
        log.info("浏览器会话已关闭")
