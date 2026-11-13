# -*- coding: utf-8 -*-
"""开发用：在浏览器里调试界面（http://127.0.0.1:8765/index.html?dev=1）。不会打进 exe。
数据写到单独的临时库，不影响正式数据。"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store  # noqa: E402

store.APP_DIR = os.path.join(tempfile.gettempdir(), "LedgerAssistantDev")
store.DB_PATH = os.path.join(store.APP_DIR, "data.db")

from bottle import request, response, route, run, static_file  # noqa: E402

import main  # noqa: E402

api = main.Api()
SAMPLES = os.path.join(HERE, "..", "samples")
api.pick_files = lambda: [os.path.abspath(os.path.join(SAMPLES, f)) for f in sorted(os.listdir(SAMPLES))
                          if not f.endswith(".py") and os.path.isfile(os.path.join(SAMPLES, f))]
api.export_excel = lambda currency: None


@route("/api/<name>", method="POST")
def call(name):
    args = json.loads(request.body.read().decode("utf-8") or "[]")
    response.content_type = "application/json; charset=utf-8"
    return json.dumps(getattr(api, name)(*args), ensure_ascii=False)


@route("/<path:path>")
def files(path):
    resp = static_file(path, root=os.path.join(HERE, "web"))
    resp.set_header("Cache-Control", "no-store")
    return resp


if __name__ == "__main__":
    store.init()
    run(host="127.0.0.1", port=8765, quiet=True)
