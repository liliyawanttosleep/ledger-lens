# -*- coding: utf-8 -*-
"""识别“自己账户之间的资金流动”——信用卡还款、跨行互转、自己给自己的 Zelle 等。
这些既不是收入也不是开销，统一标为“内部转账”，不计入任何统计。

三层判断：
  1. 关键词：Payment Thank You、Payment from CHK、Ext Trnsfr、信用卡还款 ……（categorize.is_transfer）
  2. 本人姓名：对方是自己（Zelle payment to <本人>、Transfer <本人>）
  3. 跨账户配对：A 账户转出与 B 账户转入金额相同、方向相反、日期相近，且至少一方带有转账字样。
     每次导入都对全库重新核对，配上的两笔互相记在 pair_id（“有记忆”：先后导入的账单也能对上）
  4. 路线记忆：同一描述签名已配上过两次或被手动确认过，以后直接认
用户手动改过类型的交易会被锁定，不再自动改动。
"""
import datetime as dt
import re
from collections import Counter, defaultdict

import store
from categorize import TRANSFER_CATEGORY, categorize, is_transfer

RETURNED = "已退货"
_TAX = re.compile(r"tax ref|irs treas|退税|报销|reimburse", re.I)
_PREFIX = re.compile(r"^(?:paypal|sq|tst|dd|wl|sp|py|in|uep|google|amzn|apple\.com)\s*\*\s*", re.I)


def _brand(desc: str) -> str:
    """商户名的第一个词，用来判断退款和原消费是不是同一家。"""
    s = _PREFIX.sub("", (desc or "").lower())
    m = re.search(r"[a-z\u4e00-\u9fff]{3,}", s) or re.search(r"[a-z0-9]{4,}", s)
    return m[0][:6] if m else ""

_HINT = re.compile(r"transfer|trnsfr|xfer|zelle|payment|pmt\b|\bach\b|wire|p2p|deposit|withdraw|"
                   r"转账|还款|转入|转出|汇款|汇入|提现|充值|跨行|同名", re.I)
_SELF_CTX = re.compile(r"zelle|transfer|trnsfr|xfer|p2p|\bach\b|wire|转账|汇款|转入|转出", re.I)
_NOT_SELF = re.compile(r"salary|payroll|refund|rent\b|工资|薪|退款|报销", re.I)
_ZELLE_PARTY = re.compile(r"zelle (?:payment|transfer)?\s*(?:to|from)\s+([a-z][a-z .'\-]{2,40}?)(?:\s+(?:for|conf)\b|\s*$)", re.I)
_BANK_WORD = r"chase|\bboa\b|bofa|bank|usbank|wells|citi|capital|discover|amex|checking|savings|fidelity|schwab"
_BANK_CTX = re.compile(r"electronic (?:deposit|withdrawal)|web authorized (?:pmt|payment)|external transfer|"
                       r"ach (?:deposit|credit|debit|withdrawal|pmt)|real time payment|网银互联|跨行", re.I)
_BANK_NAME = re.compile(r"jpmorgan chase|chase bank|bank of america|wells fargo|citibank|capital one|u\.?s\.? bank|"
                        r"discover bank|ally bank|chime|sofi|fid bkg|fidelity|schwab|vanguard|robinhood|"
                        r"wealthfront|betterment|webull|industrial and c|icbc|bank of china", re.I)
_PAYER_PREFIX = re.compile(r"^(?:electronic (?:deposit|withdrawal)|web authorized (?:pmt|payment)|direct deposit|"
                           r"ach (?:deposit|credit|debit|withdrawal|pmt)|pos (?:purchase|debit)|debit card purchase|"
                           r"checkcard \d+|purchase|recurring)\s+", re.I)
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
    if not names or _NOT_SELF.search(d):
        return False
    for n in names:
        if n in d and (_SELF_CTX.search(d) or re.search(r"\b(?:to|from)\s+" + re.escape(n), d)):
            return True
        first = n.split()[0]
        if len(first) >= 3 and re.search(r"\b(?:to|from)\s+" + re.escape(first) + r"\s+(?:" + _BANK_WORD + r")", d):
            return True  # Zelle 联系人昵称，如 “Alex Chase”
    return False


def is_bank_move(desc: str) -> bool:
    """对手方是一家银行 / 券商的电子转入转出：自己别处账户的资金往来（含转入证券账户）。"""
    d = (desc or "").lower()
    return bool(_BANK_CTX.search(d) and _BANK_NAME.search(d))


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


LAST = {"pairs": 0, "pending": 0, "remembered": 0}   # 最近一次 reclassify 的结果，给界面提示用
WINDOW = 5                                            # 两头入账日期最多相差几天（跨周末的 ACH）
_VAGUE = {"其他支出", "其他收入", "转账收入"}          # 只有这些“说不清”的分类才可能被配对改成内部转账
_FLOW_IN = re.compile(r"\bfrom\b|deposit|thank you|received|转入|汇入|存入", re.I)
_FLOW_OUT = re.compile(r"\bto\b|withdrawal|转出|汇出", re.I)


def flow(t) -> str:
    """资金方向 in / out。入库时记录；老数据里已是 transfer 的只能从描述里猜，猜不出返回空串（配对时不设限）。"""
    if t.get("flow") in ("in", "out"):
        return t["flow"]
    if t["kind"] in ("income", "refund"):
        return "in"
    if t["kind"] == "expense":
        return "out"
    d = t.get("desc") or ""
    i, o = bool(_FLOW_IN.search(d)), bool(_FLOW_OUT.search(d))
    return "in" if i and not o else "out" if o and not i else ""


_BANKS = [("chase", r"jpmorgan|chase"), ("boa", r"bank of america|\bboa\b|bofa"), ("usbank", r"\bu\.?s\.? ?bank"),
          ("wells", r"wells"), ("citi", r"citi"), ("capone", r"capital one"), ("discover", r"discover"),
          ("amex", r"amex|american express"), ("fidelity", r"fid bkg|fidelity"), ("schwab", r"schwab"),
          ("icbc", r"icbc|工商"), ("boc", r"bank of china|中国银行"), ("ccb", r"建设银行|\bccb\b"),
          ("cmb", r"招商|\bcmb\b"), ("abc", r"农业银行"), ("alipay", r"支付宝|alipay"), ("wechat", r"微信|wechat")]
_BANKS = [(k, re.compile(rx, re.I)) for k, rx in _BANKS]


def banks_in(text: str) -> set:
    return {k for k, rx in _BANKS if rx.search(text or "")}


def names_elsewhere(t, other) -> bool:
    """t 的描述里点名了某家银行，而 other 不在那家银行 → 这两笔不是同一次转账的两头。"""
    named = banks_in(t["desc"]) - banks_in(t.get("account"))
    there = banks_in(other.get("account"))
    return bool(named and there and not (named & there))


def sig(desc: str) -> str:
    """转账描述的“签名”：去掉通道前缀和数字后的前四个词。同一条转账路线每个月的描述签名相同。"""
    s = _PAYER_PREFIX.sub("", (desc or "").split(" · ")[0].lower())
    words = re.findall(r"[a-z一-鿿]{2,}", s)
    return " ".join(words[:4]) if len(words) >= 2 else ""


def with_pairs(txns: list) -> list:
    """给每笔已配对的内部转账附上另一头的信息（pair: {account, card, date}），界面用来显示“↔ 对方账户”。"""
    byid = {t["id"]: t for t in txns}
    for t in txns:
        p = byid.get(t.get("pair_id") or 0)
        if p and t["kind"] == "transfer":
            t["pair"] = {"account": p.get("account") or "", "card": p.get("card") or "", "date": p["date"]}
    return txns


def reclassify() -> int:
    """对全库重新识别内部转账，返回本次新标记的笔数。
    每次导入后都会跑：新账单里的每一笔都会去和库里已有的所有账单核对（金额、日期、方向、转账字样），
    所以先导入信用卡、过几天再导入储蓄卡，两头也能对上。配上的两笔互相记在 pair_id 里。"""
    pool = store.all_transactions()
    byid = {t["id"]: t for t in pool}
    # 0 清掉失效的配对（另一头被删除，或有一头被用户改回了收入 / 支出）
    for t in pool:
        if not t.get("pair_id"):
            continue
        p = byid.get(t["pair_id"])
        if not p or p.get("pair_id") != t["id"] or p["kind"] != "transfer" or t["kind"] != "transfer":
            store.update_transaction(t["id"], {"pair_id": 0})
            t["pair_id"] = 0
    learn_owner(t["desc"] for t in pool if not t.get("locked"))
    names = owner_names()
    mark = set()

    def free(t):   # 可以被自动改类型
        return not t.get("locked") and t["kind"] in ("income", "expense") and t["id"] not in mark

    def is_tr(t):
        return (t["kind"] == "transfer" and t["category"] == TRANSFER_CATEGORY) or t["id"] in mark

    # 1 + 2：关键词、本人姓名、对手方是银行 / 券商
    for t in pool:
        if free(t) and (is_transfer(t["desc"]) or is_self(t["desc"], names) or is_bank_move(t["desc"])):
            mark.add(t["id"])

    # 3：跨账户配对（按币种、金额分组）
    by_amt = defaultdict(list)
    for t in pool:
        by_amt[(t["currency"], round(t["amount"] * 100))].append(t)
    groups = [sorted(g, key=lambda t: t["date"]) for g in by_amt.values() if len(g) >= 2]
    linked = {t["id"] for t in pool if t.get("pair_id")}
    new_pairs = [0]

    def compatible(a, b):
        fa, fb = flow(a), flow(b)
        return (_key(a) != _key(b) and _days(a["date"], b["date"]) <= WINDOW and not (fa and fb and fa == fb)
                and not names_elsewhere(a, b) and not names_elsewhere(b, a))

    def candidate(b):   # 还没定性、但看起来像转账的一头
        return free(b) and b["category"] in _VAGUE and not _zelle_other(b["desc"], names)

    def link(a, b):
        for x, y in ((a, b), (b, a)):
            store.update_transaction(x["id"], {"pair_id": y["id"]})
            x["pair_id"] = y["id"]
            linked.add(x["id"])
        new_pairs[0] += 1

    def pair():
        for g in groups:
            # 3a 已确定是转账的一头（如信用卡的 Payment Thank You）去找另一账户里金额相同、方向相反的记录
            for a in g:
                if a["id"] in linked or not is_tr(a):
                    continue
                best = None
                for b in sorted(g, key=lambda b: (not is_tr(b), _days(a["date"], b["date"]))):
                    if b["id"] == a["id"] or b["id"] in linked or not compatible(a, b):
                        continue
                    if is_tr(b) or (candidate(b) and _HINT.search(b["desc"])):
                        best = b
                        break
                if best:
                    if not is_tr(best):
                        mark.add(best["id"])
                    link(a, best)
            # 3b 两头都还没定性：一出一进、不同账户、日期相近、至少一头带转账字样
            for o in g:
                if o["id"] in linked or o["kind"] != "expense" or not candidate(o):
                    continue
                for i in sorted(g, key=lambda b: _days(o["date"], b["date"])):
                    if i["id"] in linked or i["kind"] != "income" or not candidate(i) or not compatible(o, i):
                        continue
                    if not (_HINT.search(o["desc"]) or _HINT.search(i["desc"])):
                        continue
                    mark.update((o["id"], i["id"]))
                    link(o, i)
                    break

    pair()

    # 4 记忆：某条转账路线（描述签名）已经配上过两次，或被用户手动确认过，
    #   以后同样描述的记录即使另一头的账单还没导入，也直接算内部转账。用户手动改回收支的签名永不套用。
    seen, veto = Counter(), set()
    for t in pool:
        s = sig(t["desc"])
        if not s:
            continue
        if is_tr(t) and (t["id"] in linked or t.get("locked")):
            seen[s] += 2 if t.get("locked") else 1
        elif t.get("locked") and t["kind"] != "transfer":
            veto.add(s)
    remembered = 0
    for t in pool:
        if candidate(t) and _HINT.search(t["desc"]):
            s = sig(t["desc"])
            if len(s.split()) >= 3 and s not in veto and seen[s] >= 2:   # 签名太短（如 “deposit ach”）不够特定，不记
                mark.add(t["id"])
                remembered += 1
    if remembered:
        pair()

    for tid in mark:
        store.update_transaction(tid, {"kind": "transfer", "category": TRANSFER_CATEGORY})
    LAST.update(pairs=new_pairs[0], remembered=remembered,
                pending=sum(1 for t in pool if is_tr(t) and t["id"] not in linked))
    return len(mark) + _refunds() + _propagate()


def payer(desc: str) -> str:
    """付款 / 收款方的前两个词（去掉 ELECTRONIC DEPOSIT 之类的通道前缀），用于跨账户认出同一对象。"""
    s = _PAYER_PREFIX.sub("", (desc or "").split(" · ")[0].strip())
    words = re.findall(r"[a-z\u4e00-\u9fff]{2,}", s.lower())
    return " ".join(words[:2]) if len(words) >= 2 else ""


def _propagate() -> int:
    """同一对象在别处已有明确分类（如某账户上的 “ACME CORP … SALARY” 是工资、
    “MAPLE COURT … RENT” 是房租），就把其他账户里同一对象的“其他 / 转账收入”也归过去。"""
    vague = {"其他支出", "其他收入", "转账收入"}
    txns = [t for t in store.all_transactions() if t["kind"] in ("income", "expense")]
    known = {}
    for t in txns:
        p = payer(t["desc"])
        if p and t["category"] not in vague:
            known.setdefault((t["kind"], p), t["category"])
    n = 0
    for t in txns:
        if t.get("locked") or t["category"] not in vague:
            continue
        c = known.get((t["kind"], payer(t["desc"])))
        if c:
            store.update_transaction(t["id"], {"category": c})
            n += 1
    return n


def _refunds() -> int:
    """退款处理：
    - 同一账户里找得到金额相同、同一商户、120 天内的原消费 → 两笔都标“已退货”，不计收支；
    - 其余退款 / 返现 → kind=refund，冲减对应分类的支出，不算收入。
    报销、退税属于真实入账，保持为收入。"""
    txns = [t for t in store.all_transactions() if not t.get("locked")]
    spend = defaultdict(list)
    for t in txns:
        if t["kind"] == "expense":
            spend[(_key(t), t["currency"], round(t["amount"] * 100))].append(t)
    used, n = set(), 0
    for r in txns:
        if r["kind"] != "income" or r["category"] != "退款报销" or _TAX.search(r["desc"] or ""):
            continue
        match = None
        for p in spend.get((_key(r), r["currency"], round(r["amount"] * 100)), []):
            if p["id"] in used or p["date"] > r["date"] or _days(p["date"], r["date"]) > 120:
                continue
            if _brand(p["desc"]) and _brand(p["desc"]) == _brand(r["desc"]):
                match = p
                break
        if match:
            used.add(match["id"])
            for t in (match, r):
                store.update_transaction(t["id"], {"kind": "transfer", "category": RETURNED})
            n += 2
        else:
            store.update_transaction(r["id"], {"kind": "refund", "category": categorize(r["desc"], "expense")})
            n += 1
    return n
