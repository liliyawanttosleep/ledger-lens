# -*- coding: utf-8 -*-
"""识别“自己账户之间的资金流动”——信用卡还款、跨行互转、自己给自己的 Zelle 等。
这些既不是收入也不是开销，统一标为“内部转账”，不计入任何统计。

三层判断：
  1. 关键词：Payment Thank You、Payment from CHK、Ext Trnsfr、信用卡还款 ……（categorize.is_transfer）
  2. 本人姓名：对方是自己（Zelle payment to <本人>、Transfer <本人>）
  3. 跨账户配对：A 账户转出与 B 账户转入金额相同、日期相近，且至少一方带有转账字样
用户手动改过类型的交易会被锁定，不再自动改动。
"""
import datetime as dt
import re
from collections import Counter, defaultdict

import store
from categorize import TRANSFER_CATEGORY, is_transfer

_HINT = re.compile(r"transfer|trnsfr|xfer|zelle|payment|pmt\b|\bach\b|wire|p2p|deposit|withdraw|"
                   r"转账|还款|转入|转出|汇款|汇入|提现|充值|跨行|同名", re.I)
_SELF_CTX = re.compile(r"zelle|transfer|trnsfr|xfer|p2p|\bach\b|wire|转账|汇款|转入|转出", re.I)
_NOT_SELF = re.compile(r"salary|payroll|refund|rent\b|工资|薪|退款|报销", re.I)
_ZELLE_PARTY = re.compile(r"zelle (?:payment|transfer)?\s*(?:to|from)\s+([a-z][a-z .'\-]{2,40}?)(?:\s+(?:for|conf)\b|\s*$)", re.I)
_INDN = re.compile(r"INDN:\s*([A-Za-z][A-Za-z .'\-]{2,40}?)\s+CO ID", re.I)
_PLAIN_TRANSFER = re.compile(r"^(?:ach )?transfer(?: to| from)?\s+([A-Za-z][A-Za-z .'\-]{2,40}?)(?:\s+requested.*)?$", re.I)


def owner_names() -> list:
    raw = store.get_setting("owner_names", "") or ""
    return [n.strip().lower() for n in re.split(r"[,，;；\n]", raw) if len(n.strip()) >= 2]


def set_owner_names(text: str):
    names = []
    for n in re.split(r"[,，;；\n]", text or ""):
        n = re.sub(r"\s+", " ", n).strip()
        if len(n) >= 2 and n.lower() not in [x.lower() for x in names]:
            names.append(n)
    store.set_setting("owner_names", ", ".join(names))


def learn_owner(descs) -> list:
    """从账单描述里推断本人姓名（BoA 等银行的 ACH 记录带 INDN:姓名）。出现 ≥3 次才采纳。"""
    c = Counter()
    for d in descs:
        for m in _INDN.finditer(d or ""):
            c[re.sub(r"\s+", " ", m[1]).strip().lower()] += 1
        m = _PLAIN_TRANSFER.match((d or "").strip())
        if m:
            c[re.sub(r"\s+", " ", m[1]).strip().lower()] += 1
    found = [n for n, k in c.items() if k >= 3 and len(n.split()) >= 2]
    if found:
        have = owner_names()
        new = [n for n in found if n not in have]
        if new:
            set_owner_names(", ".join(have + new).title())
    return found


def is_self(desc: str, names: list) -> bool:
    """对方就是本人：描述里出现本人姓名，且语境是转账而不是工资/退款。"""
    d = (desc or "").lower()
    if not names or not _SELF_CTX.search(d) or _NOT_SELF.search(d):
        return False
    return any(n in d for n in names)


def _zelle_other(desc: str, names: list) -> bool:
    """明确是和别人的 Zelle 往来（不能拿去做跨账户配对）。"""
    m = _ZELLE_PARTY.search(desc or "")
    if not m:
        return False
    who = m[1].strip().lower()
    return not any(n in who or who in n for n in names)


def _key(t):
    return (t.get("account") or "") + "|" + (t.get("card") or "")


def _days(a, b):
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def reclassify() -> int:
    """对全库重新识别内部转账，返回本次新标记的笔数。"""
    txns = [t for t in store.all_transactions() if not t.get("locked")]
    learn_owner(t["desc"] for t in txns)
    names = owner_names()
    mark = set()

    # 1 + 2：关键词与本人姓名
    for t in txns:
        if t["kind"] != "transfer" and (is_transfer(t["desc"]) or is_self(t["desc"], names)):
            mark.add(t["id"])

    def is_tr(t):
        return t["kind"] == "transfer" or t["id"] in mark

    # 3：跨账户配对（按币种、金额）
    by_amt = defaultdict(list)
    for t in txns:
        by_amt[(t["currency"], round(t["amount"] * 100))].append(t)
    for group in by_amt.values():
        if len(group) < 2:
            continue
        used = set()
        # 3a 已确定是转账的一方（如信用卡的 Payment Thank You）去找另一账户里金额相同的对手记录
        for a in group:
            if not is_tr(a):
                continue
            for b in group:
                if b["id"] in used or b["id"] == a["id"] or is_tr(b) or _key(a) == _key(b):
                    continue
                if _days(a["date"], b["date"]) <= 4 and _HINT.search(b["desc"]) \
                        and not _zelle_other(b["desc"], names):
                    mark.add(b["id"])
                    used.add(b["id"])
                    break
        # 3b 一出一进、不同账户、日期相近、带转账字样
        outs = [t for t in group if t["kind"] == "expense" and not is_tr(t)]
        ins = [t for t in group if t["kind"] == "income" and not is_tr(t)]
        for o in outs:
            for i in ins:
                if i["id"] in used or _key(o) == _key(i) or _days(o["date"], i["date"]) > 4:
                    continue
                if not (_HINT.search(o["desc"]) or _HINT.search(i["desc"])):
                    continue
                if _zelle_other(o["desc"], names) or _zelle_other(i["desc"], names):
                    continue
                mark.update((o["id"], i["id"]))
                used.add(i["id"])
                break

    for tid in mark:
        store.update_transaction(tid, {"kind": "transfer", "category": TRANSFER_CATEGORY})
    return len(mark)
