# 开发日志

新的记录写在最上面。每条包含：做了什么、为什么、涉及文件、怎么验证的、遗留问题。

---

## 2026-11-13 · v1.1.0 — 智能识别强化、退货不计消费、五种语言

**做了什么**

1. **退货 / 退款不再算消费或收入**（`transfers.py::_refunds`，`analysis.py`）
   - 同一账户里找得到“金额相同、同一商户、120 天内”的原消费 → 原消费和退款都标为 `transfer / 已退货`，不计收支。
   - 找不到原消费的退款、返现（cashback、statement credit、fee waived）→ 新的 `kind=refund`，冲减所属分类的支出，不算收入。
   - 报销、退税仍是收入。信用卡账单上的入账默认按退款处理。
2. **内部转账识别强化**（`transfers.py`）
   - 本人判断扩展：`REAL TIME PAYMENT TO/FROM <本人>`；Zelle 联系人昵称“名 + 银行”（如 `Alex Chase`）。
   - 新规则 `is_bank_move`：对手方是银行 / 券商的电子转入转出（`ELECTRONIC DEPOSIT JPMorgan Chase`、`WEB AUTHORIZED PMT FID BKG SVC`）视为自己账户间的资金往来。
   - 概览页新增“不计入收支”条：内部转账 / 已退货 / 退款冲减的笔数和金额，点击可逐笔核对。
3. **工资识别**（`transfers.py::_propagate`）：同一付款方在别的账户已有明确分类（如 BoA 上带 `SALARY` 的记录）时，把其他账户里同一付款方的“其他 / 转账收入”也归过去。US Bank 上的 `ELECTRONIC DEPOSIT <雇主>` 因此被认成工资。概览收入卡片显示“其中工资”。
4. **五种语言**：中文、English、Français、Español、한국어。电脑端侧栏底部、手机端“同步”页切换。
   - 界面：`web/mobile/i18n.js`（渲染后替换）；后端建议 / 健康分：`app/i18n.py`。
   - `analysis.analyze(..., lang)`；`/api/sync?lang=`；设置项 `lang`。
5. **其他**：支持 `.qbo`；同一份流水的 CSV 与 QBO 重复导入会被模糊去重（同账户、同日、同金额、描述开头相同）；文件名里的卡号后四位识别放宽（`Checking - 4563_...`）；去掉 `Download from usbank.com` 之类的备注噪声。
6. 建立 `AGENTS.md` 和本日志。

**为什么**：用户用真实的 BoA / Chase / US Bank 账单测试，自己账户之间的转账、转入证券账户、退货退款都被算进了收入和支出，工资在部分银行被归为“转账收入”。

**涉及文件**：`app/transfers.py` `app/analysis.py`（重写）`app/i18n.py`（新）`app/web/mobile/i18n.js`（新）`app/main.py` `app/parsers.py` `app/categorize.py` `app/sync_server.py` `app/store.py` `app/web/app.js` `app/web/index.html` `app/web/style.css` `app/web/mobile/m.js` `app/web/mobile/index.html`

**验证**
- 用三家银行共 9 个真实文件在临时库里端到端导入：收入只剩工资、利息、朋友的 Zelle、一笔航空公司付款；支出里不再有自转。CSV + QBO 同时导入时 QBO 的 83 笔全部判为重复。
- `samples/test_parse.py` 6 份样例无回归。
- 调试服务下逐页扫描英文界面的残留中文：只剩用户数据；韩语（手机同步页）、法语（导入弹窗）抽查正常。
- **没有验证**：西班牙语界面未逐页看；手机端在真机上的多语言显示；翻译由我直接撰写，没有母语者校对。

**遗留**
- 安卓 APK 仍未构建：推送 `.github/workflows/android.yml` 需要 `workflow` 权限，等用户执行 `gh auth refresh -h github.com -s workflow`。该提交在本地 `main` 上领先远端一个。安卓工程从未编译过。
- 跨账户配对（规则 3b）在真实数据上还没有单独命中过。
- 朋友之间的 Zelle 入账目前算“转账收入”，是否应视为分摊 / 还款由用户手动改。
- 导出 Excel 的表头仍是中文。

---

## 2026-11-12 · v1.0.2 — 内部转账识别

- 新增 `app/transfers.py`：关键词 + 本人姓名（自动从 `INDN:<姓名>` 学习，可在“导入与数据”修改）+ 跨账户配对。导入后和启动时自动运行。
- 信用卡还款两侧（`PAYMENT FROM CHK` / `Mobile Banking payment to CRD`）、`Ext Trnsfr`、`ACH transfer to <本人>`、自己给自己的 Zelle 均标为内部转账。
- 信用卡账单的识别：出现“收到还款”字样即判为信用卡；账户名从文件名 / 所在文件夹推断（`boa` → Bank of America）；卡号后四位从文件名取。
- 手动改过类型的交易加锁（`locked`）。
- 验证：BoA 5 个文件 + Chase 2 个 PDF，78 笔内部转账全部识别，朋友 Zelle、工资、房租不受影响。

## 2026-11-12 · v1.0.1 — Chase 信用卡账单修复

- 问题：首页“日历数字 + 还款日 + 积分说明”一行被当成一笔 3.5 美元的交易（日期还在未来）；`PURCHASE`（单数）小标题不认识，导致消费被标成收入。
- 修复（`parsers.py`）：积分 / 利率 / 日历说明行整行跳过；金额后跟 `Pts` / `points` 不算钱；认识单数 `PURCHASE`、fees、interest、cash advances 段落；晚于当天的交易不收；描述里去掉商户电话。
- 验证：两份真实 Chase 账单分别识别为 8 笔消费 + 3 笔还款、5 笔消费 + 5 笔还款，与账单一致。

## 2026-11-12 · v1.0.0 — 首个版本

- 解析：PDF（文本 / 表格 / 扫描件 OCR）、截图（RapidOCR 离线）、CSV、Excel、Word、HTML、OFX；收入凭证（工资条）单独处理。
- 分析：KPI、分类环形图、12 个月趋势、环比 / 近 3 月均值、每日与星期分布、商户与账户、健康评分、建议、建议预算、固定扣费。
- 界面：pywebview + ECharts，浅色 / 深色；导入前预览可编辑、重复检测、分类学习。
- 分类明细钻取：点分类 / 商户 / 账户看每一笔的日期、商家、银行、卡片；卡片来自“支付方式”列或卡号后四位。
- 手机同步：局域网服务（默认关闭，8 位配对码，输错锁定）、手机网页版、安卓 WebView 壳工程。
- 打包：PyInstaller 单文件 exe（约 130 MB）；图标为“水滴里的环形图”。
- 发布到 GitHub（公开），提交使用 noreply 邮箱，样例均为虚构数据。
