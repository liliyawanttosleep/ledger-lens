# -*- coding: utf-8 -*-
"""解析自测：python test_parse.py [文件...]（不带参数则解析 samples 下的全部文件）"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import parsers  # noqa: E402
from categorize import categorize  # noqa: E402

files = sys.argv[1:] or [os.path.join(HERE, f) for f in sorted(os.listdir(HERE))
                         if os.path.splitext(f)[1].lower() in parsers.SUPPORTED_EXT]
for f in files:
    r = parsers.parse_file(f, "income" if "工资" in f else "auto")
    print(f"\n=== {r['file']} | {r['method']} | {r['account']} | {r['currency']} | card={r['credit_card']} | {len(r['txns'])} 笔")
    for w in r["warnings"]:
        print("   !", w)
    for t in r["txns"]:
        print(f"   {t['date']}  {t['kind']:8s} {t['amount']:>10.2f}  {categorize(t['desc'], t['kind']):6s}  {t['desc']}")
