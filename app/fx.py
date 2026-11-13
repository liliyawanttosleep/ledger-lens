# -*- coding: utf-8 -*-
"""货币：识别一笔交易是什么货币、各货币的符号、汇率与折算。

- 每笔交易自带 currency。默认按币种分开统计；用户选“合并”时按当前参考汇率折算成一种货币再统计。
- 汇率：内置一份参考汇率（离线兜底），联网时从公开接口更新并缓存在 settings 里。
  更新汇率的请求只是一个不带任何参数的 GET，不发送任何用户数据。
"""
import datetime as dt
import json
import re
import urllib.request

ALL = "ALL"  # “合并”视图用的伪币种代码，永远不写进数据库

SYMBOLS = {"CNY": "¥", "USD": "$", "HKD": "HK$", "EUR": "€", "GBP": "£", "JPY": "JP¥", "KRW": "₩", "CAD": "CA$",
           "AUD": "A$", "SGD": "S$", "TWD": "NT$", "CHF": "CHF ", "THB": "฿", "MYR": "RM", "INR": "₹", "MXN": "MX$",
           "BRL": "R$", "NZD": "NZ$", "SEK": "SEK ", "NOK": "NOK ", "DKK": "DKK ", "AED": "AED ", "SAR": "SAR ",
           "RUB": "₽", "VND": "₫", "PHP": "₱", "IDR": "Rp", "TRY": "₺", "ZAR": "R", "MOP": "MOP$"}
CODES = list(SYMBOLS)

# 内置参考汇率：1 美元 = 多少该货币。联网更新失败时使用。
BUILTIN = {"date": "2026-11-13", "source": "builtin", "rates": {
    "USD": 1, "CNY": 6.685071, "HKD": 7.844955, "EUR": 0.903491, "GBP": 0.755149, "JPY": 159.795417,
    "KRW": 1334.182801, "CAD": 1.42563, "AUD": 1.468309, "SGD": 1.286283, "TWD": 32.976133, "CHF": 0.83437,
    "THB": 33.855133, "MYR": 4.078759, "INR": 94.086126, "MXN": 18.620415, "BRL": 5.610238, "NZD": 1.802654,
    "SEK": 10.018002, "NOK": 9.56065, "DKK": 6.747617, "AED": 3.6725, "SAR": 3.75, "RUB": 82.849685,
    "VND": 25690.620978, "PHP": 63.786172, "IDR": 18250.530965, "TRY": 50.311711, "ZAR": 16.735572, "MOP": 8.080272}}
RATES_URL = "https://open.er-api.com/v6/latest/USD"

# 能明确指向一种货币的写法。单独的 “$” “¥” 有歧义（美元 / 加元…，人民币 / 日元），不在这里，交给整份文件的判断。
_TOKENS = [
    ("HKD", r"HK\$|\bHKD\b|港币|港元"), ("USD", r"US\$|\bUSD\b|美元|美金"), ("CAD", r"CA\$|C\$|\bCAD\b|加元|加币"),
    ("AUD", r"AU\$|A\$|\bAUD\b|澳元|澳币"), ("SGD", r"S\$|\bSGD\b|新加坡元|新币"), ("TWD", r"NT\$|\bTWD\b|新台币|台币"),
    ("NZD", r"NZ\$|\bNZD\b"), ("MXN", r"MX\$|\bMXN\b"), ("BRL", r"R\$|\bBRL\b"), ("MOP", r"MOP\$|\bMOP\b|澳门元|葡币"),
    ("EUR", r"€|\bEUR\b|欧元"), ("GBP", r"£|\bGBP\b|英镑"),
    ("JPY", r"\bJPY\b|円|日元|日圆"), ("KRW", r"₩|\bKRW\b|韩元|韩币|원"), ("CHF", r"\bCHF\b|瑞郎|瑞士法郎"),
    ("THB", r"฿|\bTHB\b|泰铢"), ("MYR", r"\bMYR\b|\bRM(?=\s?\d)|林吉特|马币"), ("INR", r"₹|\bINR\b|卢比"),
    ("RUB", r"₽|\bRUB\b|卢布"), ("VND", r"₫|\bVND\b|越南盾"), ("PHP", r"₱|\bPHP\b"), ("IDR", r"\bIDR\b|印尼盾"),
    ("TRY", r"₺|\bTRY\b"), ("SEK", r"\bSEK\b"), ("NOK", r"\bNOK\b"), ("DKK", r"\bDKK\b"), ("AED", r"\bAED\b|迪拉姆"),
    ("SAR", r"\bSAR\b"), ("ZAR", r"\bZAR\b"),
    ("CNY", r"\bCNY\b|\bRMB\b|人民币|元"),  # 放最后：“日元 / 港元 / 美元” 要先被上面的规则认走
]
_TOKENS = [(c, re.compile(rx, re.I)) for c, rx in _TOKENS]
_NUM = r"\d[\d,]*(?:\.\d+)?"
_ANY = "|".join(f"(?P<{c}>{rx.pattern})" for c, rx in _TOKENS)
_NEAR = re.compile(rf"(?:{_ANY})\s?[-+−]?\s?(?P<n1>{_NUM})|(?P<n2>{_NUM})\s?(?:{_ANY.replace('?P<', '?P<x')})", re.I)


def symbol(code: str) -> str:
    return SYMBOLS.get(code, (code or "") + " ")


def code_of(text) -> str:
    """一小段文字（如表格的“币种”单元格）指的是哪种货币；认不出返回空串。"""
    s = str(text or "").strip()
    if not s:
        return ""
    if s.upper() in SYMBOLS:
        return s.upper()
    for c, rx in _TOKENS:
        if rx.search(s):
            return c
    return ""


def amount_currency(line: str, value: float) -> str:
    """这一行里，紧挨着金额 value 写明的货币（如 “HK$ 120.00”“88.00元”“1,200 JPY”）。没写明返回空串。"""
    for m in _NEAR.finditer(line or ""):
        n = m["n1"] or m["n2"]
        try:
            if abs(float(n.replace(",", "")) - value) > 0.005:
                continue
        except ValueError:
            continue
        for c, _ in _TOKENS:
            if m[c] or m["x" + c]:
                return c
    return ""


def count_tokens(text: str) -> dict:
    return {c: len(rx.findall(text)) for c, rx in _TOKENS}


# ---------------------------------------------------------------- 汇率
def _store():
    import store
    return store


def rates() -> dict:
    """{"date", "source", "rates": {code: 每 1 美元折合多少}}。优先用缓存的联网汇率。"""
    try:
        raw = _store().get_setting("fx_rates", "")
        if raw:
            d = json.loads(raw)
            if d.get("rates", {}).get("USD"):
                return {**d, "rates": {**BUILTIN["rates"], **d["rates"]}}
    except Exception:
        pass
    return BUILTIN


def refresh(timeout: float = 6) -> dict:
    """联网取最新汇率并缓存。失败时返回现有汇率并带上 error。"""
    try:
        req = urllib.request.Request(RATES_URL, headers={"User-Agent": "ledger-lens"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        got = {c: float(v) for c, v in d["rates"].items() if c in SYMBOLS and float(v) > 0}
        if d.get("result") != "success" or "USD" not in got:
            raise ValueError("bad response")
        day = dt.datetime.fromtimestamp(int(d.get("time_last_update_unix") or 0), dt.timezone.utc).date().isoformat() \
            if d.get("time_last_update_unix") else dt.date.today().isoformat()
        out = {"date": day, "source": "open.er-api.com", "rates": got, "fetched": dt.date.today().isoformat()}
        _store().set_setting("fx_rates", json.dumps(out))
        return rates()
    except Exception as e:  # 没网、超时、接口变了：继续用旧汇率
        return {**rates(), "error": str(e)[:80]}


def stale() -> bool:
    return rates().get("fetched") != dt.date.today().isoformat()


def rate(frm: str, to: str, table: dict = None) -> float:
    """1 单位 frm 等于多少 to。不认识的货币按 1:1（并在界面上提示）。"""
    r = (table or rates())["rates"]
    if frm == to or frm not in r or to not in r:
        return 1.0
    return r[to] / r[frm]


def convert_txns(txns: list, base: str) -> list:
    """把一组不同货币的交易折算成 base，原金额和原币种保留在 orig_amount / orig_currency。"""
    table = rates()
    out = []
    for t in txns:
        cur = t.get("currency") or base
        c = dict(t)
        if cur != base:
            c["orig_amount"], c["orig_currency"] = t["amount"], cur
            c["amount"] = round(t["amount"] * rate(cur, base, table), 2)
        c["currency"] = base
        out.append(c)
    return out
