# -*- coding: utf-8 -*-
"""PO 基类：持有浏览器会话与日志，提供公共页面动作。"""

from util.logger import get_logger


class BasePage(object):
    def __init__(self, session):
        self.session = session
        self.log = get_logger(self.__class__.__name__)

    def open(self, url):
        self.log.debug("打开页面 %s", url)
        self.session.goto(url)

    def current_url(self):
        return self.session.current_url()

    def element_text(self, selector):
        return self.session.text(selector)

    def is_visible(self, selector):
        return self.session.is_visible(selector)
