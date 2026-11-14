# 给接手开发的 Agent / 开发者

**规则：每一次修改都要同步更新 `DEVLOG.md`（中文）和 `DEVLOG.en.md`（英文），各在顶部追加一条、内容一致；架构有变化时更新本文件。** 动手前先读这三个文件。

> **For English-speaking agents:** this is Ledger Lens (流水分析助手), a Windows desktop app plus an Android app that imports
> bank statements, screenshots and payslips and analyses monthly income and spending offline. The full history, what was and
> was not verified, and the open issues are in [DEVLOG.en.md](DEVLOG.en.md). The rule above: every change gets a new entry at
> the top of **both** `DEVLOG.md` and `DEVLOG.en.md`, and this file is updated when the architecture changes. The project
> folder is `D:\LedgerLens`; the repository is `liliyawanttosleep/ledger-lens`. The conventions below are written in Chinese
> and are binding. Source-code UI strings and the category names stored in the database are Chinese by design.

## 这是什么

流水分析助手（Ledger Lens）：Windows 桌面程序 + 安卓 App。导入各家银行账单 / 截图 / 收入凭证，离线分析每月收支并给出建议。数据只存在本机。

## 架构一览

```
app/
  main.py          入口。pywebview 窗口 + Api 类（界面调用的全部接口）；--selftest / --selftest-sync 用于验证打包结果
  parsers.py       文件 → 交易。三条通路：表格(parse_grid) / 文本行(parse_text_lines) / OCR(parse_ocr_lines)
  categorize.py    关键词分类规则、内部转账关键词
  transfers.py     入库后的“智能识别”：内部转账、本人姓名、跨账户配对、路线记忆 / 疑似确认、退货配对、退款冲减、分类传播
  fx.py            货币：币种识别（逐笔）、符号、汇率（内置 + 联网更新缓存）、合并视图折算
  analysis.py      月度分析 + 建议引擎（输出给界面的唯一数据结构）
  i18n.py          后端文案模板（分类名、健康分、建议），5 种语言
  store.py         SQLite（%APPDATA%\LedgerAssistant\data.db），含字段迁移
  sync_server.py   局域网同步服务（配对码鉴权），同时给手机浏览器提供 web/mobile
  dev_server.py    仅开发用：浏览器里调试界面（?dev=1），不进安装包
  web/             电脑端界面：index.html / style.css / app.js / echarts.min.js
  web/mobile/      手机端界面（浏览器与安卓 App 共用）：index.html / m.css / m.js / i18n.js
android/           安卓 WebView 壳工程；构建时把 web/mobile 拷进 assets
samples/           脚本生成的虚构账单 + test_parse.py
assets/            图标与生成脚本
```

## 必须知道的约定

- **交易的 kind**：`income` 真实收入 / `expense` 真实消费 / `refund` 退款冲减支出（不算收入）/ `transfer` 不计收支。
  `transfer` 下的分类：`内部转账`（自己账户互转、信用卡还款、转入证券账户）和 `已退货`（买了又全额退）。
- **分类名在数据库里永远是中文键**（如 `餐饮美食`），显示时再翻译。不要把译文写进库。
- **界面源码里的文字一律写中文**。翻译在 `web/mobile/i18n.js`：渲染后由 MutationObserver 把页面上的中文替换成所选语言
  （`SUBS` 带数字的句式 + `DICT` 短语）。新增界面文字后要在 `DICT` 里补四列（en, fr, es, ko），否则非中文界面会漏出中文。
  用户数据（商户名、描述）放在 `.desc` 或 `data-raw` 元素里，不会被翻译。`<option>` 必须写明 `value`，否则翻译后取值会变。
- **建议文案**在 `app/i18n.py` 的 `ADV` 里按 key 分语言写，`analysis._advice` 只传 key 和参数。
- **`flow`（`in` / `out`）是资金方向**，kind 变成 `transfer` 后仍保留；**`pair_id`** 指向另一账户里配对上的那笔。
  `transfers.reclassify()` 每次导入后对全库重跑（新账单与历史账单核对），不要改成只处理新导入的记录。
- **每笔交易自带 `currency`**（解析时逐笔写明的币种放在 `cur`，否则用整份文件的币种）。统计默认按币种分开。
  “合并”是伪币种 `ALL`（`fx.ALL`），只存在于接口参数里，**永远不写进数据库**；合并时由 `main._txns("ALL")` 现算，
  折算后的记录带 `orig_amount / orig_currency`，编辑时必须用原币金额。汇率用“当前参考汇率”，不是交易当日汇率。
- **内部转账分两档**：高把握的在 `transfers.reclassify()` 里自动标；拿不准的只进 `transfers.suggestions()` 让用户确认，
  用户的决定存在设置项 `transfer_routes`（描述签名 → self / other）。不要把打分规则直接改成自动标记。
- **用户手动改过类型的交易会被锁定**（`locked=1`），`transfers.reclassify()` 不再改它。
- **隐私**：`samples/` 只能放虚构数据；真实账单、数据库、用户姓名不得进仓库。提交用 GitHub noreply 邮箱。
- 表结构变化要在 `store.init()` 里做 `ALTER TABLE` 迁移，不能假设是新库。

## 常用命令

```bat
.venv\Scripts\python app\main.py                 运行
.venv\Scripts\python samples\test_parse.py       解析回归（6 份样例）
.venv\Scripts\python app\dev_server.py           浏览器调试 http://127.0.0.1:8765/index.html?dev=1&lang=en&page=advice&noanim=1
build.bat                                        打包 dist\流水分析助手.exe
dist\流水分析助手.exe --selftest <文件...> <out.json>      验证打包后的解析
dist\流水分析助手.exe --selftest-sync <out.json>           验证打包后的同步服务
```

发布：推送后 `gh release create vX.Y.Z LedgerLens-windows.exe`。安卓 APK 由 `.github/workflows/android.yml` 构建并附到最新 Release。

## 已知问题 / 待办

见 `DEVLOG.md`（英文版 `DEVLOG.en.md`）最上面几条的“遗留”。
