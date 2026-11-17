# -*- coding: utf-8 -*-
"""登录页 PO：只暴露业务动作，不暴露选择器。"""

from locators import login_locators as L
from page.base_page import BasePage
from util.env import get_env


class LoginPage(BasePage):
    PATH = "/login.html"

    def open(self):
        self.open_url = get_env("BASE_URL").rstrip("/") + self.PATH
        self.log.debug("打开登录页 %s", self.open_url)
        self.session.goto(self.open_url)
        self.session.wait_visible(L.SUBMIT_BUTTON)
        return self

    def login(self, username, password):
        self.log.info("提交登录：用户名=%s", username)
        self.session.fill(L.USERNAME_INPUT, username)
        self.session.fill(L.PASSWORD_INPUT, password)
        self.session.click(L.SUBMIT_BUTTON)

    def error_message(self):
        return self.session.text(L.ERROR_MESSAGE).strip()

    def is_on_dashboard(self):
        return "dashboard.html" in self.session.current_url()

    def dashboard_welcome(self):
        self.session.wait_visible(L.DASHBOARD_WELCOME)
        return self.session.text(L.DASHBOARD_WELCOME).strip()
