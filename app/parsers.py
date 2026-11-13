# -*- coding: utf-8 -*-
"""文件解析：把 PDF / 图片截图 / Excel / CSV / Word / OFX 等统一解析为交易列表。

三条通路：
  1. 表格通路  —— 有表头的结构化数据（CSV、Excel、PDF 中的表格）
  2. 文本行通路 —— 每行含“日期 + 金额”的文本（多数银行 PDF 对账单）
  3. OCR 通路   —— 截图 / 扫描件，先文字识别再按版面还原行
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import zipfile
from collections import Counter
from html.parser import HTMLParser

from categorize import is_transfer, looks_like_income

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff", ".jfif"}
SUPPORTED_EXT = IMAGE_EXT | {".pdf", ".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".docx",
                             ".html", ".htm", ".ofx", ".qfx"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = (r"(?<![a-z])(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?![a-z])\.?")

# (正则, 解析函数) —— 顺序即优先级
_DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(20\d{2})\s?[-/.年]\s?(\d{1,2})\s?[-/.月]\s?(\d{1,2})日?"),
     lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"),
     lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(20\d{2}|\d{2})(?![\d/])"),
     lambda m: (int(m[3]) + (2000 if len(m[3]) == 2 else 0), int(m[1]), int(m[2]))),
    (re.compile(_MON + r"\s*(\d{1,2})(?:(?:st|nd|rd|th)?,?\s*(20\d{2}))?(?!\d)", re.I),
     lambda m: (int(m[3]) if m[3] else None, MONTHS[m[1].lower()[:3]], int(m[2]))),
    (re.compile(r"(?<!\d)(\d{1,2})\s*[- ]?" + _MON + r"(?:[- ,]*(20\d{2}))?", re.I),
     lambda m: (int(m[3]) if m[3] else None, MONTHS[m[2].lower()[:3]], int(m[1]))),
    (re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日?"),
     lambda m: (None, int(m[1]), int(m[2]))),
]
# 无年份的 MM/DD、MM-DD：只在行首或紧跟另一个日期时才承认
_SHORT_DATE = re.compile(r"(?<![\d.])(\d{1,2})[/-](\d{1,2})(?![\d/.\-])")
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:：][0-5]\d(?:[:：][0-5]\d)?(?!\d)\s*(?:[ap]m\b)?", re.I)

_AMOUNT = re.compile(
    r"(?P<paren>\()?\s*(?P<s1>[-+−–﹣－＋])?\s*(?P<cur>[¥￥$€£]|RMB|CNY|USD|HKD)?\s*(?P<s2>[-+−–﹣－＋])?\s*"
    r"(?<![\d.,:/])(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\d:/%]|\.\d|,\d|\s*(?:pts\b|points?\b|笔|次|天|个月))"
    r"(?P<post>-(?=\s|$)|\s*(?:\)|CR\b|DR\b|元))?", re.I)

_SKIP_LINE = re.compile(
    r"beginning balance|ending balance|opening balance|closing balance|previous balance|new balance|"
    r"payment due|minimum payment|statement period|credit limit|available credit|total fees|"
    r"total interest|year-to-date|期初余额|期末余额|上期余额|承前|结转|合计|总计|小计|账单周期|本期应还|"
    r"最低还款|信用额度|可用额度|到期还款日|\bpts\b|\bpoints?\b|addl on|annual percentage|\bapr\b|"
    r"interest rate|rewards? (?:summary|balance)|积分|年利率", re.I)
_SEC_INCOME = re.compile(
    r"deposits|additions|other credits|payments and credits|credits\b|money in|存入|收入明细|入账明细", re.I)
_SEC_EXPENSE = re.compile(
    r"withdrawals|subtractions|purchases?\b|debits\b|fees\b|fees charged|interest charged?|cash advances?|"
    r"balance transfers?|checks paid|charges|money out|支出明细|"
    r"消费明细", re.I)
_CREDIT_CARD = re.compile(
    r"信用卡对账单|信用卡账单|信用卡电子账单|贷记卡|最低还款|本期应还|信用额度|minimum payment|credit limit|"
    r"new balance|credit line|cardmember|card member", re.I)
_PAYSLIP = re.compile(r"实发|工资条|工资单|薪资单|\bnet pay|pay stub|paystub|earnings statement", re.I)
_PAY_KEYS = ["实发工资", "实发金额", "实发合计", "实发薪资", "实发", "net pay", "net amount", "take home",
             "到账金额", "入账金额", "收款金额", "转账金额", "交易金额", "金额", "amount", "total"]

ACCOUNTS = [
    ("微信支付", ["微信", "wechat", "财付通"]), ("支付宝", ["支付宝", "alipay"]),
    ("招商银行", ["招商银行", "招行", "cmb"]), ("工商银行", ["工商银行", "工行", "icbc"]),
    ("建设银行", ["建设银行", "建行", "ccb"]), ("农业银行", ["农业银行", "农行"]),
    ("中国银行", ["中国银行", "中行"]), ("交通银行", ["交通银行", "交行"]),
    ("邮储银行", ["邮政储蓄", "邮储"]), ("中信银行", ["中信银行"]), ("光大银行", ["光大银行"]),
    ("民生银行", ["民生银行"]), ("浦发银行", ["浦发", "浦东发展"]), ("兴业银行", ["兴业银行"]),
    ("平安银行", ["平安银行"]), ("广发银行", ["广发银行"]), ("华夏银行", ["华夏银行"]),
    ("Chase", ["chase", "jpmorgan"]), ("Bank of America", ["bank of america", "bofa"]),
    ("Wells Fargo", ["wells fargo"]), ("Citi", ["citibank", "citi "]),
    ("Capital One", ["capital one"]), ("Discover", ["discover"]),
    ("American Express", ["american express", "amex"]), ("PNC", ["pnc bank", "pnc "]),
    ("US Bank", ["u.s. bank", "us bank"]), ("TD Bank", ["td bank"]), ("Apple Card", ["apple card"]),
    ("PayPal", ["paypal"]), ("Venmo", ["venmo"]),
]


# ----------------------------------------------------------------------------
# 基础：日期 / 金额
# ----------------------------------------------------------------------------
def _valid(y, m, d):
    try:
        dt.date(y or 2024, m, d)
        return 1 <= m <= 12
    except ValueError:
        return False


def find_dates(line: str):
    """返回 [(start, end, y|None, m, d)]，按出现位置排序、互不重叠。"""
    found = []
    for rx, fn in _DATE_PATTERNS:
        for m in rx.finditer(line):
            try:
                y, mo, d = fn(m)
            except (ValueError, KeyError):
                continue
            if not _valid(y, mo, d):
                continue
            if any(m.start() < e and m.end() > s for s, e, *_ in found):
                continue
            found.append((m.start(), m.end(), y, mo, d))
    found.sort()
    # 短日期：行首（前面只有少量字符）或紧跟在已识别日期后
    for m in _SHORT_DATE.finditer(line):
        if any(m.start() < e and m.end() > s for s, e, *_ in found):
            continue
        mo, d = int(m[1]), int(m[2])
        if not _valid(None, mo, d):
            continue
        prev_end = max([e for s, e, *_ in found if e <= m.start()], default=None)
        at_start = len(line[:m.start()].strip()) <= 2
        after_date = prev_end is not None and not line[prev_end:m.start()].strip()
        if at_start or after_date:
            found.append((m.start(), m.end(), None, mo, d))
            found.sort()
    return found


def find_amounts(text: str):
    """返回 [(value>0, sign(-1/0/+1), start, end)]。没有小数的数字必须带货币符号或正负号。"""
    out = []
    for m in _AMOUNT.finditer(text):
        num = m["num"]
        sign_ch = m["s1"] or m["s2"]
        has_dec = "." in num
        post = (m["post"] or "").strip().upper()
        if not has_dec and not (m["cur"] or sign_ch or post == "元"):
            continue
        if not has_dec and sign_ch and not m["cur"]:
            before = text[:m.start()]
            if before and not before[-1].isspace():
                continue  # 形如 “尾号-1234”
        try:
            val = float(num.replace(",", ""))
        except ValueError:
            continue
        if val == 0 or val > 1e9:
            continue
        sign = 0
        if sign_ch:
            sign = 1 if sign_ch in "+＋" else -1
        if m["paren"] and post == ")":
            sign = -1
        elif post == "-":
            sign = -1
        elif post == "CR":
            sign = 1
        elif post == "DR":
            sign = -1
        out.append((val, sign, m.start(), m.end()))
    return out


def parse_number(cell):
    """把单元格解析为带符号数字；失败返回 None。"""
    if cell is None:
        return None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell)
    s = str(cell).strip()
    if not s or s in "-—/":
        return None
    neg = s.startswith("(") and s.endswith(")")
    s2 = re.sub(r"[¥￥$€£,\s元()]|RMB|CNY|USD", "", s, flags=re.I)
    s2 = s2.replace("−", "-").replace("–", "-").replace("－", "-").replace("＋", "+")
    if s2.endswith("-"):
        s2 = "-" + s2[:-1]
    m = re.fullmatch(r"([-+]?)(\d+(?:\.\d+)?)(cr|dr)?", s2, re.I)
    if not m:
        return None
    v = float(m[2])
    if m[1] == "-" or neg or (m[3] or "").lower() == "dr":
        v = -v
    return v


def parse_date_cell(cell, ctx):
    if cell is None:
        return None
    if isinstance(cell, dt.datetime):
        return cell.date()
    if isinstance(cell, dt.date):
        return cell
    if isinstance(cell, (int, float)) and 30000 < cell < 60000:  # Excel 序列日期
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(cell))
    s = str(cell).strip()
    ds = find_dates(s)
    if not ds:
        return None
    return ctx.resolve(ds[0])


class Ctx:
    """解析上下文：年份推断、文件信息。"""

    def __init__(self, path: str, text: str = ""):
        self.path = path
        try:
            self.mtime = dt.date.fromtimestamp(os.path.getmtime(path))
        except OSError:
            self.mtime = dt.date.today()
        self.set_text(text)

    def set_text(self, text: str):
        self.text = text or ""
        full = []
        for line in self.text.splitlines():
            for s, e, y, m, d in find_dates(line):
                if y and 2000 <= y <= dt.date.today().year + 1:
                    try:
                        full.append(dt.date(y, m, d))
                    except ValueError:
                        pass
        ym = re.findall(r"(20[12]\d)\s?年", self.text)
        if full:
            self.ref = min(max(full), dt.date.today())
        elif ym:
            y = int(Counter(ym).most_common(1)[0][0])
            self.ref = min(dt.date(y, 12, 31), dt.date.today())
        else:
            self.ref = min(self.mtime, dt.date.today())

    def resolve(self, d):
        _, _, y, m, day = d
        if y is None:
            y = self.ref.year
            try:
                cand = dt.date(y, m, day)
            except ValueError:
                return None
            if cand > self.ref + dt.timedelta(days=10):
                try:
                    cand = dt.date(y - 1, m, day)
                except ValueError:
                    return None
            return cand
        try:
            return dt.date(y, m, day)
        except ValueError:
            return None


def guess_account(text: str, filename: str) -> str:
    name = filename.lower()
    for acc, keys in ACCOUNTS:
        if any(k in name for k in keys):
            return acc
    head = text[:3000].lower()
    best = None
    for acc, keys in ACCOUNTS:
        for k in keys:
            i = head.find(k)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, acc)
    return best[1] if best else os.path.splitext(filename)[0][:20]


def guess_currency(text: str) -> str:
    t = text[:20000]
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
    if "HK$" in t or "HKD" in t:
        return "HKD"
    if "€" in t or "EUR" in t:
        return "EUR"
    if "£" in t or "GBP" in t:
        return "GBP"
    usd = t.count("$") + t.count("USD") * 2
    cny = t.count("¥") + t.count("￥") + t.count("CNY") * 2 + t.count("人民币") * 2 + t.count("元")
    if usd > cny and cjk < 200:
        return "USD"
    if cny or cjk >= 20:
        return "CNY"
    return "USD" if re.search(r"[A-Za-z]{4,}", t) else "CNY"


def _card_label(v) -> str:
    """把“支付方式 / 卡号”单元格整理成简短的卡片名：长卡号只保留后四位。"""
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    if not s or s in ("/", "-", "None"):
        return ""
    digits = re.sub(r"[\s\-*xX•]", "", s)
    if digits.isdigit() and len(digits) >= 8:
        return "尾号" + digits[-4:]
    m = re.fullmatch(r"[*xX•\s\-]+(\d{4})", s)
    if m:
        return "尾号" + m[1]
    return s[:24]


_CARD_PATTERNS = [
    re.compile(r"尾号\s*[:：]?\s*(\d{4})(?!\d)"),
    re.compile(r"(?:卡号|账号|账户|card(?:\s*(?:number|no\.?))?|account(?:\s*(?:number|no\.?))?|ending in)"
               r"\s*[:：#]?\s*[\d*xX•\-\s]{0,24}?(\d{4})(?![\d.,])", re.I),
    re.compile(r"(?<![\dA-Za-z])[*•]{2,}[\s\-]?(\d{4})(?!\d)"),  # 前面是数字的多半是手机号掩码
]


def guess_card(text: str, filename: str, credit_card: bool) -> str:
    """从文件名或账单抬头里找卡号后四位，例如“尾号1234”。找不到返回空串。"""
    for src in (filename, text[:2500]):
        for rx in _CARD_PATTERNS:
            m = rx.search(src)
            if m:
                return ("信用卡" if credit_card else "") + "尾号" + m[1]
    return "信用卡" if credit_card else ""


def _clean_desc(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "")
    s = s.strip(" \t-—_|,;:：，。.*/\\")
    return s[:90]


def _mk(date, amount, kind, desc):
    return {"date": date.isoformat(), "amount": round(abs(amount), 2), "kind": kind,
            "desc": _clean_desc(desc) or "(无描述)", "card": ""}


def _finalize_kind(sign: int, desc: str) -> str:
    if is_transfer(desc):
        return "transfer"
    return "income" if sign > 0 else "expense"


# ----------------------------------------------------------------------------
# 通路 1：表格
# ----------------------------------------------------------------------------
def _norm_header(h) -> str:
    s = str(h if h is not None else "").lower()
    s = re.sub(r"[（(\[【].*?[)）\]】]", "", s)
    return re.sub(r"[\s_\-:：*.]", "", s)


def _classify_header(h: str):
    if not h or len(h) > 24:
        return None
    if "余额" in h or "balance" in h or h.startswith("runningbal"):
        return "balance"
    if h in ("收/支", "收支", "收支类型", "借贷", "借贷标志", "借贷标识", "借贷方向", "资金流向", "dr/cr",
             "details", "收付标志", "交易方向"):
        return "dir"
    if any(k in h for k in ("支出", "借方", "取出", "转出", "debit", "withdraw", "moneyout", "paidout")):
        return "out"
    if any(k in h for k in ("收入", "贷方", "存入", "转入", "credit", "deposit", "moneyin", "paidin")):
        return "in"
    if any(k in h for k in ("金额", "发生额", "amount", "交易额")):
        return "amount"
    if any(k in h for k in ("日期", "时间", "date", "交易日", "记账日")):
        return "date"
    if any(k in h for k in ("付款方式", "支付方式", "交易卡号", "卡号", "账号后四位", "cardno", "cardnumber",
                            "paymentmethod", "accountname")) and "对方" not in h and "对手" not in h:
        return "method"
    if "号" in h or "account" in h or "number" in h or h.endswith("id") or "reference" in h:
        return None
    if any(k in h for k in ("对方", "对手", "收款人", "付款人", "商户", "payee", "merchant", "counterparty")):
        return "party"
    if any(k in h for k in ("摘要", "说明", "商品", "描述", "备注", "附言", "用途", "description", "memo",
                            "name", "交易类型", "交易分类", "category", "type", "交易地点", "narrative",
                            "particulars", "交易场所", "交易渠道")):
        return "desc"
    if "状态" in h or "status" in h:
        return "status"
    if "币种" in h or "currency" in h:
        return "currency"
    return None


def _detect_header(row):
    """返回列映射 {field: [col_index...]}；不是表头返回 None。"""
    mapping = {}
    for i, cell in enumerate(row):
        f = _classify_header(_norm_header(cell))
        if f:
            mapping.setdefault(f, []).append(i)
    if "date" in mapping and ("amount" in mapping or "in" in mapping or "out" in mapping):
        return mapping
    return None


def _cell(row, idx):
    return row[idx] if idx is not None and idx < len(row) else None


def parse_grid(rows, ctx, forced_mapping=None):
    """解析一个二维表。返回 (txns, mapping, currency|None)。"""
    mapping, start = forced_mapping, 0
    if mapping is None:
        for i, row in enumerate(rows[:60]):
            mapping = _detect_header(row)
            if mapping:
                start = i + 1
                break
    if not mapping:
        return [], None, None

    # 交易日期优先于记账日期
    date_cols = mapping["date"]
    hdr = rows[start - 1] if start else []
    pref = [c for c in date_cols if any(k in _norm_header(_cell(hdr, c)) for k in ("交易", "trans"))]
    date_col = (pref or date_cols)[0]
    amt_col = mapping.get("amount", [None])[0]
    in_col = mapping.get("in", [None])[0]
    out_col = mapping.get("out", [None])[0]
    dir_col = mapping.get("dir", [None])[0]
    st_col = mapping.get("status", [None])[0]
    cur_col = mapping.get("currency", [None])[0]
    method_col = mapping.get("method", [None])[0]
    text_cols = mapping.get("party", []) + mapping.get("desc", [])

    staged, currency = [], None
    for row in rows[start:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        date = parse_date_cell(_cell(row, date_col), ctx)
        if not date:
            continue
        status = str(_cell(row, st_col) or "")
        if re.search(r"关闭|失败|撤销|已取消|cancel|declin|void", status, re.I):
            continue
        parts = []
        for c in text_cols:
            v = str(_cell(row, c) or "").replace("\n", " ").strip()
            if v and v not in ("/", "-", "None") and v not in parts:
                parts.append(v)
        desc = " · ".join(parts)
        if cur_col is not None and currency is None:
            cv = str(_cell(row, cur_col) or "")
            if re.search(r"美元|usd", cv, re.I):
                currency = "USD"
            elif re.search(r"人民币|cny|rmb", cv, re.I):
                currency = "CNY"

        sign, amount, neutral = 0, None, False
        vin, vout = parse_number(_cell(row, in_col)), parse_number(_cell(row, out_col))
        if vout:
            amount, sign = abs(vout), -1
        elif vin:
            amount, sign = abs(vin), 1
        elif amt_col is not None:
            v = parse_number(_cell(row, amt_col))
            if v is None or v == 0:
                continue
            amount = abs(v)
            signed = -1 if v < 0 else 0
            dv = str(_cell(row, dir_col) or "").strip().lower() if dir_col is not None else ""
            if dv:
                if re.search(r"^(收|贷|入)|收入|credit|^cr|^in|dslip|deposit", dv):
                    sign = 1
                elif re.search(r"^(支|借|出|付)|支出|debit|^dr|^out|check", dv):
                    sign = -1
                else:
                    neutral = True
            staged.append([date, amount, sign, desc, neutral, signed, v, _card_label(_cell(row, method_col))])
            continue
        else:
            continue
        staged.append([date, amount, sign, desc, neutral, 0, None, _card_label(_cell(row, method_col))])

    # 单金额列且无方向列：根据正负号含义判断
    undecided = [s for s in staged if s[2] == 0 and not s[4] and s[6] is not None]
    if undecided:
        has_neg = any(s[6] < 0 for s in undecided)
        pos_share = sum(1 for s in undecided if s[6] > 0) / len(undecided)
        card_style = has_neg and pos_share > 0.6 and any(
            s[6] < 0 and is_transfer(s[3]) for s in undecided)
        for s in undecided:
            if has_neg:
                s[2] = (1 if s[6] < 0 else -1) if card_style else (-1 if s[6] < 0 else 1)
            else:
                s[2] = 1 if looks_like_income(s[3]) else -1

    txns = []
    for date, amount, sign, desc, neutral, _, _, card in staged:
        kind = "transfer" if neutral else _finalize_kind(sign, desc)
        t = _mk(date, amount, kind, desc)
        t["card"] = card
        txns.append(t)
    return txns, mapping, currency


def parse_grids(grids, ctx):
    txns, last_map, currency = [], None, None
    for g in grids:
        if not g:
            continue
        t, m, cur = parse_grid(g, ctx)
        if not m and last_map and max(len(r) for r in g) == last_map["_width"]:
            t, m, cur = parse_grid(g, ctx, forced_mapping=last_map)
        if m:
            m["_width"] = max(len(r) for r in g)
            last_map = m
        txns += t
        currency = currency or cur
    return txns, currency


# ----------------------------------------------------------------------------
# 通路 2：文本行
# ----------------------------------------------------------------------------
_BAL_INLINE = re.compile(r"(余额|balance)\s*[:：]?\s*[¥￥$]?\s*[\d,]+\.\d{2}", re.I)


def _strip_spans(line, spans):
    out, last = [], 0
    for s, e in sorted(spans):
        out.append(line[last:s])
        last = max(last, e)
    out.append(line[last:])
    return " ".join(out)


def _split_line(line, ctx, allow_date_anywhere=False):
    """拆出 (date|None, amounts, desc)。"""
    dates = find_dates(line)
    date = None
    spans = []
    prefix = line[:dates[0][0]].strip() if dates else ""
    if dates and (allow_date_anywhere or (len(prefix) <= 26 and not re.fullmatch(r"(?:\d{1,2}\s+){2,}\d{1,2}", prefix))):
        date = ctx.resolve(dates[0])
        spans = [(s, e) for s, e, *_ in dates]
    rest = _strip_spans(line, spans) if spans else line
    rest = _TIME.sub(" ", rest)
    amts = find_amounts(rest)
    desc = _strip_spans(rest, [(s, e) for _, _, s, e in amts])
    desc = re.sub(r"[¥￥$€£()]|\b(CNY|RMB|USD|CR|DR)\b", " ", desc)
    desc = re.sub(r"\b(?:(?:recurring )?card purchase(?: with pin)?|card \d{4}|(?:ppd|web|ccd) id:?)",
                  " ", desc, flags=re.I)
    desc = re.sub(r"(?<![A-Za-z])\d{6,}(?![A-Za-z])", " ", desc)  # 流水号、卡号
    desc = re.sub(r"(?<![\d/])\d{1,2}/\d{1,2}(?![\d/])", " ", desc)  # 残留的记账日期
    desc = re.sub(r"(?<!\d)\d{3}-\d{3}-\d{4}(?!\d)", " ", desc)  # 商户电话
    return date, amts, _clean_desc(desc)


def parse_text_lines(lines, ctx, credit_card=False):
    rows, section = [], 0
    for raw in lines:
        line = (raw or "").strip()
        if len(line) < 6:
            continue
        date, amts, desc = _split_line(line, ctx)
        if date is None or not amts:
            if len(line) < 70 and not amts:
                if _SEC_INCOME.search(line):
                    section = 1
                elif _SEC_EXPENSE.search(line):
                    section = -1
            continue
        if _SKIP_LINE.search(line):
            continue
        amt = amts[0]
        bal = amts[-1][0] if len(amts) >= 2 else None
        rows.append({"date": date, "amt": amt[0], "sign": amt[1], "bal": bal,
                     "section": section, "desc": desc})

    # 用余额变化反推收支方向（最可靠）
    def model(step):
        hits = {}
        for i, r in enumerate(rows):
            j = i + step
            if 0 <= j < len(rows) and r["bal"] is not None and rows[j]["bal"] is not None:
                d = r["bal"] - rows[j]["bal"]
                if abs(abs(d) - r["amt"]) < 0.011:
                    hits[i] = 1 if d > 0 else -1
        return hits

    asc, desc_m = model(-1), model(1)
    by_bal = asc if len(asc) >= len(desc_m) else desc_m
    if len(by_bal) < max(2, len(rows) * 0.3):
        by_bal = {}

    txns = []
    for i, r in enumerate(rows):
        if credit_card:
            sign = 1 if r["sign"] < 0 else -1
            if r["section"] == 1 and r["sign"] == 0:
                sign = 1
        elif i in by_bal:
            sign = by_bal[i]
        elif r["sign"]:
            sign = r["sign"]
        elif r["section"]:
            sign = r["section"]
        else:
            sign = 1 if looks_like_income(r["desc"]) else -1
        txns.append(_mk(r["date"], r["amt"], _finalize_kind(sign, r["desc"]), r["desc"]))
    return txns


# ----------------------------------------------------------------------------
# 通路 3：OCR
# ----------------------------------------------------------------------------
_ocr_engine = None


def _engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr import RapidOCR
        _ocr_engine = RapidOCR(params={"Global.log_level": "error"})
    return _ocr_engine


def _tiles(img):
    """长截图切片，切口选在最“空白”的行，避免把文字切断。"""
    import numpy as np
    w, h = img.size
    if h <= w * 2.4:
        return [img]
    gray = np.asarray(img.convert("L"), dtype="float32")
    cuts, y, step = [0], 0, int(w * 1.8)
    while y + step * 1.25 < h:
        lo, hi = int(y + step * 0.85), int(y + step * 1.15)
        stds = gray[lo:hi].std(axis=1)
        y = lo + int(stds.argmin())
        cuts.append(y)
    cuts.append(h)
    return [img.crop((0, a, w, b)) for a, b in zip(cuts, cuts[1:]) if b - a > 8]


def ocr_image(img):
    """对 PIL 图片做 OCR，返回按版面还原的文本行。"""
    import numpy as np
    img = img.convert("RGB")
    if max(img.size) < 900:  # 小图放大可明显提高识别率
        k = 900 / max(img.size)
        img = img.resize((int(img.width * k), int(img.height * k)))
    lines = []
    for tile in _tiles(img):
        res = _engine()(np.asarray(tile))
        if res is None or res.boxes is None or res.txts is None:
            continue
        items = []
        for box, txt in zip(res.boxes, res.txts):
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append((sum(ys) / 4, min(xs), max(ys) - min(ys), txt))
        if not items:
            continue
        items.sort()
        med_h = sorted(i[2] for i in items)[len(items) // 2] or 10
        row, row_y = [], None
        for yc, x, hgt, txt in items:
            if row_y is None or abs(yc - row_y) <= med_h * 0.6:
                row.append((x, txt))
                row_y = yc if row_y is None else (row_y * (len(row) - 1) + yc) / len(row)
            else:
                lines.append("  ".join(t for _, t in sorted(row)))
                row, row_y = [(x, txt)], yc
        if row:
            lines.append("  ".join(t for _, t in sorted(row)))
    return lines


def parse_ocr_lines(lines, ctx):
    """账单截图常见版式：金额与商户同一行，日期在下一行（或作为上方分组标题）。"""
    recs = []
    for raw in lines:
        line = _BAL_INLINE.sub(" ", raw.strip())
        rel = None
        if re.search(r"今天|today", line, re.I):
            rel = ctx.mtime
        elif re.search(r"昨天|yesterday", line, re.I):
            rel = ctx.mtime - dt.timedelta(days=1)
        elif "前天" in line:
            rel = ctx.mtime - dt.timedelta(days=2)
        date, amts, desc = _split_line(line, ctx, allow_date_anywhere=True)
        date = date or rel
        if re.match(r"^\s*(支出|收入|结余|合计|总支出|总收入|共支出|共收入|余额|可用余额|总资产)", line):
            amts = []
        if _SKIP_LINE.search(line):
            amts = []
        recs.append({"date": date, "amts": amts, "desc": re.sub(r"今天|昨天|前天", "", desc).strip()})

    amt_idx = [i for i, r in enumerate(recs) if r["amts"]]
    date_only = [i for i, r in enumerate(recs) if r["date"] and not r["amts"]]
    below = bool(amt_idx and date_only and amt_idx[0] < date_only[0])

    txns, current = [], None
    for i, r in enumerate(recs):
        if not r["amts"]:
            if r["date"] and not below:
                current = r["date"]
            continue
        date = r["date"]
        desc = r["desc"]
        if date is None and below:
            for j in (i + 1, i + 2):
                if j < len(recs) and not recs[j]["amts"]:
                    if recs[j]["date"]:
                        date = recs[j]["date"]
                        break
                else:
                    break
        if date is None:
            date = current
        if len(desc) < 2:  # 商户名可能在上一行
            for j in (i - 1, i + 1):
                if 0 <= j < len(recs) and not recs[j]["amts"] and not recs[j]["date"] \
                        and len(recs[j]["desc"]) >= 2:
                    desc = recs[j]["desc"]
                    break
        if date is None:
            continue
        val, sign, *_ = r["amts"][0]
        if sign == 0:
            sign = 1 if looks_like_income(desc) else -1
        txns.append(_mk(date, val, _finalize_kind(sign, desc), desc))
    return txns


# ----------------------------------------------------------------------------
# 收入凭证（工资条、到账截图）
# ----------------------------------------------------------------------------
def parse_income_doc(lines, ctx, label):
    """从非流水类凭证中提取一笔收入：优先“实发 / Net Pay”等关键字旁的金额。"""
    low = [l.lower() for l in lines]
    date = None
    for l in lines:
        ds = [d for d in find_dates(l) if d[2]]
        if ds:
            date = ctx.resolve(ds[-1])
            break
    date = date or ctx.mtime
    for key in _PAY_KEYS:
        for i, l in enumerate(low):
            mk = re.search(r"(?<![a-z])" + re.escape(key), l)
            if not mk:
                continue
            p = mk.start()
            tail = _TIME.sub(" ", _strip_spans(lines[i], [(s, e) for s, e, *_ in find_dates(lines[i])]))
            cands = [a for a in find_amounts(tail) if a[2] >= min(p, len(tail))] or find_amounts(tail)
            if not cands and i + 1 < len(lines):
                cands = find_amounts(_TIME.sub(" ", lines[i + 1]))
            if cands:
                name = "工资收入" if re.search(r"实发|net|take", key) else "收入"
                return [_mk(date, cands[-1][0] if re.search(r"实发|net|take", key) else cands[0][0],
                            "income", f"{name} · {label}")], False
    allamts = []
    for l in lines:
        clean = _TIME.sub(" ", _strip_spans(l, [(s, e) for s, e, *_ in find_dates(l)]))
        allamts += [a[0] for a in find_amounts(clean)]
    if allamts:
        return [_mk(date, max(allamts), "income", f"收入 · {label}")], True
    return [], True


# ----------------------------------------------------------------------------
# 各类文件读取
# ----------------------------------------------------------------------------
def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _text_to_grid(text: str):
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    sample = lines[:80]
    delim = max([",", "\t", ";", "|"], key=lambda d: sum(l.count(d) for l in sample))
    if sum(l.count(delim) for l in sample) < len(sample):
        return []
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    return [[c.strip() for c in r] for r in rows]


class _TableHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.text = [], None, None, []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag == "br":
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
                self.text.append("  ".join(self.row) + "\n")
            self.row = None
        elif tag in ("p", "div", "li"):
            self.text.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif self.row is None:
            self.text.append(data)


def _read_html(text):
    p = _TableHTML()
    p.feed(text)
    return [p.rows], "".join(p.text)


def _read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    grids = []
    for ws in wb.worksheets:
        grids.append([list(r) for r in ws.iter_rows(values_only=True)])
    wb.close()
    return grids


def _read_xls(path):
    import xlrd
    wb = xlrd.open_workbook(path)
    grids = []
    for sh in wb.sheets():
        g = []
        for r in range(sh.nrows):
            row = []
            for c in range(sh.ncols):
                cell = sh.cell(r, c)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        row.append(xlrd.xldate_as_datetime(cell.value, wb.datemode))
                    except Exception:
                        row.append(cell.value)
                else:
                    row.append(cell.value)
            g.append(row)
        grids.append(g)
    return grids


def _read_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")

    def txt(frag):
        frag = re.sub(r"<w:tab[^>]*/>", "\t", frag)
        return re.sub(r"\s+", " ", "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", frag))).strip()

    grids = []
    for tbl in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S):
        g = [[txt(c) for c in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
             for tr in re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S)]
        grids.append(g)
    lines = [txt(p) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    lines += ["  ".join(r) for g in grids for r in g]
    return grids, [l for l in lines if l]


def _parse_ofx(text, ctx):
    txns = []
    for blk in re.findall(r"<STMTTRN>(.*?)(?=<STMTTRN>|</BANKTRANLIST>|</STMTTRN>|\Z)", text, re.S | re.I):
        def tag(t):
            m = re.search(rf"<{t}>([^<\r\n]*)", blk, re.I)
            return m[1].strip() if m else ""
        amt, d = parse_number(tag("TRNAMT")), tag("DTPOSTED")
        if amt is None or len(d) < 8:
            continue
        try:
            date = dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        except ValueError:
            continue
        desc = " ".join(x for x in (tag("NAME"), tag("MEMO")) if x)
        txns.append(_mk(date, amt, _finalize_kind(1 if amt > 0 else -1, desc), desc))
    cur = re.search(r"<CURDEF>([A-Z]{3})", text)
    return txns, (cur[1] if cur else None)


class NeedPassword(Exception):
    pass


def _read_pdf(path, password=None):
    """返回 (grids, text_lines, ocr_lines)。无文字层的页面走 OCR。"""
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    try:
        pdf = pdfplumber.open(path, password=password or None)
    except Exception as e:  # pdfplumber 把密码错误包装成多种异常
        if isinstance(e, PDFPasswordIncorrect) or "password" in repr(e).lower():
            raise NeedPassword() from e
        raise
    grids, lines, scanned = [], [], []
    with pdf:
        for idx, page in enumerate(pdf.pages[:200]):
            text = page.extract_text() or ""
            if len(text.strip()) < 20:
                scanned.append(idx)
                continue
            lines += text.splitlines()
            try:
                for tb in page.extract_tables():
                    g = [[(c or "").replace("\n", " ").strip() for c in row] for row in tb if row]
                    if g and max(len(r) for r in g) >= 3:
                        grids.append(g)
            except Exception:
                pass
    ocr_lines = []
    if scanned:
        import pypdfium2
        doc = pypdfium2.PdfDocument(path, password=password or None)
        try:
            for idx in scanned[:30]:
                img = doc[idx].render(scale=2.2).to_pil()
                ocr_lines += ocr_image(img)
        finally:
            doc.close()
    return grids, lines, ocr_lines


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def parse_file(path: str, mode: str = "auto", password: str | None = None) -> dict:
    """mode: auto（自动判断）/ statement（银行流水）/ income（收入凭证）"""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    ctx = Ctx(path)
    grids, lines, ocr_lines, warnings = [], [], [], []
    txns, method, currency = [], "", None

    if ext == ".pdf":
        grids, lines, ocr_lines = _read_pdf(path, password)
        method = "PDF 扫描件识别" if ocr_lines and not lines else "PDF 文本解析"
    elif ext in IMAGE_EXT:
        from PIL import Image, ImageSequence
        with Image.open(path) as im:
            frames = [f.copy() for f in ImageSequence.Iterator(im)][:20] if ext in (".tif", ".tiff") else [im.copy()]
        for f in frames:
            ocr_lines += ocr_image(f)
        method = "截图文字识别"
    elif ext in (".xlsx", ".xlsm"):
        grids = _read_xlsx(path)
        method = "Excel 表格"
    elif ext == ".xls":
        try:
            grids = _read_xls(path)
        except Exception:  # 很多银行导出的 .xls 实际是 HTML 或文本
            raw = _decode(open(path, "rb").read())
            if "<table" in raw.lower():
                grids, t = _read_html(raw)
                lines = t.splitlines()
            else:
                grids, lines = [_text_to_grid(raw)], raw.splitlines()
        method = "Excel 表格"
    elif ext == ".docx":
        grids, lines = _read_docx(path)
        method = "Word 文档"
    elif ext in (".html", ".htm"):
        grids, t = _read_html(_decode(open(path, "rb").read()))
        lines = t.splitlines()
        method = "网页表格"
    elif ext in (".ofx", ".qfx"):
        raw = _decode(open(path, "rb").read())
        ctx.set_text(raw)
        txns, currency = _parse_ofx(raw, ctx)
        lines = raw.splitlines()
        method = "OFX 账务文件"
    else:
        data = open(path, "rb").read()
        if b"\x00" in data[:2000] and data[:2] not in (b"\xff\xfe", b"\xfe\xff"):
            raise ValueError("暂不支持这种文件格式")
        raw = _decode(data)
        grids, lines = [_text_to_grid(raw)], raw.splitlines()
        method = "CSV / 文本"

    grid_text = "\n".join("  ".join(str(c) for c in r if c is not None) for g in grids for r in g[:400])
    full_text = "\n".join(lines + ocr_lines) + "\n" + grid_text
    ctx.set_text(full_text)
    credit_card = bool(_CREDIT_CARD.search(full_text[:6000]) or _CREDIT_CARD.search(name))

    if not txns:
        t_grid, cur = parse_grids(grids, ctx) if grids else ([], None)
        currency = cur
        t_line = parse_text_lines(lines, ctx, credit_card) if lines else []
        t_ocr = parse_ocr_lines(ocr_lines, ctx) if ocr_lines else []
        txns = max([t_grid, t_line, t_ocr], key=len)  # 取识别最完整的一路

    all_lines = lines + ocr_lines or grid_text.splitlines()
    is_income_doc = mode == "income" or (mode == "auto" and bool(_PAYSLIP.search(full_text)))
    if is_income_doc:
        if _PAYSLIP.search(full_text) or len(txns) == 0:
            got, unsure = parse_income_doc(all_lines, ctx, os.path.splitext(name)[0][:30])
            if got:
                txns = got
                if unsure:
                    warnings.append("未找到明确的“实发/到账”字样，已取凭证中最大的金额，请核对。")
        for t in txns:
            if t["kind"] != "income":
                t["kind"] = "income"
        method += " · 收入凭证"

    if not txns:
        if not full_text.strip():
            warnings.append("没有读到任何文字，文件可能是空白或损坏的。")
        else:
            warnings.append("没有识别出交易记录。可以在下方手动添加，或换一种导出格式再试。")
    if ocr_lines and txns:
        warnings.append("来自图片识别，个别数字可能有误，请在确认前核对。")

    today = dt.date.today()
    txns = [t for t in txns if "2000-01-01" <= t["date"] <= (today + dt.timedelta(days=1)).isoformat()]
    card = guess_card(full_text, name, credit_card)
    for t in txns:
        t["card"] = t.get("card") or card
    return {
        "file": name, "path": path, "method": method, "card": card,
        "account": guess_account(full_text, name),
        "currency": currency or guess_currency(full_text),
        "credit_card": credit_card, "txns": txns, "warnings": warnings,
    }
