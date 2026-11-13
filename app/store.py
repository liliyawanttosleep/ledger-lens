# -*- coding: utf-8 -*-
"""本地数据存储（SQLite）。数据保存在当前用户的 AppData 下，每个使用者各自独立。"""
import datetime as dt
import hashlib
import os
import sqlite3
import threading

APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "LedgerAssistant")
DB_PATH = os.path.join(APP_DIR, "data.db")
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, account TEXT, method TEXT,
  imported_at TEXT, count INTEGER);
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, amount REAL NOT NULL,
  kind TEXT NOT NULL, category TEXT NOT NULL, desc TEXT, account TEXT, currency TEXT,
  import_id INTEGER, hash TEXT);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_txn_hash ON transactions(hash);
CREATE TABLE IF NOT EXISTS rules(pattern TEXT PRIMARY KEY, category TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def _conn():
    os.makedirs(APP_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(transactions)")}
        if "card" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN card TEXT DEFAULT ''")
        if "locked" not in cols:  # 用户手动改过类型的交易，自动识别不再改动
            c.execute("ALTER TABLE transactions ADD COLUMN locked INTEGER DEFAULT 0")


def txn_hash(t: dict, seq: int = 0) -> str:
    """去重指纹：同一账户、同一天、同金额、同描述视为同一笔；seq 区分同文件内确实重复的交易。"""
    key = f'{t["date"]}|{t["amount"]:.2f}|{t["kind"] == "income"}|{(t.get("desc") or "").lower()[:40]}|' \
          f'{t.get("account", "")}|{seq}'
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def assign_hashes(txns: list):
    seen = {}
    for t in txns:
        base = txn_hash(t, 0)
        n = seen.get(base, 0)
        seen[base] = n + 1
        t["hash"] = txn_hash(t, n)
    return txns


def existing_hashes(hashes):
    if not hashes:
        return set()
    with _lock, _conn() as c:
        out = set()
        hs = list(hashes)
        for i in range(0, len(hs), 500):
            chunk = hs[i:i + 500]
            q = ",".join("?" * len(chunk))
            out |= {r[0] for r in c.execute(f"SELECT hash FROM transactions WHERE hash IN ({q})", chunk)}
        return out


def add_import(filename, account, method, txns) -> int:
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO imports(filename, account, method, imported_at, count) VALUES(?,?,?,?,?)",
                        (filename, account, method, dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(txns)))
        iid = cur.lastrowid
        c.executemany(
            "INSERT INTO transactions(date, amount, kind, category, desc, account, currency, import_id, hash, card)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(t["date"], t["amount"], t["kind"], t["category"], t.get("desc", ""), t.get("account", ""),
              t.get("currency", "CNY"), iid, t.get("hash", ""), t.get("card", "") or "") for t in txns])
        return iid


def all_transactions(currency=None):
    with _lock, _conn() as c:
        if currency:
            rows = c.execute("SELECT * FROM transactions WHERE currency=? ORDER BY date DESC, id DESC", (currency,))
        else:
            rows = c.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
        return [dict(r) for r in rows]


def update_transaction(tid, fields: dict):
    allowed = {k: v for k, v in fields.items() if k in ("date", "amount", "kind", "category", "desc", "account", "card", "locked")}
    if not allowed:
        return
    sets = ", ".join(f"{k}=?" for k in allowed)
    with _lock, _conn() as c:
        c.execute(f"UPDATE transactions SET {sets} WHERE id=?", (*allowed.values(), tid))


def get_transaction(tid):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
        return dict(r) if r else None


def delete_transactions(ids):
    with _lock, _conn() as c:
        c.executemany("DELETE FROM transactions WHERE id=?", [(i,) for i in ids])


def list_imports():
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT i.*, (SELECT COUNT(*) FROM transactions t WHERE t.import_id=i.id) AS remaining,"
            " (SELECT MIN(date) FROM transactions t WHERE t.import_id=i.id) AS first_date,"
            " (SELECT MAX(date) FROM transactions t WHERE t.import_id=i.id) AS last_date"
            " FROM imports i ORDER BY i.id DESC")]


def delete_import(iid):
    with _lock, _conn() as c:
        c.execute("DELETE FROM transactions WHERE import_id=?", (iid,))
        c.execute("DELETE FROM imports WHERE id=?", (iid,))


def clear_all():
    with _lock, _conn() as c:
        c.execute("DELETE FROM transactions")
        c.execute("DELETE FROM imports")


def learned_rules() -> dict:
    with _lock, _conn() as c:
        return {r["pattern"]: {"category": r["category"], "kind": r["kind"]}
                for r in c.execute("SELECT * FROM rules")}


def save_rule(pattern, category, kind):
    if not pattern:
        return
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO rules(pattern, category, kind) VALUES(?,?,?)", (pattern, category, kind))


def get_setting(key, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default


def set_setting(key, value):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, str(value)))
