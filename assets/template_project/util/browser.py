# -*- coding: utf-8 -*-
"""浏览器会话统一封装（Playwright / Selenium 双后端）。

规范：
1. 用例与 PO 层只依赖 BrowserSession 接口，不直接 import 任一框架；
   切换引擎只改环境变量 BROWSER_ENGINE（playwright | selenium）。
2. 选择器统一使用 CSS（两个后端均原生支持）；定位一律来自 locators 层。
3. 等待禁止 sleep：用 wait_visible()；两后端都内置元素级等待。
4. Playwright 后端优先复用本机 Chrome（channel="chrome"），无需下载浏览器；本机无 Chrome
   时自动回退到内置 Chromium，此时需先执行 python -m playwright install chromium。
"""

from util.env import get_env, get_timeout_ms, is_headless
from util.logger import get_logger

log = get_logger("browser")


class BrowserSession(object):
    """浏览器会话接口。PO/用例层只使用这些方法。"""

    def goto(self, url):
        raise NotImplementedError

    def fill(self, selector, value):
        raise NotImplementedError

    def click(self, selector):
        raise NotImplementedError

    def wait_visible(self, selector):
        raise NotImplementedError

    def text(self, selector):
        """返回元素可见文本；元素不存在返回空串。"""
        raise NotImplementedError

    def is_visible(self, selector):
        raise NotImplementedError

    def current_url(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    # 上下文管理：with create_session() as s: ...
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class PlaywrightSession(BrowserSession):
    def __init__(self):
        from playwright.sync_api import sync_playwright

        self._timeout = get_timeout_ms()
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                channel="chrome", headless=is_headless()
            )
        except Exception as e:
            # 本机未安装 Chrome（或 channel 不可用）时回退到 Playwright 内置 Chromium。
            # 需先执行：python -m playwright install chromium
            log.warning("本机 Chrome 不可用，回退内置 Chromium：%s", e)
            self._browser = self._pw.chromium.launch(headless=is_headless())
        self._ctx = self._browser.new_context()
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(self._timeout)
        log.debug("Playwright 会话已启动（channel=chrome, headless=%s）", is_headless())

    def goto(self, url):
        self._page.goto(url)

    def fill(self, selector, value):
        self._page.fill(selector, value)

    def click(self, selector):
        self._page.click(selector)

    def wait_visible(self, selector):
        self._page.wait_for_selector(selector, state="visible", timeout=self._timeout)

    def text(self, selector):
        try:
            return self._page.inner_text(selector, timeout=1500)
        except Exception:
            return ""

    def is_visible(self, selector):
        return self._page.is_visible(selector)

    def current_url(self):
        return self._page.url

    def close(self):
        for closer in (self._ctx.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception:
                pass


class SeleniumSession(BrowserSession):
    def __init__(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        self._timeout = get_timeout_ms()
        opts = Options()
        if is_headless():
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,800")
        try:
            self._driver = webdriver.Chrome(options=opts)
        except Exception as e:
            raise RuntimeError(
                "Selenium 启动 Chrome 失败：%s\n"
                "若为驱动下载失败（国内网络），请手动从 "
                "https://registry.npmmirror.com/-/binary/chrome-for-testing/ "
                "下载与本机 Chrome 大版本匹配的 chromedriver，放入 PATH 后重试。" % e
            )
        log.debug("Selenium 会话已启动（headless=%s）", is_headless())

    def goto(self, url):
        self._driver.get(url)

    def fill(self, selector, value):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        el = WebDriverWait(self._driver, self._timeout / 1000.0).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
        )
        el.clear()
        el.send_keys(value)

    def click(self, selector):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self._driver, self._timeout / 1000.0).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        ).click()

    def wait_visible(self, selector):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self._driver, self._timeout / 1000.0).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
        )

    def text(self, selector):
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException

        try:
            return self._driver.find_element(By.CSS_SELECTOR, selector).text
        except NoSuchElementException:
            return ""

    def is_visible(self, selector):
        from selenium.webdriver.common.by import By

        els = self._driver.find_elements(By.CSS_SELECTOR, selector)
        return bool(els) and els[0].is_displayed()

    def current_url(self):
        return self._driver.current_url

    def close(self):
        try:
            self._driver.quit()
        except Exception:
            pass


def create_session():
    """工厂：按 BROWSER_ENGINE 创建会话。默认 playwright。"""
    engine = get_env("BROWSER_ENGINE").strip().lower()
    if engine == "selenium":
        log.info("使用 Selenium 引擎")
        return SeleniumSession()
    log.info("使用 Playwright 引擎")
    return PlaywrightSession()
