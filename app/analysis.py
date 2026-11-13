# -*- coding: utf-8 -*-
"""月度收支分析与建议引擎。

交易的 kind：
  income   真实收入          expense  真实消费
  refund   退款 / 返现，冲减所属分类的支出（不算收入）
  transfer 不计收支：内部转账（自己账户互转、信用卡还款）、已退货（买了又全额退掉）
所有统计只看 income / expense / refund。分类名是中文键，文案按 lang 生成（见 i18n.py）。
"""
import calendar
import datetime as dt
import re
from collections import defaultdict

import fx
import i18n
from categorize import FLEXIBLE

SYMBOLS = fx.SYMBOLS
FIXED_COST = {"住房物业", "超市日用", "餐饮美食", "交通出行"}
RETURNED = "已退货"


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
    return s[:22] or "—"


def _nice(x: float) -> float:
    if x >= 1000:
        return float(round(x / 50) * 50)
    if x >= 200:
        return float(round(x / 10) * 10)
    return float(round(x))


def months_available(txns):
    return sorted({t["date"][:7] for t in txns})


def analyze(txns: list, month: str, currency: str, lang: str = "zh") -> dict:
    if lang not in i18n.LANGS:
        lang = "zh"
    sym = SYMBOLS.get(currency, currency + " ")
    months = months_available(txns)

    by_month = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "cats": defaultdict(float),
                                    "icats": defaultdict(float), "txns": [], "refunds": [], "excluded": []})
    for t in txns:
        b = by_month[t["date"][:7]]
        if t["kind"] == "income":
            b["income"] += t["amount"]
            b["icats"][t["category"]] += t["amount"]
            b["txns"].append(t)
        elif t["kind"] == "expense":
            b["cats"][t["category"]] += t["amount"]
            b["txns"].append(t)
        elif t["kind"] == "refund":
            b["cats"][t["category"]] -= t["amount"]
            b["refunds"].append(t)
        else:
            b["excluded"].append(t)
    for b in by_month.values():  # 退款冲减后，分类不为负；总支出 = 各分类之和
        for k in list(b["cats"]):
            b["cats"][k] = max(0.0, b["cats"][k])
        b["expense"] = sum(b["cats"].values())

    cur = by_month[month]
    prev_m = _add_month(month, -1)
    prev = by_month[prev_m] if prev_m in by_month and (by_month[prev_m]["txns"]) else None
    hist_months = [m for m in (_add_month(month, -i) for i in (1, 2, 3)) if m in by_month and by_month[m]["txns"]]
    n_hist = len(hist_months)

    def avg(fn):
        return sum(fn(by_month[m]) for m in hist_months) / n_hist if n_hist else None

    income, expense = cur["income"], cur["expense"]
    net = income - expense
    sr = net / income if income > 0 else None
    exp_txns = [t for t in cur["txns"] if t["kind"] == "expense"]
    inc_txns = [t for t in cur["txns"] if t["kind"] == "income"]
    salary = cur["icats"].get("工资薪酬", 0.0)

    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    today = dt.date.today()
    is_current = (today.year, today.month) == (y, m)
    days_elapsed = today.day if is_current else days_in_month
    avg_exp, avg_inc = avg(lambda b: b["expense"]), avg(lambda b: b["income"])

    def ex_sum(pred):
        rows = [t for t in cur["excluded"] if pred(t)]
        return {"count": len(rows), "amount": round(sum(t["amount"] for t in rows), 2)}

    excluded = {
        "transfer": ex_sum(lambda t: t["category"] != RETURNED),
        "returned": ex_sum(lambda t: t["category"] == RETURNED),
        "refund": {"count": len(cur["refunds"]), "amount": round(sum(t["amount"] for t in cur["refunds"]), 2)},
    }

    kpi = {
        "income": round(income, 2), "expense": round(expense, 2), "net": round(net, 2),
        "salary": round(salary, 2),
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
              "expense": round(by_month[mm]["expense"], 2) if mm in by_month else 0,
              "salary": round(by_month[mm]["icats"].get("工资薪酬", 0.0), 2) if mm in by_month else 0}
             for mm in trend_months]
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
    top = [k for k, v in sorted(totals.items(), key=lambda kv: -kv[1])[:5] if v > 0]
    cat_trend = {"months": ct_months, "series": []}
    for name in top:
        cat_trend["series"].append({"name": name, "data": [
            round(by_month[mm]["cats"].get(name, 0.0), 2) if mm in by_month else 0 for mm in ct_months]})
    if len([v for v in totals.values() if v > 0]) > len(top):
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
    gross = sum(t["amount"] for t in exp_txns)
    weekend_share = (wd[5] + wd[6]) / gross if gross else 0

    acc = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "count": 0})
    for t in cur["txns"]:
        a = acc[t.get("account") or "—"]
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
                         "share": round(v["amount"] / gross * 100, 1) if gross else 0}
                        for k, v in mer.items()), key=lambda r: -r["amount"])[:10]

    top_expenses = [{"date": t["date"], "desc": t["desc"], "amount": t["amount"], "category": t["category"],
                     "account": t.get("account", "")}
                    for t in sorted(exp_txns, key=lambda t: -t["amount"])[:10]]

    # ---- 固定订阅 / 周期性支出 ----
    seen = defaultdict(lambda: defaultdict(list))
    for t in txns:
        if t["kind"] == "expense":
            seen[_merchant(t["desc"]).lower()][t["date"][:7]].append(t["amount"])
    recurring = []
    for name, per_month in seen.items():
        if month not in per_month:
            continue
        amts = [sum(v) for v in per_month.values()]
        mine = [t for t in exp_txns if _merchant(t["desc"]).lower() == name]
        cat = mine[0]["category"] if mine else ""
        steady = (len(per_month) >= 3 and max(amts) - min(amts) <= 0.05 * (sum(amts) / len(amts))
                  and all(len(v) == 1 for v in per_month.values()) and cat not in FIXED_COST)
        if cat == "通讯订阅" or steady:
            recurring.append({"name": _merchant(mine[0]["desc"]) if mine else name,
                              "amount": round(sum(per_month[month]), 2), "months": len(per_month)})
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
                       "avg3": r["avg3"], "save": round(save, 2), "flexible": r["name"] in FLEXIBLE})

    # ---- 健康分 ----
    M = lambda key, **kw: i18n.misc(key, lang, **kw)  # noqa: E731
    cat_amt = {r["name"]: r["amount"] for r in exp_cats}
    flex_share = sum(v for k, v in cat_amt.items() if k in FLEXIBLE) / expense if expense else 0
    fee_amt = cat_amt.get("金融费用", 0.0)
    parts = []
    if sr is not None:
        parts.append({"name": M("p_save"), "max": 40, "score": round(max(0, min(1, sr / 0.3)) * 40),
                      "note": M("n_save", sr=f"{sr * 100:.0f}")})
    if expense:
        if avg_exp:
            ratio = expense / avg_exp
            parts.append({"name": M("p_stable"), "max": 20, "score": round(max(0, min(1, (1.5 - ratio) / 0.5)) * 20),
                          "note": M("n_vs_avg", n=n_hist, pct=f"{ratio * 100:.0f}")})
        parts.append({"name": M("p_struct"), "max": 20, "score": round(max(0, min(1, (0.8 - flex_share) / 0.4)) * 20),
                      "note": M("n_flex", pct=f"{flex_share * 100:.0f}")})
        parts.append({"name": M("p_fee"), "max": 10,
                      "score": round(max(0, min(1, 1 - (fee_amt / expense) / 0.02)) * 10),
                      "note": M("n_fee0") if fee_amt == 0 else M("n_fee", amt=f"{sym}{fee_amt:,.0f}")})
    if income and avg_inc:
        ratio = income / avg_inc
        parts.append({"name": M("p_income"), "max": 10, "score": round(max(0, min(1, (ratio - 0.6) / 0.35)) * 10),
                      "note": M("n_vs_avg", n=n_hist, pct=f"{ratio * 100:.0f}")})
    score = round(sum(p["score"] for p in parts) / sum(p["max"] for p in parts) * 100) if parts else None

    advice = _advice(lang, sym, currency, sr, income, expense, net, exp_cats, inc_cats, cat_amt, exp_txns,
                     recurring, weekend_share, fee_amt, avg_exp, avg_inc, n_hist, potential, prev,
                     days_elapsed, days_in_month, is_current)

    return {
        "month": month, "currency": currency, "symbol": sym, "months": months, "lang": lang,
        "has_data": bool(cur["txns"] or cur["refunds"] or cur["excluded"]), "kpi": kpi, "excluded": excluded,
        "expense_cats": [r for r in exp_cats if r["amount"] > 0 or (r["avg3"] or 0) > 0],
        "income_cats": [r for r in inc_cats if r["amount"] > 0 or (r["avg3"] or 0) > 0],
        "trend": trend, "cat_trend": cat_trend, "daily": daily_data,
        "weekday": [round(v, 2) for v in wd],
        "accounts": accounts, "merchants": merchants, "top_expenses": top_expenses,
        "recurring": recurring[:12], "budget": budget, "saving_potential": round(potential, 2),
        "score": {"total": score, "parts": parts}, "advice": advice,
    }


def _advice(lang, sym, currency, sr, income, expense, net, exp_cats, inc_cats, cat_amt, exp_txns, recurring,
            weekend_share, fee_amt, avg_exp, avg_inc, n_hist, potential, prev, days_elapsed, days_in_month,
            is_current):
    """生成可执行的建议。每条：级别、结论、依据、做法，以及“现状 vs 目标”的度量供界面画进度条。"""
    out = []
    C = lambda name: i18n.cat(name, lang)  # noqa: E731
    M = lambda key: i18n.misc(key, lang)  # noqa: E731

    def money(v):
        return f"{sym}{v:,.0f}"

    def add(level, key, metric=None, **kw):
        title, detail, action = i18n.adv(key, lang, **kw)
        out.append({"level": level, "key": key, "title": title, "detail": detail, "action": action, "metric": metric})

    def metric(label, current, target, unit="money", lower=True):
        return {"label": label, "current": round(current, 2), "target": round(target, 2), "unit": unit,
                "lower_better": lower}

    if not expense and not income:
        return out

    # 1. 储蓄率
    if sr is None:
        add("info", "no_income")
    elif sr < 0:
        add("alert", "overspend", metric(M("m_exp_inc"), expense, income), over=money(-net), income=money(income),
            expense=money(expense), ratio=f"{expense / income * 100:.0f}", potential=money(potential))
    else:
        key, level = ("low_save", "warn") if sr < 0.1 else ("near_save", "info") if sr < 0.2 else ("good_save", "good")
        add(level, key, metric(M("m_sr"), sr * 100, 20, "pct", False), sr=f"{sr * 100:.0f}", net=money(net),
            gap=money(max(income * 0.2 - net, 0)))

    # 2. 总支出对比
    if avg_exp and expense:
        diff = expense - avg_exp
        if diff > avg_exp * 0.15:
            drivers = sorted((r for r in exp_cats if r["avg3"] is not None and r["amount"] - r["avg3"] > 0),
                             key=lambda r: -(r["amount"] - r["avg3"]))[:3]
            dtxt = M("sep").join(f'{C(r["name"])} (+{money(r["amount"] - r["avg3"])})' for r in drivers)
            add("warn", "exp_up", metric(M("m_exp_avg"), expense, avg_exp), n=n_hist,
                pct=f"{diff / avg_exp * 100:.0f}", expense=money(expense), avg=money(avg_exp), diff=money(diff),
                drivers=dtxt or M("many_small"))
        elif diff < -avg_exp * 0.1:
            add("good", "exp_down", metric(M("m_exp_avg"), expense, avg_exp), n=n_hist,
                pct=f"{-diff / avg_exp * 100:.0f}", expense=money(expense), avg=money(avg_exp), diff=money(-diff))

    # 3. 单类异常上涨
    for r in exp_cats:
        base = r["avg3"]
        if not base or r["name"] == "其他支出":
            continue
        up = r["amount"] - base
        if up > base * 0.3 and r["amount"] >= expense * 0.05 and up >= expense * 0.02:
            cap = _nice(base * 1.05)
            flexible = r["name"] in FLEXIBLE
            add("warn" if flexible else "info", "cat_up_flex" if flexible else "cat_up_ess",
                metric(C(r["name"]), r["amount"], cap), cat=C(r["name"]), pct=f"{up / base * 100:.0f}",
                amount=money(r["amount"]), count=r["count"], base=money(base), up=money(up), cap=money(cap))

    # 4. 结构性占比
    ref_amt, ref_name = (income, M("of_income")) if income else (expense, M("of_expense"))
    limits = {"餐饮美食": (0.25, 0.35), "住房物业": (0.35, 0.5), "购物消费": (0.15, 0.25), "娱乐休闲": (0.10, 0.15)}
    for name, (li, le) in limits.items():
        amt, limit = cat_amt.get(name, 0.0), (li if income else le)
        if ref_amt and amt / ref_amt > limit:
            target = _nice(ref_amt * limit)
            add("warn", "share", metric(C(name), amt, target), cat=C(name), base_name=ref_name,
                pct=f"{amt / ref_amt * 100:.0f}", amount=money(amt), limit=f"{limit * 100:.0f}",
                target=money(target), tip=i18n.tip(name, lang))

    # 5. 订阅
    if recurring:
        total = sum(r["amount"] for r in recurring)
        if len(recurring) >= 3 or (expense and total / expense > 0.05):
            names = M("sep").join(r["name"] for r in recurring[:5]) + (M("etc") if len(recurring) > 5 else "")
            add("info", "subs", metric(M("m_fixed"), total, _nice(total * 0.7)), n=len(recurring),
                total=money(total), names=names, year=money(total * 12))

    # 6. 小额高频
    small_cap = 30 if currency == "CNY" else (8 if currency in ("USD", "EUR", "GBP") else
                                              _nice(8 * fx.BUILTIN["rates"].get(currency, 1)))  # 约 8 美元
    small = [t for t in exp_txns if t["amount"] <= small_cap
             and t["category"] in ("餐饮美食", "购物消费", "娱乐休闲", "超市日用", "其他支出")]
    if len(small) >= 15 and expense:
        s = sum(t["amount"] for t in small)
        add("info", "small", metric(M("m_small"), s, _nice(s * 2 / 3)), n=len(small), sum=money(s),
            cap=f"{sym}{small_cap}", share=f"{s / expense * 100:.0f}",
            perday=f"{len(small) / max(days_elapsed, 1):.1f}", save=money(s / 3))

    # 7. 大额单笔
    if exp_txns and expense:
        big = max(exp_txns, key=lambda t: t["amount"])
        if big["amount"] > expense * 0.2 and len(exp_txns) >= 5:
            add("info", "big", pct=f"{big['amount'] / expense * 100:.0f}", date=big["date"][5:],
                desc=big["desc"][:24], amount=money(big["amount"]), cat=C(big["category"]))

    # 8. 手续费 / 利息
    if fee_amt > 0:
        add("warn", "fees", metric(M("m_fees"), fee_amt, 0), amount=money(fee_amt))

    # 9. 周末集中
    if expense and weekend_share > 0.45 and len(exp_txns) >= 10:
        add("info", "weekend", pct=f"{weekend_share * 100:.0f}")

    # 10. 收入变化
    if income and avg_inc:
        ch = (income - avg_inc) / avg_inc
        if ch < -0.15:
            add("alert", "inc_down", metric(M("m_inc_avg"), income, avg_inc, lower=False), n=n_hist,
                pct=f"{-ch * 100:.0f}", income=money(income), avg=money(avg_inc))
        elif ch > 0.2:
            add("good", "inc_up", n=n_hist, pct=f"{ch * 100:.0f}", income=money(income), avg=money(avg_inc),
                extra=money(income - avg_inc))
    if income and inc_cats:
        top = max(inc_cats, key=lambda r: r["amount"])
        if top["name"] in ("转账收入", "其他收入") and top["amount"] / income > 0.6:
            add("info", "inc_other", cat=C(top["name"]), pct=f"{top['amount'] / income * 100:.0f}")

    # 11. 月中进度（房租等一次性大额不按天外推）
    if is_current and days_elapsed < days_in_month and expense and days_elapsed >= 5:
        base = avg_exp or (prev["expense"] if prev else None)
        if base:
            lump = sum(t["amount"] for t in exp_txns if t["amount"] > base * 0.08)
            proj = lump + max(expense - lump, 0) / days_elapsed * days_in_month
            left = days_in_month - days_elapsed
            warn = proj > base * 1.1
            add("warn" if warn else "good", "pace_warn" if warn else "pace_ok", metric(M("m_proj"), proj, base),
                proj=money(proj), d=days_elapsed, dm=days_in_month, expense=money(expense), base=money(base),
                left=left, perday=money(max(base - expense, 0) / left))

    # 12. 应急金
    base_exp = avg_exp or expense
    if base_exp:
        if net > 0:
            add("info", "efund_pos", lo=money(base_exp * 3), hi=money(base_exp * 6), base=money(base_exp),
                net=money(net), months=f"{base_exp * 3 / net:.0f}")
        else:
            add("info", "efund_neg", lo=money(base_exp * 3), hi=money(base_exp * 6), base=money(base_exp))

    # 13. 数据不足提示
    if n_hist == 0:
        add("info", "more_data")

    order = {"alert": 0, "warn": 1, "info": 2, "good": 3}
    out.sort(key=lambda a: order[a["level"]])
    return out
