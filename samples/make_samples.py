# -*- coding: utf-8 -*-
"""生成几份不同格式的测试账单（虚构数据），用来验证解析是否正确。运行：python make_samples.py"""
import os

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

HERE = os.path.dirname(os.path.abspath(__file__))
pdfmetrics.registerFont(TTFont("hei", r"C:\Windows\Fonts\simhei.ttf"))


def alipay_csv():
    lines = ["支付宝交易记录明细查询", "账号:[demo@example.com]", "起始日期:[2026-09-01 00:00:00]    终止日期:[2026-09-30 23:59:59]",
             "---------------------------------交易记录明细列表------------------------------------",
             "交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,",
             "2026-09-28 12:31:02,餐饮美食,美团,mt***@meituan.com,美团外卖订单,支出,32.50,花呗,交易成功,2026092822001\t,M123\t,,",
             "2026-09-27 19:05:44,日用百货,盒马鲜生,hm***@hema.com,盒马订单,支出,186.40,余额宝,交易成功,2026092722002\t,M124\t,,",
             "2026-09-25 09:00:00,转账红包,张三,138****0000,转账,收入,500.00,余额,交易成功,2026092522003\t,,,",
             "2026-09-20 08:12:10,交通出行,滴滴出行,didi***@didi.com,快车,支出,24.80,招商银行储蓄卡(1234),交易成功,2026092022004\t,,,",
             "2026-09-18 10:00:00,投资理财,余额宝,,余额宝-自动转入,不计收支,1000.00,余额,交易成功,2026091822005\t,,,",
             "2026-09-15 21:40:00,服饰装扮,优衣库官方旗舰店,uniqlo***,T恤,支出,199.00,花呗,交易关闭,2026091522006\t,,,",
             "2026-09-12 14:00:00,文化休闲,爱奇艺,iqiyi***,黄金会员连续包月,支出,25.00,余额宝,交易成功,2026091222007\t,,,"]
    with open(os.path.join(HERE, "支付宝账单_9月.csv"), "w", encoding="gbk", newline="") as f:
        f.write("\r\n".join(lines))


def cmb_pdf():
    doc = SimpleDocTemplate(os.path.join(HERE, "招商银行交易流水.pdf"), pagesize=A4)
    data = [["记账日期", "货币", "交易金额", "联机余额", "交易摘要", "对手信息"],
            ["2026-10-01", "人民币", "-3,200.00", "18,450.22", "转账汇款", "自如生活 房租"],
            ["2026-10-05", "人民币", "-35.00", "18,415.22", "快捷支付", "财付通-星巴克咖啡"],
            ["2026-10-10", "人民币", "12,500.00", "30,915.22", "代发工资", "某某科技有限公司"],
            ["2026-10-12", "人民币", "-268.00", "30,647.22", "快捷支付", "支付宝-京东商城"],
            ["2026-10-21", "人民币", "23.18", "30,670.40", "账户结息", ""],
            ["2026-10-25", "人民币", "-3,000.00", "27,670.40", "信用卡还款", "招商银行信用卡"],
            ["2026-10-28", "人民币", "-420.00", "27,250.40", "快捷支付", "市第一医院"]]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "hei", 9), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    doc.build([t])


def chase_pdf():
    c = canvas.Canvas(os.path.join(HERE, "chase_checking_statement.pdf"), pagesize=letter)
    y = 750

    def line(s, bold=False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(50, y, s)
        y -= 16

    line("JPMorgan Chase Bank, N.A.", True)
    line("September 16, 2026 through October 15, 2026")
    line("Account Number: 000000123456789")
    line("CHECKING SUMMARY", True)
    line("Beginning Balance $2,310.45")
    line("Ending Balance $3,018.26")
    y -= 8
    line("DEPOSITS AND ADDITIONS", True)
    line("DATE DESCRIPTION AMOUNT")
    line("09/30 State Univ Payroll PPD ID: 1234567890 $1,450.00")
    line("10/02 Zelle Payment From Li Lei 21334455667 200.00")
    line("Total Deposits and Additions $1,650.00")
    y -= 8
    line("ATM & DEBIT CARD WITHDRAWALS", True)
    line("DATE DESCRIPTION AMOUNT")
    line("09/18 Card Purchase 09/17 Wegmans Springfield NY Card 1234 $86.32")
    line("09/21 Card Purchase 09/20 Starbucks Store 08812 Springfield NY Card 1234 5.75")
    line("10/03 Card Purchase 10/02 Amazon.Com*Ab12C Amzn.Com/Bill WA Card 1234 42.19")
    line("10/08 Recurring Card Purchase 10/08 Netflix.Com CA Card 1234 15.49")
    y -= 8
    line("ELECTRONIC WITHDRAWALS", True)
    line("10/01 Maple Court Apts Web Pmts 1Q2W3E Web ID: 9000000001 $725.00")
    line("10/05 Discover E-Payment 1234 Web ID: 2510020270 67.44")
    c.save()


def discover_csv():
    rows = ["Trans. Date,Post Date,Description,Amount,Category",
            "10/02/2026,10/02/2026,UBER *TRIP HELP.UBER.COM,18.42,Travel/ Entertainment",
            "10/04/2026,10/05/2026,TRADER JOE S #123 SPRINGFIELD NY,54.10,Supermarkets",
            "10/05/2026,10/05/2026,INTERNET PAYMENT - THANK YOU,-67.44,Payments and Credits",
            "10/09/2026,10/09/2026,SPOTIFY USA,11.99,Services",
            "10/11/2026,10/12/2026,CHIPOTLE 1234 SPRINGFIELD NY,13.75,Restaurants"]
    with open(os.path.join(HERE, "Discover-Statement-20261015.csv"), "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(rows))


def _font(size):
    return ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", size)


def wechat_png():
    img = Image.new("RGB", (750, 1100), "#ededed")
    d = ImageDraw.Draw(img)
    d.text((320, 30), "账单", fill="black", font=_font(34))
    d.text((40, 110), "2026年10月", fill="black", font=_font(30))
    d.text((40, 160), "支出¥386.50  收入¥500.00", fill="#888", font=_font(24))
    items = [("瑞幸咖啡", "-16.90", "10月28日 08:42"), ("美团外卖", "-38.60", "10月27日 12:15"),
             ("二维码收款-来自小王", "+500.00", "10月26日 20:03"), ("滴滴出行", "-31.00", "10月25日 23:10"),
             ("永辉超市", "-212.00", "10月24日 18:30"), ("猫眼电影", "-88.00", "10月23日 19:55")]
    y = 220
    for name, amt, when in items:
        d.rectangle((0, y, 750, y + 130), fill="white")
        d.ellipse((30, y + 30, 100, y + 100), fill="#07c160")
        d.text((125, y + 25), name, fill="black", font=_font(30))
        d.text((125, y + 75), when, fill="#999", font=_font(24))
        w = d.textlength(amt, font=_font(32))
        d.text((720 - w, y + 30), amt, fill="#e6a23c" if amt[0] == "+" else "black", font=_font(32))
        y += 132
    img.save(os.path.join(HERE, "微信账单截图.png"))


def payslip_png():
    img = Image.new("RGB", (900, 520), "white")
    d = ImageDraw.Draw(img)
    d.text((330, 30), "2026年10月工资条", fill="black", font=_font(34))
    rows = [("姓名", "王小明"), ("发薪日期", "2026-10-10"), ("基本工资", "10,000.00"), ("绩效奖金", "4,500.00"),
            ("应发合计", "14,500.00"), ("社保公积金", "-1,560.00"), ("个人所得税", "-440.00"), ("实发工资", "12,500.00")]
    y = 110
    for k, v in rows:
        d.line((60, y - 8, 840, y - 8), fill="#ddd")
        d.text((80, y), k, fill="#444", font=_font(26))
        d.text((560, y), v, fill="black", font=_font(26))
        y += 48
    img.save(os.path.join(HERE, "工资条_10月.png"))


if __name__ == "__main__":
    alipay_csv(); cmb_pdf(); chase_pdf(); discover_csv(); wechat_png(); payslip_png()
    print("samples written to", HERE)
