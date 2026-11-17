# UI 元素定位规范（生成 UI 用例前必读）

## 1. 判定标准：什么算"最稳"

一个定位稳定，当且仅当同时满足：

1. **唯一**：在目标页面只命中 1 个元素（不是"碰巧第一个"）；
2. **语义锚定**：挂在"业务含义"上，而不是挂在"当前实现"上；
3. **抗变更**：改样式、改文案、调 DOM 层级后仍然命中。

一句话验证法：**问自己"前端改版一次它会挂吗"**。会挂就是不稳定。

## 2. 四档策略（从稳到脆）

| 档位 | 写法示例 | Playwright | Selenium | 何时用 |
|------|---------|-----------|----------|--------|
| A 契约属性（最稳） | `[data-testid="login-submit"]` | `page.get_by_test_id("login-submit")` | `By.CSS_SELECTOR, '[data-testid="login-submit"]'` | **首选**。需要前端配合加属性 |
| B 语义定位 | role + 可访问名 | `page.get_by_role("button", name="登录")` / `get_by_label("账号")` / `get_by_placeholder("请输入手机号")` | `By.NAME` / `By.ID`（静态 id）/ `By.CSS_SELECTOR, '[aria-label="搜索"]'` | 拿不到 testid 时的默认选择 |
| C 表现与文本 | `text=登录`、`.login-form button` | `page.get_by_text("登录")`、`page.locator(".login-form button")` | `By.LINK_TEXT` / `By.PARTIAL_LINK_TEXT` | 兜底。文案与样式会变，慎用于断言主流程 |
| D 结构定位（禁用） | `div:nth-child(3)`、`/html/body/div[2]`、坐标点击 | — | — | **禁止提交**。仅临时排查用 |

> 相对 XPath 轴（`//div[@class='x']/following-sibling::button`）算 C 档，比绝对 XPath 强，
> 但只要有 A/B 档可用就不要用。

## 3. 稳定性评分规则

`scripts/locator_check.py` 用这套规则自动打分，人工评审也照此标准：

| 特征 | 分值 |
|------|------|
| `data-testid` / `data-cy` / `data-test` / `get_by_test_id` | **+3** |
| `get_by_role` / `get_by_label` / `get_by_placeholder` / `aria-label` / 静态 `name=` / 非数字 `id=` | **+2** |
| 语义化 class（无 hash）+ 标签名 / `text=` / `has_text` | **+1** |
| 其他 CSS 选择器 | 0 |
| `:nth-child` / `:nth-of-type` / 三级以上 `>` 链 / `css-xxx` / `sc-xxx` / `data-v-xxxx` / 含随机数字的 id | **-1** |
| 绝对 XPath（`/html/`）/ 裸 `.nth(k)` / 坐标点击 | **-3** |

等级：`A ≥3`｜`B 1~2`｜`C 0`｜`D <0`。**D 级必须改掉才能进入连跑验收。**

## 4. 一眼识别"会变"的定位（黑名单）

看到这些特征直接判不稳定：

- 构建产物 class：`css-1a2b3c`、`sc-bdVaJa`、`jsx-123456`、`data-v-1f2e3d`
- 框架生成 id：`ember1234`、`id="input-7"`、`rc-tabs-0-panel-1`、UUID 形 id
- 结构依赖：`nth-child`、`nth-of-type`、`>` 链超过 3 层、`/html/body/...`
- 纯索引：`.nth(2)`、`.eq(1)`、坐标 `click(x=100, y=200)`
- 文案依赖：按钮文案、提示语（多语言/文案调整即失效）

## 5. 怎么获取最好：工具链与正确用法

### 5.1 拿 testid（收益最高的动作）

约定命名：`<模块>-<元素>-<动作>`，例如 `login-username-input`、`login-submit-btn`、`order-list-row`。
把它当**前后端契约**而不是测试私货：

1. 提需求时把 testid 清单写进验收项；
2. 在工程的 `locators/`（或 PO 层）集中维护，用例层不散写选择器；
3. 评审 PR 时禁止删除已登记 testid。

### 5.2 拿不到 testid 时：codegen 录制 → 人工改造（标准工作流）

Playwright codegen 是 UI 定位的**首选获取方式**（Selenium 无等价工具，Selenium 场景下用 Inspector/DevTools 拾取后套用同一套四档改造规则）。

```bash
# 录制（Python 安装 playwright 后自带 CLI，与 npx 版等价）
python -m playwright codegen http://localhost:5173 -o recorded_raw.py
npx playwright codegen http://localhost:5173 -o recorded_raw.py   # npm 版等价

# Inspector：逐元素拾取定位，适合只缺个别元素时补刀
npx playwright open --viewport-size=1280,720 <url>
```

**录制产物定位（必须遵守）**：

1. codegen 输出的是**操作草稿，不是定稿**。它偏好 `text=` 与 CSS 链，多为 C/D 档，
   **禁止原样合入用例层**；
2. 按本规范 §2 四档策略逐条改造（改造清单见下表），产出 A/B 档定位；
3. 每条定位做 §5.4 三步校验（唯一 / 抗变 / 语义）；
4. 最终收进工程的 `locators/`（常量）与 `page/`（方法），用例层只调 PO 方法，
   录制脚本本身不进版本库（或放 `recordings/` 临时目录并加 .gitignore）。

**codegen 输出 → 四档改造对照表**：

| codegen 典型输出 | 档位 | 改造为 |
|---|---|---|
| `page.get_by_text("登录")` | C | `page.get_by_role("button", name="登录")`（B）；有 testid 时 `get_by_test_id("login-submit-btn")`（A） |
| `page.locator("#app > div:nth-child(2) > button")` | D | 重取：testid / role / aria-label，禁止带 `nth-child` 提交 |
| `page.get_by_placeholder("请输入手机号")` | B | 保留（B 档），补唯一性验证 |
| `page.locator("input").first` | D | 换 `get_by_label("用户名")` 或 testid |
| `page.get_by_label("账号")` | B | 保留（B 档） |

**录制时的操作纪律**：

- 录制路径 = 用例主流程（如登录→进入首页），**不要在录制里走分支**，分支单独录；
- 被测页面有 data-testid 时，codegen 会自动生成 `get_by_test_id`，直接可用；
- 登录态录制用 `--save-storage=auth.json` 保存会话，回放时 `--load-storage=auth.json`，
  避免每个用例重录登录；
- 录制完立刻在页面控制台验证唯一性：`document.querySelectorAll('<selector>').length === 1`；
- Playwright 优先用 `get_by_role` / `get_by_label` / `get_by_placeholder`，
  它们天然要求"语义 + 可访问名唯一"，比 class 稳得多；可用 `locator.aria_snapshot()` 看语义树。

### 5.3 DevTools 的正确用法

Chrome 元素面板右键 → Copy → Copy selector / Copy XPath 只是**读结构的起点**，
产出多为 `#app > div:nth-child(2) > button`（D 档），**必须改造成 A/B 档**。

拿到候选后立刻在控制台验证唯一性：

```js
document.querySelectorAll('你的选择器').length   // 必须 === 1
```

Playwright 里等价断言：

```python
expect(page.get_by_test_id("login-submit")).to_have_count(1)
```

### 5.4 三步校验（每个定位都要过）

1. **唯一**：`count == 1`；
2. **抗变**：刷新、换测试数据、换视口（如 1280 / 375）各跑一次仍命中；
3. **语义**：不含第 4 节黑名单里的任何特征。

## 6. 定位对了还是会 flaky：等待策略

- **禁止用 `sleep` 掩盖**。等待用 `wait_for_selector(state="visible")` 或
  `expect(locator).to_be_visible()`；Playwright 的 `page.click()` 自带自动等待，不要再手动等。
- **等"业务就绪"而不是"元素出现"**：等 loading 遮罩消失、等表格行数 > 0、等特定文案出现。
- **iframe**：`page.frame_locator("iframe#main").locator(...)`；Selenium 需 `switch_to.frame`。
- **shadow DOM**：Playwright 的 CSS 可直接穿透（或 `>>>`），Selenium 需 `shadowRoot.querySelector`。
- **集合元素**：`locator.filter(has_text="xxx").first`，不要裸 `.nth(k)`。
- **超时**：统一 `page.set_default_timeout(30000)`，单点再按需加长。

## 7. 组织方式：定位只写一次

定位统一放在 PO / `locators.py`，用例层只调方法：

```python
class LoginPage:
    SUBMIT = "[data-testid='login-submit']"   # 定位集中在这里

    def __init__(self, page):
        self.page = page

    def submit(self):
        self.page.click(self.SUBMIT)
```

改版时只改 PO 一处，而不是翻几十个用例。

## 8. 写用例表时的约定（影响生成质量）

本 skill 的 UI 用例解析会把步骤里的 `点击@<元素>` / `输入@<元素>|<值>` 中的 `<元素>` 原样当选择器。
因此：

- **直接写稳定选择器**（推荐）：`点击@[data-testid="login-submit"]`、`输入@input[name="username"]|admin`；
- 写中文描述（`点击@登录按钮`）会被当作选择器生成，必然失效 —— 生成后必须按本规范人工替换，
  或先跑 `scripts/locator_check.py` 让它把这些标出来；
- 生成后必跑：

```bash
python <skill>/scripts/locator_check.py --files <生成的测试文件>
```

D 级清零后再做连跑 3 次验收。
