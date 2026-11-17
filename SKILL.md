---
name: usecase-script-composer
description: 浏览器 UI 自动化测试工程脚手架与规范工具链。从零搭建 pytest + Playwright/Selenium 双引擎测试工程，把 playwright codegen 录制脚本按四档定位策略改造成 PO 结构，连跑稳定性验收并导出 Excel 结果。用于：新建浏览器自动化测试工程、codegen 录制脚本改造、用例连跑验收。
license: MIT
compatibility: opencode
metadata:
  audience: qa-engineers
  workflow: browser-ui-automation
  stack: pytest+playwright/selenium
---

# UseCase_Script_Composer — 浏览器 UI 自动化测试工程

## What I do

- 从零搭建分层清晰的浏览器 UI 自动化工程（用例层 / 页面层 / 定位层 / 工具层）
- 把 `playwright codegen` 录制产物按 A/B/C/D 四档定位策略改造成可维护的 PO 结构
- 对自动化用例做连跑稳定性验收（STABLE / FLAKY / BROKEN）并导出 Excel 报告

## When to use me

- 需要新建一个浏览器 UI 自动化测试工程，且本机没有既有工程可参照
- 已有 codegen 录制脚本，需要改造成工程化结构
- 需要对用例做「连跑 N 次」稳定性验收并输出结果报表

被测系统是真实项目、且已有现成测试工程时，先对既有工程跑 `scripts/learn_style.py`
归纳风格，再按归纳结果生成，不要直接套模板。

## Layout

```
assets/template_project/   # 已通过验收的工程模板（3 用例连跑 3 次全 STABLE，定位全 A 档）
scripts/                   # 工具链
references/                # 规范文档
```

## My workflow

1. 拆解用例为「步骤—方法」对照（显式步骤 / 隐含条件 / 预期结果）
2. 复制 `assets/template_project/` 为工程骨架，真实被测地址写入 `.env` 的 `BASE_URL`
3. `npx playwright codegen <被测地址>` 录制主流程
4. 按四档策略逐条改造定位（见 `references/locator_guide.md` §5.2），归档进 `locators/` 层
5. 按模板风格写 PO 与用例：文件 `test_{module}.py`、类 `Test{Module}`、函数 `test_{case_id}`
6. 实体机首跑通过 → 补断言 → `scripts/verify_stability.py --count 3` 连跑验收
7. `scripts/export_result_excel.py` 输出 Excel 结果

## 模板工程分层

| 层 | 位置 | 职责 |
|---|---|---|
| 用例层 | `testcases/` | 只写步骤与断言，不出现选择器 |
| 页面层 | `page/` | PO 封装，聚合页面操作 |
| 定位层 | `locators/` | 全部选择器集中管理，A/B/C/D 分级 |
| 工具层 | `util/` | 双引擎会话（browser.py）、环境变量（env.py）、日志（logger.py） |
| 被测样例 | `demo/` + `start_demo.py` | 内置 demo 登录应用（127.0.0.1:8765），开箱即跑 |

双引擎：`BROWSER_ENGINE=playwright|selenium`（默认 playwright），PO 与定位两引擎共用。

模板冒烟验证：

```bash
cd assets/template_project
pip install -r requirements.txt
playwright install chromium        # 仅首次
python start_demo.py &             # 启动 demo 被测应用
pytest testcases/test_login.py -v  # 期望 3 passed
```

## 硬性规范（违反即返工）

1. **Python 3.7 语法闸门**：禁 `:=`、f-string `=`、`match`、`list[str]` 内置泛型
2. **复用优先**：用例/页面层禁止裸调 webdriver / playwright API，必须走封装层
3. **配置入环境变量**：`BASE_URL`、`BROWSER_ENGINE`、`HEADLESS`、`LOGIN_USER`、`LOGIN_PASSWORD`、`LOG_LEVEL`，禁硬编码
4. **断言**：原生 `assert`，消息必须带「期望 X / 实际 Y」
5. **定位四档**，D 级清零才能连跑：
   - A 契约属性：`data-testid` / `data-test` / `data-qa`
   - B 语义：`role` / `label` / `placeholder` / `name`
   - C 文本：可见文本匹配
   - D 结构：nth-child、深层 class 链 —— **禁用**

## 工具脚本

| 脚本 | 用途 | 用法 |
|---|---|---|
| `scripts/locator_check.py` | 定位体检，输出 A/B/C/D 分级 | `python locator_check.py --files locators/login_locators.py` |
| `scripts/verify_stability.py` | 连跑 N 次验收，输出 JSON/Markdown 报告 | `python verify_stability.py --project <工程目录> --target testcases/test_login.py --count 3` |
| `scripts/export_result_excel.py` | 稳定性报告 JSON → Excel（在工程目录内运行） | `python export_result_excel.py` |
| `scripts/learn_style.py` | 归纳既有工程风格为 style_guide / style_config | `python learn_style.py --project <工程目录>` |

Windows 下运行 Python 脚本前置 `PYTHONUTF8=1`，避免控制台 GBK 编码报错。

## 验收标准

- 连跑 3 次：`FLAKY = 0 且 BROKEN = 0`（细节见 `references/verification.md`）
- 定位体检：无 D 级定位
- 全部文件过 Python 3.7 静态语法闸门
- 结果落盘：`reports/stability_result.xlsx`

## What I won't do

- 不在用例层写任何选择器或引擎 API
- 不为通过验收而降低断言强度（如把相等断言改成非空断言）
- 不引入模板技术栈之外的新框架（pytest / playwright / selenium / openpyxl 之外需先确认）
- 不用 `time.sleep` 代替显式等待
