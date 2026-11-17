# -*- coding: utf-8 -*-
"""登录页 / 工作台 定位集中维护（A 档：data-testid 契约属性）。

约定：
1. 定位只写在本层，用例与 PO 不散写选择器；
2. 命名规则：<模块>-<元素>-<动作>；
3. 前端改版时只改本文件，评审禁止删除已登记的 testid。
"""

USERNAME_INPUT = '[data-testid="login-username-input"]'
PASSWORD_INPUT = '[data-testid="login-password-input"]'
SUBMIT_BUTTON = '[data-testid="login-submit-btn"]'
ERROR_MESSAGE = '[data-testid="login-error-msg"]'
LOGIN_TITLE = '[data-testid="login-title"]'

DASHBOARD_TITLE = '[data-testid="dashboard-title"]'
DASHBOARD_WELCOME = '[data-testid="dashboard-welcome"]'
DASHBOARD_TABLE = '[data-testid="dashboard-table"]'
