# -*- coding: utf-8 -*-
"""流水分析助手 —— 程序入口。界面是内嵌网页（web/），通过 pywebview 与这里的 Api 通信。"""
import calendar
import datetime as dt
import json
import os
import random
import sys
import traceback

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import webview  # noqa: E402

import analysis  # noqa: E402
import parsers  # noqa: E402
import store  # noqa: E402
from categorize import (EXPENSE_CATEGORIES, INCOME_CATEGORIES, TRANSFER_CATEGORY, categorize,  # noqa: E402
                        rule_key)

import sync_server  # noqa: E402
import transfers  # noqa: E402

APP_NAME = "流水分析助手"
REPO_URL = "https://github.com/liliyawanttosleep/ledger-lens"
window = None


def _on_push(n):
    """手机推送了新记账：通知界面刷新。"""
    if window:
        window.evaluate_js(f"window.onPhonePush && window.onPhonePush({int(n)})")


def _dialog(kind):
    fd = getattr(webview, "FileDialog", None)
    if fd is not None:
        return getattr(fd, kind)
    return getattr(webview, f"{kind}_DIALOG")


def _norm_desc(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _enrich(txns, account, currency, learned, credit_card=False):
    names = transfers.owner_names() + transfers.learn_owner(t.get("desc", "") for t in txns)
    for t in txns:
        t["account"] = account
        t["currency"] = currency
        if t["kind"] != "transfer" and transfers.is_self(t.get("desc", ""), names):
            t["kind"] = "transfer"  # 对方是本人：自己账户间互转
        t["category"] = categorize(t.get("desc", ""), t["kind"], learned)
        if credit_card and t["kind"] == "income" and t["category"] in ("其他收入", "转账收入"):
            t["category"] = "退款报销"  # 信用卡上的入账只可能是退款 / 返现
    store.assign_hashes(txns)
    have = store.existing_hashes({t["hash"] for t in txns})
    near = {}
    for e in store.all_transactions(currency):
        if e["account"] == account:
            near.setdefault((e["date"], round(e["amount"] * 100)), []).append(_norm_desc(e["desc"]))
    for t in txns:
        d = _norm_desc(t.get("desc", ""))
        t["dup"] = t["hash"] in have or any(
            x[:10] == d[:10] for x in near.get((t["date"], round(t["amount"] * 100)), []))
    return txns


class Api:
    # ---------- 基础 ----------
    def bootstrap(self):
        txns = store.all_transactions()
        cur = {}
        for t in txns:
            c = cur.setdefault(t["currency"] or "CNY", {"count": 0, "months": set()})
            c["count"] += 1
            c["months"].add(t["date"][:7])
        currencies = [{"code": k, "symbol": analysis.SYMBOLS.get(k, k + " "), "count": v["count"],
                       "months": sorted(v["months"])}
                      for k, v in sorted(cur.items(), key=lambda kv: -kv[1]["count"])]
        return {
            "currencies": currencies, "total": len(txns),
            "expense_categories": EXPENSE_CATEGORIES, "income_categories": INCOME_CATEGORIES,
            "transfer_category": TRANSFER_CATEGORY,
            "accounts": sorted({t["account"] for t in txns if t["account"]}),
            "theme": store.get_setting("theme", "light"),
            "lang": store.get_setting("lang", "zh"),
            "today": dt.date.today().isoformat(),
        }

    def set_theme(self, theme):
        store.set_setting("theme", theme)

    def set_lang(self, lang):
        store.set_setting("lang", lang if lang in analysis.i18n.LANGS else "zh")

    # ---------- 导入 ----------
    def pick_files(self):
        types = ("账单与凭证 (*.pdf;*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.gif;*.tif;*.tiff;*.csv;*.tsv;*.txt;"
                 "*.xlsx;*.xlsm;*.xls;*.docx;*.html;*.htm;*.ofx;*.qfx;*.qbo)", "所有文件 (*.*)")
        res = window.create_file_dialog(_dialog("OPEN"), allow_multiple=True, file_types=types)
        return list(res) if res else []

    def parse_file(self, path, mode="auto", password=None):
        name = os.path.basename(path)
        try:
            if not os.path.isfile(path):
                return {"file": name, "path": path, "error": "找不到这个文件"}
            res = parsers.parse_file(path, mode, password)
        except parsers.NeedPassword:
            return {"file": name, "path": path, "need_password": True}
        except Exception as e:  # 任何单个文件失败都不能影响其他文件
            traceback.print_exc()
            return {"file": name, "path": path, "error": f"无法解析：{e}"}
        _enrich(res["txns"], res["account"], res["currency"], store.learned_rules(), res.get("credit_card"))
        res["mode"] = mode
        return res

    def commit_import(self, batch):
        txns = []
        for t in batch.get("txns", []):
            try:
                d = dt.date.fromisoformat(str(t["date"])[:10]).isoformat()
                amt = round(abs(float(t["amount"])), 2)
            except (ValueError, TypeError, KeyError):
                continue
            if amt <= 0 or t.get("kind") not in ("income", "expense", "transfer", "refund"):
                continue
            txns.append({"date": d, "amount": amt, "kind": t["kind"],
                         "category": t.get("category") or categorize(t.get("desc", ""), t["kind"]),
                         "desc": (t.get("desc") or "").strip()[:120],
                         "account": (batch.get("account") or "").strip()[:30],
                         "card": str(t.get("card") or batch.get("card") or "").strip()[:24],
                         "flow": t.get("flow") if t.get("flow") in ("in", "out") and t["kind"] == "transfer" else "",
                         "currency": batch.get("currency") or "CNY"})
        if not txns:
            return {"count": 0}
        store.assign_hashes(txns)
        store.add_import(batch.get("file", "手动添加"), batch.get("account", ""), batch.get("method", ""), txns)
        n = transfers.reclassify()
        return {"count": len(txns), "transfers": n, "paired": transfers.LAST["pairs"], "pending": transfers.LAST["pending"],
                "months": sorted({t["date"][:7] for t in txns}), "currency": txns[0]["currency"]}

    # ---------- 查询 ----------
    def get_analysis(self, month, currency):
        return analysis.analyze(store.all_transactions(currency), month, currency, store.get_setting("lang", "zh"))

    def get_transactions(self, currency):
        return transfers.with_pairs(store.all_transactions(currency))

    def update_transaction(self, tid, fields):
        old = store.get_transaction(tid)
        if not old:
            return False
        fields = dict(fields)
        if "amount" in fields:
            fields["amount"] = round(abs(float(fields["amount"])), 2)
        kind = fields.get("kind", old["kind"])
        if "kind" in fields and fields["kind"] != old["kind"]:
            fields["locked"] = 1
        if "kind" in fields and fields["kind"] != old["kind"] and "category" not in fields:
            fields["category"] = categorize(old["desc"], kind, store.learned_rules())
        if kind == "transfer" and fields.get("category", old["category"]) != transfers.RETURNED:
            fields["category"] = TRANSFER_CATEGORY
        if kind == "refund" and "category" not in fields:
            fields["category"] = categorize(old["desc"], "expense", store.learned_rules())
        store.update_transaction(tid, fields)
        if "category" in fields and kind != "transfer":  # 记住这次修改，以后同类交易自动归类
            store.save_rule(rule_key(fields.get("desc", old["desc"])), fields["category"], kind)
        return store.get_transaction(tid)

    def delete_transactions(self, ids):
        store.delete_transactions(ids)
        return True

    def list_imports(self):
        return store.list_imports()

    def delete_import(self, iid):
        store.delete_import(iid)
        return True

    def clear_all(self):
        store.clear_all()
        return True

    # ---------- 内部转账识别 ----------
    def get_owner_names(self):
        return store.get_setting("owner_names", "") or ""

    def set_owner_names(self, text):
        transfers.set_owner_names(text)
        return {"names": self.get_owner_names(), "transfers": transfers.reclassify()}

    def reclassify_transfers(self):
        return {"names": self.get_owner_names(), "transfers": transfers.reclassify()}

    # ---------- 手机同步 ----------
    def sync_status(self):
        import segno
        st = sync_server.status()
        st["enabled"] = store.get_setting("sync_enabled", "0") == "1"
        st["qr"] = segno.make(st["url"], error="m").svg_inline(scale=6, border=2, dark="#14161a", light="#ffffff")
        st["repo"] = REPO_URL
        return st

    def sync_enable(self, on):
        store.set_setting("sync_enabled", "1" if on else "0")
        if on:
            if not sync_server.start(os.path.join(BASE, "web"), _on_push):
                return {"error": "端口被占用，无法开启同步服务"}
        else:
            sync_server.stop()
        return self.sync_status()

    def sync_reset(self):
        sync_server.reset_token()
        return self.sync_status()

    # ---------- 导出 ----------
    def export_excel(self, currency):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        res = window.create_file_dialog(_dialog("SAVE"), save_filename=f"收支报告_{currency}_{dt.date.today()}.xlsx",
                                        file_types=("Excel 工作簿 (*.xlsx)",))
        if not res:
            return None
        path = res if isinstance(res, str) else res[0]
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        txns = store.all_transactions(currency)
        wb = Workbook()
        head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2A78D6")

        def sheet(ws, headers, rows, widths):
            ws.append(headers)
            for c in ws[1]:
                c.font, c.fill, c.alignment = head_font, head_fill, Alignment(horizontal="center")
            for r in rows:
                ws.append(r)
            for i, w in enumerate(widths):
                ws.column_dimensions[chr(65 + i)].width = w
            ws.freeze_panes = "A2"

        kinds = {"income": "收入", "expense": "支出", "transfer": "不计收支", "refund": "退款冲减"}
        ws = wb.active
        ws.title = "交易明细"
        sheet(ws, ["日期", "类型", "分类", "金额", "描述", "账户", "卡片"],
              [[t["date"], kinds[t["kind"]], t["category"], t["amount"], t["desc"], t["account"], t.get("card") or ""] for t in txns],
              [12, 10, 12, 12, 48, 16, 18])
        months = analysis.months_available(txns)
        rows, cat_rows = [], []
        for m in months:
            a = analysis.analyze(txns, m, currency)
            k = a["kpi"]
            rows.append([m, k["income"], k["expense"], k["net"],
                         (k["savings_rate"] / 100) if k["savings_rate"] is not None else None, k["count"]])
            for r in a["expense_cats"]:
                if r["amount"]:
                    cat_rows.append([m, "支出", r["name"], r["amount"], r["share"] / 100, r["count"]])
            for r in a["income_cats"]:
                if r["amount"]:
                    cat_rows.append([m, "收入", r["name"], r["amount"], r["share"] / 100, r["count"]])
        ws2 = wb.create_sheet("月度汇总")
        sheet(ws2, ["月份", "收入", "支出", "结余", "储蓄率", "笔数"], rows, [10, 14, 14, 14, 10, 8])
        for c in ws2["E"][1:]:
            c.number_format = "0.0%"
        ws3 = wb.create_sheet("分类汇总")
        sheet(ws3, ["月份", "类型", "分类", "金额", "占比", "笔数"], cat_rows, [10, 8, 14, 14, 10, 8])
        for c in ws3["E"][1:]:
            c.number_format = "0.0%"
        if months:
            a = analysis.analyze(txns, months[-1], currency, store.get_setting("lang", "zh"))
            ws4 = wb.create_sheet(f"建议({months[-1]})")
            sheet(ws4, ["级别", "结论", "依据", "建议做法"],
                  [[{"alert": "需立即关注", "warn": "建议调整", "info": "提示", "good": "保持"}[x["level"]],
                    x["title"], x["detail"], x["action"]] for x in a["advice"]], [12, 36, 60, 70])
            for row in ws4.iter_rows(min_row=2):
                for c in row:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
        wb.save(path)
        return path

    # ---------- 示例数据 ----------
    def load_demo(self):
        rnd = random.Random(7)
        DEMO_CARDS = {"招商银行": "储蓄卡尾号6621", "微信支付": "招商银行储蓄卡(6621)", "支付宝": "花呗"}
        today = dt.date.today()
        txns = []

        def add(d, amt, kind, desc, acc):
            if d <= today:
                txns.append({"date": d.isoformat(), "amount": round(amt, 2), "kind": kind, "desc": desc,
                             "account": acc, "currency": "CNY", "card": DEMO_CARDS.get(acc, ""),
                             "category": categorize(desc, kind)})

        food = ["美团外卖", "饿了么", "瑞幸咖啡", "公司食堂", "海底捞火锅", "肯德基", "兰州拉面", "喜茶", "星巴克", "麦当劳"]
        shop = ["淘宝 · 日用品", "京东 · 数码配件", "拼多多", "优衣库", "天猫旗舰店", "得物"]
        fun = ["猫眼电影", "Steam 游戏", "KTV", "健身房月卡", "剧本杀"]
        for back in range(5, -1, -1):
            k = today.year * 12 + today.month - 1 - back
            y, m = k // 12, k % 12 + 1
            nd = calendar.monthrange(y, m)[1]
            hot = back == 0  # 最近一个月刻意花得多一些，便于展示建议
            add(dt.date(y, m, 10), 12500 + rnd.choice([0, 0, 300, -200]), "income", "代发工资 · 某某科技有限公司", "招商银行")
            if m in (1, 7):
                add(dt.date(y, m, 15), 6000, "income", "年中奖金", "招商银行")
            add(dt.date(y, m, 21), round(rnd.uniform(18, 46), 2), "income", "活期结息 利息", "招商银行")
            add(dt.date(y, m, 1), 3200, "expense", "房租 · 自如", "招商银行")
            add(dt.date(y, m, 5), round(rnd.uniform(160, 260), 2), "expense", "国家电网 电费 水费", "支付宝")
            add(dt.date(y, m, 8), 99, "expense", "中国移动 话费", "支付宝")
            add(dt.date(y, m, 12), 25, "expense", "爱奇艺 连续包月", "微信支付")
            add(dt.date(y, m, 12), 15, "expense", "网易云音乐 会员", "微信支付")
            add(dt.date(y, m, 18), 21, "expense", "iCloud 存储", "支付宝")
            add(dt.date(y, m, 25), 3000, "transfer", "信用卡还款", "招商银行")
            for d in range(1, nd + 1):
                day = dt.date(y, m, d)
                for _ in range(rnd.choice([1, 2, 2, 3]) + (1 if hot and rnd.random() < 0.4 else 0)):
                    add(day, rnd.uniform(12, 58) * (1.25 if hot else 1), "expense", rnd.choice(food),
                        rnd.choice(["微信支付", "支付宝"]))
                if day.weekday() >= 5 and rnd.random() < 0.55:
                    add(day, rnd.uniform(120, 380), "expense", rnd.choice(["海底捞火锅", "日料店 聚餐", "烧烤店"]), "微信支付")
                if rnd.random() < 0.75:
                    add(day, rnd.choice([3, 4, 6, 18, 24, 32]), "expense", rnd.choice(["地铁", "滴滴出行", "哈啰单车"]), "支付宝")
                if day.weekday() == 6:
                    add(day, rnd.uniform(90, 240), "expense", rnd.choice(["盒马鲜生", "永辉超市", "山姆会员店"]), "支付宝")
                if rnd.random() < (0.28 if hot else 0.14):
                    add(day, rnd.uniform(60, 680), "expense", rnd.choice(shop), "招商银行")
                if rnd.random() < 0.09:
                    add(day, rnd.uniform(40, 260), "expense", rnd.choice(fun), "微信支付")
            if back == 2:
                add(dt.date(y, m, 16), 1880, "expense", "携程 机票", "招商银行")
                add(dt.date(y, m, 17), 960, "expense", "全季酒店", "招商银行")
            if back == 1:
                add(dt.date(y, m, 9), 420, "expense", "市第一医院 门诊", "招商银行")
            if hot:
                add(dt.date(y, m, 3), 35, "expense", "信用卡 滞纳金 手续费", "招商银行")
                add(dt.date(y, m, 6), 2399, "expense", "京东 · 降噪耳机", "招商银行")
        store.assign_hashes(txns)
        store.add_import("示例数据", "多个账户", "内置示例", txns)
        return {"count": len(txns)}


def _bind(win):
    """把拖进窗口的文件路径交给前端。"""
    try:
        from webview.dom import DOMEventHandler

        def on_drop(e):
            files = (e.get("dataTransfer") or {}).get("files") or []
            paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
            if paths:
                win.evaluate_js(f"window.onFilesDropped({json.dumps(paths)})")

        win.dom.document.events.drop += DOMEventHandler(on_drop, True, False)
    except Exception:
        traceback.print_exc()


def _selftest(files, out):
    """--selftest 文件... 输出.json：不开窗口，解析文件并把结果写到 json（用于验证打包后的 exe）。"""
    res = []
    for f in files:
        try:
            r = parsers.parse_file(f)
            res.append({"file": r["file"], "method": r["method"], "count": len(r["txns"]), "txns": r["txns"][:3]})
        except Exception:
            res.append({"file": f, "error": traceback.format_exc()})
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)


def main():
    global window
    if "--selftest-sync" in sys.argv:  # 验证打包后同步服务与手机端页面是否齐全
        import urllib.request
        out = sys.argv[sys.argv.index("--selftest-sync") + 1]
        try:
            ok = sync_server.start(os.path.join(BASE, "web"))
            base = f"http://127.0.0.1:{sync_server.status()['port']}"
            res = {"started": ok, "qr": "<svg" in Api().sync_status()["qr"]}
            for p in ("/api/ping", "/", "/m.js", "/m.css", "/echarts.min.js", "/icon.png"):
                res[p] = len(urllib.request.urlopen(base + p, timeout=5).read())
        except Exception:
            res = {"error": traceback.format_exc()}
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
        return
    if "--selftest" in sys.argv:
        args = sys.argv[sys.argv.index("--selftest") + 1:]
        return _selftest(args[:-1], args[-1])
    store.init()
    try:  # 升级后对已有数据补做一次内部转账识别
        transfers.reclassify()
    except Exception:
        traceback.print_exc()
    if store.get_setting("sync_enabled", "0") == "1":
        sync_server.start(os.path.join(BASE, "web"), _on_push)
    window = webview.create_window(
        APP_NAME, os.path.join(BASE, "web", "index.html"), js_api=Api(),
        width=1360, height=880, min_size=(1100, 700), background_color="#f9f9f7", text_select=True)
    webview.start(_bind, window)


if __name__ == "__main__":
    main()
