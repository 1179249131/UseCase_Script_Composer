# -*- coding: utf-8 -*-
"""日志规范（skill 规范未覆盖项的工程级补齐）。

约定：
1. 统一使用 logging 标准库，logger 名按模块命名（autotest.<模块>）。
2. 级别由环境变量 LOG_LEVEL 控制，默认 INFO。
3. 格式：[HH:MM:SS] [LEVEL] [logger] 消息。
4. 双输出：控制台 + reports/logs/autotest.log（UTF-8）。
5. 用例只在关键步骤记 INFO（打开页面/提交/断言点），PO 层记 DEBUG。
"""

import logging
import os

from util.env import get_env

_INITIALIZED = False
_LOG_FILE = os.path.join("reports", "logs", "autotest.log")


def get_logger(name):
    global _INITIALIZED
    logger = logging.getLogger("autotest." + name)
    if not _INITIALIZED:
        level = getattr(logging, get_env("LOG_LEVEL").upper(), logging.INFO)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%H:%M:%S"
        )
        root = logging.getLogger("autotest")
        root.setLevel(level)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
        log_dir = os.path.dirname(_LOG_FILE)
        if log_dir and not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        root.propagate = False
        _INITIALIZED = True
    return logger
