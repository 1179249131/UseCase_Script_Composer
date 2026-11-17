# 自动化脚本风格规范（由 learn_style.py 自动生成）

> 来源工程：`browser_autotest`（`learn_style.py` 示例扫描产物）
> 扫描统计：Python 文件 16 个，其中测试文件 1 个。

**使用约定**：本文件由脚本自动归纳，结论可能有偏差。**「## 人工补充约定」章节由人工维护，优先级最高**，重新执行 learn_style.py 时该章节会被自动保留。

## 1. 工程结构

```
.
api
cli
db
demo
locators
page
testcases
util
```

识别出的分层目录：

| 角色 | 目录 |
|------|--------|
| case_dir | `testcases` |
| api_dir | `api` |
| page_dir | `page` |
| util_dir | `util` |
| config_dir | `（未识别，需人工确认）` |
| data_dir | `（未识别，需人工确认）` |

## 2. 文件与命名

- 测试文件命名：`test_{module}.py`（前缀 `test_`），聚合粒度：module
- 是否使用测试类：**是**，类名形如 `Test{Module}`
- 测试函数命名：`test_{case_id}`（snake_case: 是）
- 参数化使用：否

## 3. Fixture 与依赖注入

工程内已定义的 fixture（**优先直接复用，不要自己 new 客户端**）：

| fixture | scope | 定义位置 |
|---------|-------|----------|
| `session` | function | `conftest.py` |

按类型推荐的 fixture：

- api: `session`
- db: `（未识别，生成时需在测试内自建并加 TODO）`
- browser: `（未识别，生成时需在测试内自建并加 TODO）`
- cli: `（未识别，生成时需在测试内自建并加 TODO）`

## 4. 断言与标记

- 断言风格：`assert`（原生 assert）
- pytest 标记（markers）：（无）
- allure：未启用

## 5. 依赖与技术选型

| 类别 | 选型 |
|------|------|
| HTTP | requests |
| UI | playwright |
| DB | none |
| 断言 | assert |

高频第三方库：

- `playwright` — UI 驱动: Playwright（引用 1 次）
- `selenium` — UI 驱动: Selenium（引用 14 次）

## 6. 配置与日志

- 配置文件：pytest.ini, conftest.py, requirements.txt
- 配置读取方式：os.getenv
- 日志方式：logger/log 对象, logging.getLogger, print
- conftest.py 位置：`conftest.py`

## 7. 可复用方法清单（**优先复用，不要重复造轮子**）

> **写脚本前先查本节。** 能调用已有方法就直接调用；确认确实没有再自己实现，而且新实现要放进对应层（`api` / `page` / `db` / `cli` / `util`），供后续用例复用。

### page — 页面对象 / UI 操作

| 方法 | 签名 | 位置（文件） | 说明 |
|------|------|--------------|------|
| `page.base_page.BasePage.open` | `(self, url)` | `page/base_page.py` |  |
| `page.base_page.BasePage.current_url` | `(self)` | `page/base_page.py` |  |
| `page.base_page.BasePage.element_text` | `(self, selector)` | `page/base_page.py` |  |
| `page.base_page.BasePage.is_visible` | `(self, selector)` | `page/base_page.py` |  |
| `page.login_page.LoginPage.open` | `(self)` | `page/login_page.py` |  |
| `page.login_page.LoginPage.login` | `(self, username, password)` | `page/login_page.py` |  |
| `page.login_page.LoginPage.error_message` | `(self)` | `page/login_page.py` |  |
| `page.login_page.LoginPage.is_on_dashboard` | `(self)` | `page/login_page.py` |  |
| `page.login_page.LoginPage.dashboard_welcome` | `(self)` | `page/login_page.py` |  |

### util — 公共工具

| 方法 | 签名 | 位置（文件） | 说明 |
|------|------|--------------|------|
| `util.browser.BrowserSession.goto` | `(self, url)` | `util/browser.py` |  |
| `util.browser.BrowserSession.fill` | `(self, selector, value)` | `util/browser.py` |  |
| `util.browser.BrowserSession.click` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.BrowserSession.wait_visible` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.BrowserSession.text` | `(self, selector)` | `util/browser.py` | 返回元素可见文本；元素不存在返回空串。 |
| `util.browser.BrowserSession.is_visible` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.BrowserSession.current_url` | `(self)` | `util/browser.py` |  |
| `util.browser.BrowserSession.close` | `(self)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.goto` | `(self, url)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.fill` | `(self, selector, value)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.click` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.wait_visible` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.text` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.is_visible` | `(self, selector)` | `util/browser.py` |  |
| `util.browser.PlaywrightSession.current_url` | `(self)` | `util/browser.py` |  |

（共 29 个，此处列出前 15 个）

### other — 其他

| 方法 | 签名 | 位置（文件） | 说明 |
|------|------|--------------|------|
| `start_demo.Handler.log_message` | `(self, fmt, *args)` | `start_demo.py` |  |

推荐入口（生成脚本时优先调用的那一层）：

| 类别 | 优先调用 |
|------|----------|
| 接口 | `（无，需自建并抽到该层）` |
| 页面 | `page.base_page.BasePage.open` |
| 数据库 | `（无，需自建并抽到该层）` |
| 命令行 | `（无，需自建并抽到该层）` |
| 工具 | `util.env.get_env` |

**复用判定**：出现下面这些裸调用，而本节有对应封装时，就是重复造轮子——必须改成调用封装：

- 接口：`requests.get/post/request(...)` 直连
- UI：`webdriver.Chrome()`、重复写 `page.click(...)` 而 PO 里已有对应方法
- DB：`pymysql.connect(...)` 直连
- CLI：`subprocess.run(...)` 裸调

## 8. 生成脚本时的硬性要求

1. **优先复用已有方法**：先查第 3 节的 fixture 与第 7 节的可复用清单，能调用就调用，禁止在用例里重写已有的请求/页面/数据库/命令封装。
2. 函数与文件命名严格遵循第 2 节的规则。
3. 断言遵循第 3/4 节风格，断言消息写清楚「期望 X，实际 Y」。
4. 环境相关值（URL、账号、DB 连接）一律从配置/环境变量读取，禁止硬编码。
5. 每个用例函数保留 docstring：用例编号 + 标题 + 前置条件 + 步骤 + 预期。

## 人工补充约定

<!-- 本节由人工维护，重新执行 learn_style.py 时会自动保留。请把团队口头约定、代码里看不出来的规范写在这里。 -->

- **工程定位**：纯浏览器（UI）自动化。`api/`、`db/`、`cli/` 为预留分层，当前无实现；新增对应类型用例时，先把实现抽到该层再供用例复用。
- **浏览器 fixture**：统一使用 `conftest.py` 的 `session`（函数级），禁止在用例内自行启动浏览器。§3 中 browser「未识别」为静态扫描局限，实际即 `session`。
- **双引擎**：`BROWSER_ENGINE=playwright|selenium` 切换；PO/用例层只调用 `util.browser.BrowserSession` 接口，禁止 import 具体框架。Playwright 使用本机 Chrome（channel="chrome"），无需下载 chromium。
- **日志规范**（skill 模板未覆盖，本工程约定）：
  - 统一 logging 标准库，入口 `util.logger.get_logger(<模块名>)`，logger 名 `autotest.<模块>`；
  - 级别由 `LOG_LEVEL` 环境变量控制，默认 INFO；
  - 格式 `[HH:MM:SS] [LEVEL] [logger] 消息`，控制台 + `reports/logs/autotest.log` 双输出；
  - 用例在关键步骤（打开页面/提交/断言点）记 INFO；PO 与封装层记 DEBUG；禁止以 print 代替日志（`start_demo.py` 启动横幅除外）。
- **配置层**：无独立 config 目录；配置统一经 `util.env.get_env()` 读取环境变量，默认值仅作本地兜底，生产值必须走环境变量。
- **测试数据**：小型数据经环境变量注入（如 `DEMO_USER`/`DEMO_PASSWORD`）；后期引入 data 目录时按 `<module>/<case>.json` 组织。
- **断言消息**：「期望 X / 实际 Y」格式必须保留。
- **UI 定位**：一律 A 档 `data-testid`（集中在 `locators/`）；D 级定位禁止提交（`locator_check.py` 必须清零）。
- **运行验收**：每次生成或修改用例后，执行 `verify_stability.py` 连跑 3 次，`FLAKY=0 且 BROKEN=0` 才允许合入。