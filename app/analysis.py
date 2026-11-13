# -*- coding: utf-8 -*-
"""月度收支分析与建议引擎。所有统计都不含“内部转账”（信用卡还款、自己账户互转等）。"""
import calendar
import datetime as dt
import re
from collections import defaultdict

from categorize import ESSENTIAL, FLEXIBLE

SYMBOLS = {"CNY": "¥", "USD": "$", "HKD": "HK$", "EUR": "€", "GBP": "£"}
FIXED_COST = {"住房物业", "超市日用", "餐饮美食", "交通出行"}
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _add_month(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    k = y * 12 + (m - 1) + n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def _pct(cur, base):
    if not base:
        return None
    return round((cur - base) / base * 100, 1)


def _merchant(desc: str) -> str:
    s = (desc or "").split(" · ")[0]
    s = re.sub(r"[#*]?\d{3,}", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/|*")
    return s[:22] or "(无描述)"


def _nice(x: float) -> float:
    if x >= 1000:
        return float(round(x / 50) * 50)
    if x >= 200:
        return float(round(x / 10) * 10)
    return float(round(x))


def months_available(txns):
    return sorted({t["date"][:7] for t in txns})


def analyze(txns: list, month: str, currency: str) -> dict:
    sym = SYMBOLS.get(currency, currency + " ")
    months = months_available(txns)
    real = [t for t in txns if t["kind"] in ("income", "expense")]

    by_month = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "cats": defaultdict(float),
                                    "icats": defaultdict(float), "txns": []})
    for t in real:
        b = by_month[t["date"][:7]]
        b[t["kind"]] += t["amount"]
        (b["cats"] if t["kind"] == "expense" else b["icats"])[t["category"]] += t["amount"]
        b["txns"].append(t)

    cur = by_month[month]
    prev_m = _add_month(month, -1)
    prev = by_month[prev_m] if prev_m in by_month else None
    hist_months = [m for m in (_add_month(month, -i) for i in (1, 2, 3)) if m in by_month and by_month[m]["txns"]]
    n_hist = len(hist_months)

    def avg(fn):
        return sum(fn(by_month[m]) for m in hist_months) / n_hist if n_hist else None

    income, expense = cur["income"], cur["expense"]
    net = income - expense
    sr = net / income if income > 0 else None
    exp_txns = [t for t in cur["txns"] if t["kind"] == "expense"]
    inc_txns = [t for t in cur["txns"] if t["kind"] == "income"]

    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    today = dt.date.today()
    is_current = (today.year, today.month) == (y, m)
    days_elapsed = today.day if is_current else days_in_month
    avg_exp, avg_inc = avg(lambda b: b["expense"]), avg(lambda b: b["income"])

    kpi = {
        "income": round(income, 2), "expense": round(expense, 2), "net": round(net, 2),
        "savings_rate": round(sr * 100, 1) if sr is not None else None,
        "count": len(cur["txns"]), "expense_count": len(exp_txns), "income_count": len(inc_txns),
        "daily_avg": round(expense / max(days_elapsed, 1), 2),
        "prev_month": prev_m if prev else None,
        "prev_income": round(prev["income"], 2) if prev else None,
        "prev_expense": round(prev["expense"], 2) if prev else None,
        "prev_net": round(prev["income"] - prev["expense"], 2) if prev else None,
        "income_change": _pct(income, prev["income"]) if prev else None,
        "expense_change": _pct(expense, prev["expense"]) if prev else None,
        "avg3_income": round(avg_inc, 2) if avg_inc is not None else None,
        "avg3_expense": round(avg_exp, 2) if avg_exp is not None else None,
        "hist_months": n_hist, "is_current": is_current, "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
    }

    # ---- 分类表 ----
    def cat_table(key, total, count_src):
        names = set(cur[key])
        for hm in hist_months:
            names |= set(by_month[hm][key])
        rows = []
        for name in names:
            amt = cur[key].get(name, 0.0)
            p = prev[key].get(name, 0.0) if prev else None
            a3 = sum(by_month[hm][key].get(name, 0.0) for hm in hist_months) / n_hist if n_hist else None
            rows.append({
                "name": name, "amount": round(amt, 2),
                "share": round(amt / total * 100, 1) if total else 0,
                "count": sum(1 for t in count_src if t["category"] == name),
                "prev": round(p, 2) if p is not None else None,
                "avg3": round(a3, 2) if a3 is not None else None,
                "change": _pct(amt, p) if p else None,
                "vs_avg": _pct(amt, a3) if a3 else None,
            })
        rows.sort(key=lambda r: (-r["amount"], -(r["avg3"] or 0)))
        return rows

    exp_cats = cat_table("cats", expense, exp_txns)
    inc_cats = cat_table("icats", income, inc_txns)

    # ---- 近 12 个月趋势 ----
    first = months[0] if months else month
    trend_months = [mm for mm in (_add_month(month, -i) for i in range(11, -1, -1)) if mm >= first]
    trend = [{"month": mm, "income": round(by_month[mm]["income"], 2) if mm in by_month else 0,
              "expense": round(by_month[mm]["expense"], 2) if mm in by_month else 0} for mm in trend_months]
    for r in trend:
        r["net"] = round(r["income"] - r["expense"], 2)
        r["savings_rate"] = round(r["net"] / r["income"] * 100, 1) if r["income"] else None

    # ---- 分类趋势（近 6 个月，前 5 类 + 其他）----
    ct_months = trend_months[-6:]
    totals = defaultdict(float)
    for mm in ct_months:
        if mm in by_month:
            for k, v in by_month[mm]["cats"].items():
                totals[k] += v
    top = [k for k, _ in sorted(totals.items(), key=lambda kv: -kv[1])[:5]]
    cat_trend = {"months": ct_months, "series": []}
    for name in top:
        cat_trend["series"].append({"name": name, "data": [
            round(by_month[mm]["cats"].get(name, 0.0), 2) if mm in by_month else 0 for mm in ct_months]})
    if len(totals) > len(top):
        cat_trend["series"].append({"name": "其他", "data": [
            round(sum(v for k, v in by_month[mm]["cats"].items() if k not in top), 2) if mm in by_month else 0
            for mm in ct_months]})

    # ---- 每日支出与累计（对比上月）----
    def daily(bucket, ndays):
        arr = [0.0] * ndays
        if bucket:
            for t in bucket["txns"]:
                if t["kind"] == "expense":
                    d = int(t["date"][8:10])
                    if d <= ndays:
                        arr[d - 1] += t["amount"]
        return arr

    d_cur = daily(cur, days_in_month)
    py, pm = int(prev_m[:4]), int(prev_m[5:7])
    d_prev = daily(prev, calendar.monthrange(py, pm)[1]) if prev else []

    def cum(arr, upto=None):
        out, s = [], 0.0
        for i, v in enumerate(arr):
            s += v
            out.append(round(s, 2) if upto is None or i < upto else None)
        return out

    daily_data = {
        "days": list(range(1, days_in_month + 1)),
        "daily": [round(v, 2) for v in d_cur],
        "cum": cum(d_cur, days_elapsed if is_current else None),
        "prev_cum": (cum(d_prev) + [None] * 31)[:days_in_month] if prev else None,
    }

    # ---- 星期分布 / 账户 / 商户 / 大额 ----
    wd = [0.0] * 7
    for t in exp_txns:
        wd[dt.date.fromisoformat(t["date"]).weekday()] += t["amount"]
    weekend_share = (wd[5] + wd[6]) / expense if expense else 0

    acc = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "count": 0})
    for t in cur["txns"]:
        a = acc[t.get("account") or "未命名账户"]
        a[t["kind"]] += t["amount"]
        a["count"] += 1
    accounts = sorted(({"name": k, "income": round(v["income"], 2), "expense": round(v["expense"], 2),
                        "count": v["count"]} for k, v in acc.items()), key=lambda r: -(r["expense"] + r["income"]))

    mer = defaultdict(lambda: {"amount": 0.0, "count": 0, "category": ""})
    for t in exp_txns:
        e = mer[_merchant(t["desc"])]
        e["amount"] += t["amount"]
        e["count"] += 1
        e["category"] = t["category"]
    merchants = sorted(({"name": k, "amount": round(v["amount"], 2), "count": v["count"],
                         "category": v["category"],
                         "share": round(v["amount"] / expense * 100, 1) if expense else 0}
                        for k, v in mer.items()), key=lambda r: -r["amount"])[:10]

    top_expenses = [{"date": t["date"], "desc": t["desc"], "amount": t["amount"], "category": t["category"],
                     "account": t.get("account", "")}
                    for t in sorted(exp_txns, key=lambda t: -t["amount"])[:10]]

    # ---- 固定订阅 / 周期性支出 ----
    seen = defaultdict(lambda: defaultdict(list))
    for t in real:
        if t["kind"] == "expense":
            seen[_merchant(t["desc"]).lower()][t["date"][:7]].append(t["amount"])
    recurring = []
    for name, per_month in seen.items():
        if month not in per_month:
            continue
        amts = [sum(v) for v in per_month.values()]
        in_sub = any(t["category"] == "通讯订阅" and _merchant(t["desc"]).lower() == name for t in exp_txns)
        cat = next((t["category"] for t in exp_txns if _merchant(t["desc"]).lower() == name), "")
        steady = (len(per_month) >= 3 and max(amts) - min(amts) <= 0.05 * (sum(amts) / len(amts))
                  and all(len(v) == 1 for v in per_month.values()) and cat not in FIXED_COST)
        if in_sub or steady:
            disp = next((_merchant(t["desc"]) for t in exp_txns if _merchant(t["desc"]).lower() == name), name)
            recurring.append({"name": disp, "amount": round(sum(per_month[month]), 2), "months": len(per_month)})
    recurring.sort(key=lambda r: -r["amount"])

    # ---- 预算建议 ----
    tighten = 1.0 if (sr is not None and sr >= 0.2) else (0.9 if (sr is not None and sr >= 0.1) else 0.85)
    budget, potential = [], 0.0
    for r in exp_cats:
        cur_amt, base = r["amount"], (r["avg3"] if r["avg3"] else r["amount"])
        if r["name"] in FLEXIBLE:
            ref = min(cur_amt, base) if cur_amt > 0 else base
            sug = ref * tighten
        else:
            sug = min(cur_amt, base * 1.05) if cur_amt > 0 else base
        sug = _nice(sug)
        if cur_amt <= 0 and sug <= 0:
            continue
        save = max(0.0, cur_amt - sug)
        potential += save
        budget.append({"name": r["name"], "current": r["amount"], "suggested": sug,
                       "avg3": r["avg3"], "save": round(save, 2),
                       "flexible": r["name"] in FLEXIBLE})

    # ---- 健康分 ----
    cat_amt = {r["name"]: r["amount"] for r in exp_cats}
    flex_amt = sum(v for k, v in cat_amt.items() if k in FLEXIBLE)
    flex_share = flex_amt / expense if expense else 0
    fee_amt = cat_amt.get("金融费用", 0.0)
    parts = []
    if sr is not None:
        parts.append({"name": "储蓄能力", "max": 40, "score": round(max(0, min(1, sr / 0.3)) * 40),
                      "note": f"储蓄率 {sr * 100:.0f}%（目标 ≥ 20%）"})
    if expense:
        if avg_exp:
            ratio = expense / avg_exp
            parts.append({"name": "支出稳定", "max": 20, "score": round(max(0, min(1, (1.5 - ratio) / 0.5)) * 20),
                          "note": f"为近 {n_hist} 月均值的 {ratio * 100:.0f}%"})
        parts.append({"name": "消费结构", "max": 20, "score": round(max(0, min(1, (0.8 - flex_share) / 0.4)) * 20),
                      "note": f"弹性消费占 {flex_share * 100:.0f}%"})
        parts.append({"name": "费用控制", "max": 10,
                      "score": round(max(0, min(1, 1 - (fee_amt / expense) / 0.02)) * 10),
                      "note": "无手续费/利息" if fee_amt == 0 else f"手续费/利息 {sym}{fee_amt:,.0f}"})
    if income and avg_inc:
        ratio = income / avg_inc
        parts.append({"name": "收入稳定", "max": 10, "score": round(max(0, min(1, (ratio - 0.6) / 0.35)) * 10),
                      "note": f"为近 {n_hist} 月均值的 {ratio * 100:.0f}%"})
    score = round(sum(p["score"] for p in parts) / sum(p["max"] for p in parts) * 100) if parts else None

    advice = _advice(sym, currency, month, kpi, sr, income, expense, net, exp_cats, inc_cats, cat_amt,
                     exp_txns, recurring, weekend_share, flex_share, fee_amt, avg_exp, avg_inc, n_hist,
                     potential, budget, prev, days_elapsed, days_in_month, is_current)

    return {
        "month": month, "currency": currency, "symbol": sym, "months": months,
        "has_data": bool(cur["txns"]), "kpi": kpi,
        "expense_cats": [r for r in exp_cats if r["amount"] > 0 or (r["avg3"] or 0) > 0],
        "income_cats": [r for r in inc_cats if r["amount"] > 0 or (r["avg3"] or 0) > 0],
        "trend": trend, "cat_trend": cat_trend, "daily": daily_data,
        "weekday": [{"name": WEEKDAYS[i], "amount": round(wd[i], 2)} for i in range(7)],
        "accounts": accounts, "merchants": merchants, "top_expenses": top_expenses,
        "recurring": recurring[:12], "budget": budget, "saving_potential": round(potential, 2),
        "score": {"total": score, "parts": parts}, "advice": advice,
    }


def _advice(sym, currency, month, kpi, sr, income, expense, net, exp_cats, inc_cats, cat_amt, exp_txns,
            recurring, weekend_share, flex_share, fee_amt, avg_exp, avg_inc, n_hist, potential, budget,
            prev, days_elapsed, days_in_month, is_current):
    """生成可执行的建议。每条：级别、结论、依据、具体做法，以及一个“现状 vs 目标”的度量供界面画图。"""
    out = []

    def money(v):
        return f"{sym}{v:,.0f}"

    def add(level, title, detail, action, metric=None):
        out.append({"level": level, "title": title, "detail": detail, "action": action, "metric": metric})

    if not expense and not income:
        return out

    # 1. 储蓄率
    if sr is None:
        add("info", "还没有本月的收入记录",
            "只导入了支出流水，无法计算结余和储蓄率。",
            "导入工资条、到账截图或含入账记录的流水（导入时选“收入凭证”），分析会更完整。")
    elif sr < 0:
        add("alert", f"本月入不敷出，超支 {money(-net)}",
            f"收入 {money(income)}，支出 {money(expense)}，支出是收入的 {expense / income * 100:.0f}%。",
            f"下月先把总支出压回收入以内：按下方“建议预算”执行可减少约 {money(potential)}；"
            "同时检查超支是否来自一次性大额（学费、房租押金等），若是则无需过度担心。",
            {"label": "支出 / 收入", "current": round(expense, 2), "target": round(income, 2), "unit": "money",
             "lower_better": True})
    elif sr < 0.1:
        add("warn", f"储蓄率偏低：{sr * 100:.0f}%",
            f"本月结余 {money(net)}。常用的参考线是把收入的 20% 留作储蓄。",
            f"要达到 20%，每月需再多留出 {money(income * 0.2 - net)}。建议发薪当天先把这笔钱转入单独的储蓄账户，剩下的再用于开销。",
            {"label": "储蓄率", "current": round(sr * 100, 1), "target": 20, "unit": "pct", "lower_better": False})
    elif sr < 0.2:
        add("info", f"储蓄率 {sr * 100:.0f}%，接近 20% 目标",
            f"本月结余 {money(net)}，再多留 {money(income * 0.2 - net)} 即可达标。",
            "从弹性最大的一两类开销里各减一点，比全面压缩更容易坚持。",
            {"label": "储蓄率", "current": round(sr * 100, 1), "target": 20, "unit": "pct", "lower_better": False})
    else:
        add("good", f"储蓄率 {sr * 100:.0f}%，状态健康",
            f"本月结余 {money(net)}，已超过 20% 的参考线。",
            "保持当前节奏。结余可以按“应急金 → 定期/货币基金 → 长期投资”的顺序安排。",
            {"label": "储蓄率", "current": round(sr * 100, 1), "target": 20, "unit": "pct", "lower_better": False})

    # 2. 总支出对比
    if avg_exp and expense:
        diff = expense - avg_exp
        if diff > avg_exp * 0.15:
            drivers = sorted((r for r in exp_cats if r["avg3"] is not None and r["amount"] - r["avg3"] > 0),
                             key=lambda r: -(r["amount"] - r["avg3"]))[:3]
            dtxt = "、".join(f'{r["name"]}（+{money(r["amount"] - r["avg3"])}）' for r in drivers)
            add("warn", f"总支出比近 {n_hist} 个月均值高 {diff / avg_exp * 100:.0f}%",
                f"本月 {money(expense)}，此前月均 {money(avg_exp)}，多花了 {money(diff)}。主要来自：{dtxt or '多个类别小幅上涨'}。",
                "逐项看这几类里是否有一次性支出；属于习惯性上涨的，下月按建议预算设上限。",
                {"label": "本月支出 vs 月均", "current": round(expense, 2), "target": round(avg_exp, 2),
                 "unit": "money", "lower_better": True})
        elif diff < -avg_exp * 0.1:
            add("good", f"总支出比近 {n_hist} 个月均值低 {-diff / avg_exp * 100:.0f}%",
                f"本月 {money(expense)}，此前月均 {money(avg_exp)}，少花了 {money(-diff)}。",
                "把省下的部分直接转入储蓄，避免下月被“报复性消费”抵消。",
                {"label": "本月支出 vs 月均", "current": round(expense, 2), "target": round(avg_exp, 2),
                 "unit": "money", "lower_better": True})

    # 3. 单类异常上涨
    for r in exp_cats:
        base = r["avg3"]
        if not base or r["name"] in ("其他支出",):
            continue
        up = r["amount"] - base
        if up > base * 0.3 and r["amount"] >= expense * 0.05 and up >= expense * 0.02:
            cap = _nice(base * 1.05)
            flexible = r["name"] in FLEXIBLE
            add("warn" if flexible else "info",
                f"{r['name']}上涨 {up / base * 100:.0f}%",
                f"本月 {money(r['amount'])}（{r['count']} 笔），此前月均 {money(base)}，多出 {money(up)}。",
                (f"这是弹性开销，下月建议控制在 {money(cap)} 以内。" if flexible else
                 "这类属于必需开销，先确认是否为一次性（如年付、押金）；若是持续上涨，考虑换更便宜的方案。"),
                {"label": r["name"], "current": r["amount"], "target": cap, "unit": "money", "lower_better": True})

    # 4. 结构性占比
    def share_rule(cat, limit, base_amt, base_name, tip):
        amt = cat_amt.get(cat, 0.0)
        if base_amt and amt / base_amt > limit:
            target = _nice(base_amt * limit)
            add("warn", f"{cat}占{base_name}的 {amt / base_amt * 100:.0f}%，偏高",
                f"本月{cat} {money(amt)}，一般建议不超过{base_name}的 {limit * 100:.0f}%（约 {money(target)}）。",
                tip, {"label": cat, "current": round(amt, 2), "target": target, "unit": "money",
                      "lower_better": True})

    ref_amt, ref_name = (income, "收入") if income else (expense, "总支出")
    share_rule("餐饮美食", 0.25 if income else 0.35, ref_amt, ref_name,
               "外卖和堂食是最容易压缩的一项：每周固定 2–3 天自己做饭或带饭，通常能省下 20%–30%。")
    share_rule("住房物业", 0.35 if income else 0.5, ref_amt, ref_name,
               "住房成本短期难降。续租时可以比较合租/更远一站的房源，或核对水电网套餐是否有更优惠的档位。")
    share_rule("购物消费", 0.15 if income else 0.25, ref_amt, ref_name,
               "给非必需购物设“24 小时冷静期”：先加购物车，隔天还想要再下单。")
    share_rule("娱乐休闲", 0.10 if income else 0.15, ref_amt, ref_name,
               "给娱乐设一个固定月额度，用完即止；游戏充值、直播打赏建议关闭免密支付。")

    # 5. 订阅
    if recurring:
        total = sum(r["amount"] for r in recurring)
        names = "、".join(r["name"] for r in recurring[:5])
        if len(recurring) >= 3 or (expense and total / expense > 0.05):
            add("info", f"发现 {len(recurring)} 项固定扣费，合计 {money(total)}/月",
                f"包括：{names}{' 等' if len(recurring) > 5 else ''}。一年约 {money(total * 12)}。",
                "逐项问自己“过去 30 天用过吗？”，没用过的直接退订；视频/音乐类可以改成需要时再开一个月。",
                {"label": "固定扣费", "current": round(total, 2), "target": _nice(total * 0.7), "unit": "money",
                 "lower_better": True})

    # 6. 小额高频
    small_cap = 30 if currency == "CNY" else (8 if currency in ("USD", "EUR", "GBP") else 60)
    small = [t for t in exp_txns if t["amount"] <= small_cap and t["category"] in ("餐饮美食", "购物消费", "娱乐休闲", "超市日用", "其他支出")]
    if len(small) >= 15:
        s = sum(t["amount"] for t in small)
        add("info", f"{len(small)} 笔小额消费累计 {money(s)}",
            f"单笔不超过 {sym}{small_cap} 的零散支出（咖啡、奶茶、零食、小件）占总支出的 {s / expense * 100:.0f}%，"
            f"平均每天 {len(small) / max(days_elapsed, 1):.1f} 笔。",
            f"不用全戒：把频率减掉三分之一，一个月就能省约 {money(s / 3)}。",
            {"label": "小额消费", "current": round(s, 2), "target": _nice(s * 2 / 3), "unit": "money",
             "lower_better": True})

    # 7. 大额单笔
    if exp_txns and expense:
        big = max(exp_txns, key=lambda t: t["amount"])
        if big["amount"] > expense * 0.2 and len(exp_txns) >= 5:
            add("info", f"单笔最大支出占全月 {big['amount'] / expense * 100:.0f}%",
                f"{big['date'][5:]} {big['desc'][:24]}：{money(big['amount'])}（{big['category']}）。",
                "如果是房租、学费这类可预见的大额支出，建议每月提前预留等额资金，避免集中支付时现金吃紧。")

    # 8. 手续费 / 利息
    if fee_amt > 0:
        add("warn", f"本月支付手续费/利息 {money(fee_amt)}",
            "这类支出没有换来任何商品或服务，是最应该先消掉的一项。",
            "信用卡设全额自动还款避免利息；跨行/境外取现改用免手续费的卡；有年费的卡确认是否达到免年费条件。",
            {"label": "手续费/利息", "current": round(fee_amt, 2), "target": 0, "unit": "money", "lower_better": True})

    # 9. 周末集中
    if expense and weekend_share > 0.45 and len(exp_txns) >= 10:
        add("info", f"周末花掉了全月的 {weekend_share * 100:.0f}%",
            "两天的开销接近或超过五个工作日的总和，支出集中在周末的聚餐、购物和娱乐。",
            "周末出门前先定一个当日上限；聚餐与购物尽量不安排在同一天。")

    # 10. 收入变化
    if income and avg_inc:
        ch = (income - avg_inc) / avg_inc
        if ch < -0.15:
            add("alert", f"收入比近 {n_hist} 个月均值少 {-ch * 100:.0f}%",
                f"本月 {money(income)}，此前月均 {money(avg_inc)}。",
                "先确认是否有收入尚未到账或未导入；若确实下降，下月的弹性开销建议同比例下调。",
                {"label": "本月收入 vs 月均", "current": round(income, 2), "target": round(avg_inc, 2),
                 "unit": "money", "lower_better": False})
        elif ch > 0.2:
            add("good", f"收入比近 {n_hist} 个月均值高 {ch * 100:.0f}%",
                f"本月 {money(income)}，此前月均 {money(avg_inc)}。",
                f"多出来的 {money(income - avg_inc)} 建议至少存下一半，避免开销随收入同步上涨。")
    if income and len(inc_cats) >= 1:
        top = max(inc_cats, key=lambda r: r["amount"])
        if top["name"] in ("转账收入", "其他收入") and top["amount"] / income > 0.6:
            add("info", "大部分收入被归为“转账/其他”",
                f"{top['name']}占收入的 {top['amount'] / income * 100:.0f}%，可能包含亲友转账、自己账户互转等。",
                "在“交易明细”里把不属于真实收入的记录改为“内部转账”，储蓄率才会准确。")

    # 11. 月中进度
    if is_current and days_elapsed < days_in_month and expense and days_elapsed >= 5:
        base = avg_exp or (prev["expense"] if prev else None)
        # 房租等一次性大额不按天外推，只外推日常开销
        lump = sum(t["amount"] for t in exp_txns if t["amount"] > (base or expense) * 0.08)
        proj = lump + (expense - lump) / days_elapsed * days_in_month
        if base:
            lvl = "warn" if proj > base * 1.1 else "good"
            add(lvl, f"按目前节奏，本月预计支出 {money(proj)}",
                f"已过 {days_elapsed}/{days_in_month} 天，花了 {money(expense)}；参考值（往月）为 {money(base)}。",
                (f"剩余 {days_in_month - days_elapsed} 天日均控制在 {money(max(base - expense, 0) / (days_in_month - days_elapsed))} 以内，才能与往月持平。"
                 if proj > base * 1.1 else "进度正常，保持即可。"),
                {"label": "预计全月支出", "current": round(proj, 2), "target": round(base, 2), "unit": "money",
                 "lower_better": True})

    # 12. 应急金
    base_exp = avg_exp or expense
    if base_exp:
        add("info", f"应急金参考：{money(base_exp * 3)} – {money(base_exp * 6)}",
            f"按月均支出 {money(base_exp)} 计算，建议常备 3–6 个月的生活费，放在随时可取的账户里。",
            (f"按本月结余 {money(net)} 的速度，约 {base_exp * 3 / net:.0f} 个月可以攒够 3 个月应急金。"
             if net > 0 else "当前没有结余，先实现收支平衡，再开始积累应急金。"))

    # 13. 数据不足提示
    if n_hist == 0:
        add("info", "再导入一两个月的数据，建议会更准",
            "目前只有这一个月的数据，无法判断哪些开销是“比平时多”。",
            "把前几个月的流水也导入进来，就能看到环比变化、趋势和更贴合你习惯的预算建议。")

    order = {"alert": 0, "warn": 1, "info": 2, "good": 3}
    out.sort(key=lambda a: order[a["level"]])
    return out
