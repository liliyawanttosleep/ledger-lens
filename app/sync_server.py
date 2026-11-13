# -*- coding: utf-8 -*-
"""手机同步服务：在局域网内提供手机端页面和同步接口。

- 默认关闭，由用户在电脑端“手机同步”页开启。
- 所有数据接口都要带配对码（X-Token）；连续输错会被暂时锁定。
- 手机端页面（web/mobile）既由这里直接提供给浏览器，也被打进安卓 App。
"""
import datetime as dt
import hashlib
import json
import os
import secrets
import socket
import threading
import time
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from bottle import Bottle, HTTPResponse, request, response, static_file

import analysis
import store
from categorize import EXPENSE_CATEGORIES, INCOME_CATEGORIES, TRANSFER_CATEGORY, categorize

PORT = 8756
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # 去掉易混淆的 0/O、1/I/L
_state = {"server": None, "thread": None, "port": None, "on_push": None, "web": None}
_fails = {}  # ip -> [次数, 解锁时间]


def token() -> str:
    t = store.get_setting("sync_token")
    if not t:
        t = reset_token()
    return t


def reset_token() -> str:
    t = "".join(secrets.choice(ALPHABET) for _ in range(8))
    store.set_setting("sync_token", t)
    return t


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # 不会真的发包，只是让系统选出局域网网卡
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def build_payload(lang: str = "zh") -> dict:
    """打包给手机的全部数据：每个币种近 12 个月的完整分析 + 近期明细。"""
    txns = store.all_transactions()
    by_cur = {}
    for t in txns:
        by_cur.setdefault(t["currency"] or "CNY", []).append(t)
    currencies = []
    for code, rows in sorted(by_cur.items(), key=lambda kv: -len(kv[1])):
        months = analysis.months_available(rows)
        currencies.append({
            "code": code, "symbol": analysis.SYMBOLS.get(code, code + " "), "months": months,
            "analyses": {m: analysis.analyze(rows, m, code, lang) for m in months[-12:]},
            "txns": [{k: t[k] for k in ("id", "date", "amount", "kind", "category", "desc", "account", "card")}
                     for t in rows[:3000]],
        })
    return {
        "app": "ledger-lens", "device": socket.gethostname(),
        "synced_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "expense_categories": EXPENSE_CATEGORIES, "income_categories": INCOME_CATEGORIES,
        "transfer_category": TRANSFER_CATEGORY, "currencies": currencies,
    }


def accept_push(items: list) -> int:
    """接收手机上记的账。用手机端生成的 cid 去重，重复推送不会重复入账。"""
    txns = []
    for it in items[:500]:
        try:
            d = dt.date.fromisoformat(str(it["date"])[:10]).isoformat()
            amt = round(abs(float(it["amount"])), 2)
            kind = it["kind"]
        except (KeyError, ValueError, TypeError):
            continue
        if amt <= 0 or kind not in ("income", "expense", "transfer", "refund"):
            continue
        desc = str(it.get("desc") or "(无描述)")[:120]
        txns.append({"date": d, "amount": amt, "kind": kind, "desc": desc,
                     "category": str(it.get("category") or categorize(desc, kind))[:20],
                     "account": str(it.get("account") or "手机记账")[:30],
                     "currency": str(it.get("currency") or "CNY")[:3],
                     "hash": hashlib.md5(("m|" + str(it.get("cid", ""))).encode()).hexdigest()})
    have = store.existing_hashes({t["hash"] for t in txns})
    fresh = [t for t in txns if t["hash"] not in have]
    if fresh:
        store.add_import("手机记账", "手机", "手机同步", fresh)
    return len(fresh)


def _make_app(web_dir: str) -> Bottle:
    app = Bottle()
    mobile = os.path.join(web_dir, "mobile")

    @app.hook("after_request")
    def cors():
        response.set_header("Access-Control-Allow-Origin", "*")
        response.set_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        response.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.set_header("Cache-Control", "no-store")

    def deny(code, msg):
        return HTTPResponse(status=code, body=json.dumps({"error": msg}, ensure_ascii=False),
                            headers={"Content-Type": "application/json; charset=utf-8",
                                     "Access-Control-Allow-Origin": "*"})

    def auth():
        ip = request.remote_addr or "?"
        n, until = _fails.get(ip, (0, 0))
        if until > time.time():
            raise deny(429, "尝试次数过多，请 5 分钟后再试")
        got = (request.headers.get("X-Token") or request.query.get("t") or "").strip().upper()
        if not secrets.compare_digest(got, token()):
            n += 1
            _fails[ip] = (0, time.time() + 300) if n >= 8 else (n, 0)
            raise deny(401, "配对码不正确")
        _fails.pop(ip, None)

    def js(obj):
        response.content_type = "application/json; charset=utf-8"
        return json.dumps(obj, ensure_ascii=False)

    @app.route("/api/<path:path>", method="OPTIONS")
    def preflight(path):
        return ""

    @app.get("/api/ping")
    def ping():
        return js({"app": "ledger-lens", "device": socket.gethostname()})

    @app.get("/api/sync")
    def sync():
        auth()
        return js(build_payload(request.query.get("lang") or "zh"))

    @app.post("/api/push")
    def push():
        auth()
        body = json.loads(request.body.read().decode("utf-8") or "{}")
        n = accept_push(body.get("txns") or [])
        if n and _state["on_push"]:
            try:
                _state["on_push"](n)
            except Exception:
                pass
        return js({"added": n})

    @app.get("/")
    def index():
        return static_file("index.html", root=mobile)

    @app.get("/echarts.min.js")
    def echarts():
        return static_file("echarts.min.js", root=web_dir)

    @app.get("/<path:path>")
    def files(path):
        return static_file(path, root=mobile)

    return app


class _Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


class _Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


def start(web_dir: str, on_push=None) -> bool:
    if _state["server"]:
        return True
    _state["on_push"] = on_push
    app = _make_app(web_dir)
    for port in range(PORT, PORT + 10):
        try:
            srv = make_server("0.0.0.0", port, app, server_class=_Server, handler_class=_Quiet)
        except OSError:
            continue
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        _state.update(server=srv, thread=th, port=port)
        return True
    return False


def stop():
    srv = _state["server"]
    if srv:
        srv.shutdown()
        srv.server_close()
        _state.update(server=None, thread=None, port=None)


def status() -> dict:
    running = _state["server"] is not None
    ip, port, tk = local_ip(), _state["port"] or PORT, token()
    base = f"http://{ip}:{port}"
    return {"running": running, "ip": ip, "port": port, "token": tk, "base": base,
            "url": f"{base}/?t={tk}", "device": socket.gethostname()}
