# -*- coding: utf-8 -*-
"""登录模块示例用例（demo 被测应用）。

断言规范：原生 assert，消息带「期望 X / 实际 Y」。
环境依赖：BASE_URL / DEMO_USER / DEMO_PASSWORD 经 util.env 注入，禁止硬编码。
"""

from page.login_page import LoginPage
from util.env import get_env
from util.logger import get_logger

log = get_logger("test_login")


class TestLogin(object):
    """登录模块（demo 应用：admin/123456）"""

    def test_demo_001(self, session):
        """DEMO-001 正常登录：跳转工作台并显示欢迎语（P0）"""
        page = LoginPage(session).open()
        page.login(get_env("DEMO_USER"), get_env("DEMO_PASSWORD"))

        log.info("断言1：跳转工作台")
        assert page.is_on_dashboard(), (
            "期望 跳转 dashboard.html / 实际 %s" % page.current_url()
        )
        log.info("断言2：欢迎语含用户名")
        welcome = page.dashboard_welcome()
        expect = "欢迎回来，%s" % get_env("DEMO_USER")
        assert expect in welcome, "期望 包含「%s」/ 实际「%s」" % (expect, welcome)

    def test_demo_002(self, session):
        """DEMO-002 密码错误：停留登录页并提示错误（P0）"""
        page = LoginPage(session).open()
        page.login(get_env("DEMO_USER"), "wrongpwd")

        log.info("断言1：未跳转工作台")
        assert not page.is_on_dashboard(), (
            "期望 停留登录页 / 实际 %s" % page.current_url()
        )
        log.info("断言2：错误提示文本")
        actual = page.error_message()
        assert actual == "用户名或密码错误", (
            "期望 用户名或密码错误 / 实际 %s" % actual
        )

    def test_demo_003(self, session):
        """DEMO-003 空值提交：前端校验拦截（P1）"""
        page = LoginPage(session).open()
        page.login("", "")

        actual = page.error_message()
        assert actual == "用户名和密码不能为空", (
            "期望 用户名和密码不能为空 / 实际 %s" % actual
        )
