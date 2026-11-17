# browser_autotest — 浏览器 UI 自动化测试工程

纯浏览器自动化测试骨架。Playwright / Selenium 双引擎，PO + locators 分层，
用例经连跑 3 次稳定性验收（FLAKY=0 且 BROKEN=0）后合入。

## 目录结构

```
browser_autotest/
├── conftest.py            # session 夹具（函数级浏览器会话）
├── pytest.ini             # pytest 配置
├── requirements.txt
├── .env.example           # 环境变量样例
├── start_demo.py          # 启动 demo 被测应用（127.0.0.1:8765）
├── export_result_excel.py # 连跑结果导出 Excel
├── demo/                  # 本地被测样例应用（login.html / dashboard.html）
├── testcases/             # 用例层：test_{module}.py / Test{Module} / test_{case_id}
├── page/                  # PO 层：业务动作封装，不暴露选择器
├── locators/              # 定位层：A 档 data-testid 常量，集中维护
├── api/  db/  cli/        # 预留分层（当前无实现）
├── util/
│   ├── browser.py         # 双引擎统一封装（BrowserSession 接口）
│   ├── env.py             # 环境变量集中读取（禁止硬编码）
│   └── logger.py          # 日志规范实现
└── reports/               # 验收产物（xlsx / logs/）
```

## 快速开始

```bash
pip install -r requirements.txt          # 建议 Python 3.11（脚本兼容 3.7 语法）
python start_demo.py                     # 终端1：启动 demo 被测应用
pytest -v                                # 终端2：运行用例（默认 Playwright）
```

切换 Selenium 引擎（Windows cmd 下分两行写，`set X=Y && ...` 会把尾随空格写进变量值）：

```bat
set BROWSER_ENGINE=selenium
pytest -v
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `BASE_URL` | `http://127.0.0.1:8765` | 被测系统地址 |
| `BROWSER_ENGINE` | `playwright` | `playwright` 或 `selenium` |
| `HEADLESS` | `true` | 无头模式 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DEMO_USER` / `DEMO_PASSWORD` | `admin` / `123456` | 演示账号（断言期望值） |
| `DEFAULT_TIMEOUT_MS` | `10000` | 元素级超时 |

## 规范要点

- 命名：文件 `test_{module}.py`，类 `Test{Module}`，函数 `test_{case_id}`；
- 断言：原生 assert，消息格式「期望 X / 实际 Y」；
- 定位：只用 A 档 `data-testid`，集中在 `locators/`；D 级（nth-child/绝对 XPath）禁止提交；
- 配置：一律 `util.env.get_env()`，禁止硬编码 URL/账号；
- 日志：`util.logger.get_logger(<模块>)`，关键步骤 INFO；
- 复用：浏览器会话只用 `conftest.session` 夹具；PO 方法优先复用；
- 验收：连跑 3 次全 STABLE 才算通过（`verify_stability.py`），结果导出 `reports/stability_result.xlsx`。

## 接入真实被测系统

1. 把 `BASE_URL` 指向真实系统；
2. 用 `python -m playwright codegen <url> -o recorded_raw.py` 录制主流程；
3. 按四档策略把录制产物改造成 A/B 档定位，收进 `locators/`；
4. 新增 PO 方法与用例，连跑 3 次验收。

完整规范见 `../../references/`：定位策略（locator_guide.md）、风格规范（style_guide.md）、
验收规则（verification.md）。
