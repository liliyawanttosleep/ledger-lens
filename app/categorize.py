# -*- coding: utf-8 -*-
"""交易分类：基于关键词的规则引擎（中英文商户均支持）。"""
import re

EXPENSE_CATEGORIES = [
    "餐饮美食", "超市日用", "购物消费", "交通出行", "住房物业", "通讯订阅",
    "娱乐休闲", "医疗健康", "教育学习", "旅行住宿", "人情往来", "金融费用", "其他支出",
]
INCOME_CATEGORIES = ["工资薪酬", "奖金补贴", "投资理财", "退款报销", "转账收入", "其他收入"]
TRANSFER_CATEGORY = "内部转账"

# 必需型支出（建议中不压缩）与弹性支出（可优化）
ESSENTIAL = {"住房物业", "医疗健康", "教育学习", "交通出行", "超市日用", "通讯订阅"}
FLEXIBLE = {"餐饮美食", "购物消费", "娱乐休闲", "旅行住宿", "人情往来", "其他支出", "金融费用"}

# 不计入收支的内部资金流动
TRANSFER_KEYWORDS = [
    "信用卡还款", "还款", "自动还款", "余额宝", "零钱通", "理财通", "转入零钱", "零钱提现", "提现",
    "充值到", "本人转账", "自己转账", "同名转账", "银证转账", "基金申购", "定期存款", "活期转定期",
    "payment thank you", "autopay", "auto pay", "directpay", "online payment", "internet payment",
    "payment received", "epay", "e-payment", "credit card payment", "card payment", "crd epay",
    "online transfer to", "online transfer from", "transfer to sav", "transfer from sav",
    "transfer to chk", "transfer from chk", "transfer to checking", "transfer to savings",
    "transfer from checking", "transfer from savings", "internal transfer", "balance transfer",
    "applecard gsbank", "chase credit crd", "discover e-payment", "capital one crcardpmt",
    "amex epayment", "citi card online", "barclaycard", "wealthfront", "robinhood", "fidelity",
    "vanguard", "schwab", "coinbase",
]

EXPENSE_RULES = [
    ("金融费用", ["手续费", "年费", "利息支出", "滞纳金", "违约金", "短信费", "工本费", "服务费", "管理费",
              "interest charge", "late fee", "annual fee", "service fee", "monthly fee", "overdraft",
              "atm fee", "foreign transaction", "finance charge", "maintenance fee", "wire fee"]),
    ("住房物业", ["房租", "租金", "物业", "水费", "电费", "燃气", "煤气", "暖气", "供暖", "宽带", "自如", "贝壳",
              "链家", "房贷", "按揭", "公积金贷款", "国家电网", "水务", "rent", "apartment", "apts", "leasing",
              "property", "mortgage", "electric", "utility", "utilities", "water bill", "gas bill",
              "peco", "pg&e", "con ed", "duke energy", "comcast", "xfinity", "spectrum",
              "internet", "landlord", "housing", "realty", "renters ins", "lemonade"]),
    ("通讯订阅", ["话费", "中国移动", "中国联通", "中国电信", "流量", "会员费", "会员续费", "黄金会员", "超级会员", "音乐 会员", "视频会员", "连续包月", "自动续费", "订阅",
              "爱奇艺", "腾讯视频", "优酷", "芒果tv", "哔哩哔哩大会员", "网易云音乐", "qq音乐", "icloud",
              "百度网盘", "夸克", "netflix", "spotify", "hulu", "disney", "hbo", "youtube", "apple.com/bill",
              "apple com bill", "google one", "google storage", "google *", "prime video", "amazon prime",
              "chatgpt", "openai", "claude", "anthropic", "github", "notion", "dropbox", "adobe",
              "microsoft", "verizon", "at&t", "t-mobile", "tmobile", "mint mobile", "visible", "cricket",
              "patreon", "nytimes", "subscription", "membership", "grammarly", "midjourney", "cursor"]),
    ("餐饮美食", ["餐", "饭", "面", "粉", "食堂", "美食", "外卖", "美团", "饿了么", "肯德基", "麦当劳", "星巴克", "瑞幸",
              "喜茶", "奈雪", "蜜雪", "茶百道", "古茗", "霸王茶姬", "海底捞", "火锅", "烧烤", "咖啡", "奶茶", "小吃",
              "必胜客", "汉堡", "披萨", "寿司", "料理", "酒楼", "食品", "饮品", "甜品", "面包", "蛋糕", "早餐",
              "restaurant", "cafe", "coffee", "starbucks", "mcdonald", "kfc", "burger", "pizza", "chipotle",
              "subway", "taco", "wendy", "dunkin", "panera", "chick-fil-a", "panda express", "doordash",
              "uber eats", "ubereats", "grubhub", "kitchen", "grill", "bistro", "diner", "sushi", "ramen",
              "noodle", "bbq", "bakery", "tea", "boba", "bar ", "pub", "eatery", "deli", "pho", "thai",
              "hot pot", "dumpling", "tst*", "sq *", "toast", "food", "dining", "five guys", "popeyes",
              "domino", "shake shack", "wingstop", "ihop", "denny", "waffle"]),
    ("超市日用", ["超市", "便利店", "盒马", "永辉", "沃尔玛", "山姆", "大润发", "华润万家", "物美", "全家", "罗森",
              "7-11", "叮咚买菜", "朴朴", "美团买菜", "多多买菜", "菜市场", "生鲜", "水果", "日用", "百货", "名创",
              "屈臣氏", "walmart", "wal-mart", "target", "costco", "sam's club", "sams club", "kroger",
              "wegmans", "trader joe", "whole foods", "wholefds", "aldi", "safeway", "giant", "weis",
              "publix", "h mart", "hmart", "99 ranch", "grocery", "market", "instacart", "weee", "cvs",
              "walgreens", "rite aid", "dollar", "7-eleven", "sheetz", "wawa", "supermarket", "meijer",
              "food lion", "stop & shop", "harris teeter"]),
    ("交通出行", ["滴滴", "打车", "出租", "地铁", "公交", "一卡通", "高德", "曹操出行", "t3出行", "哈啰", "单车", "青桔",
              "加油", "中石化", "中石油", "停车", "高速", "etc", "12306", "铁路", "火车", "动车", "高铁", "充电",
              "车险", "洗车", "保养", "uber", "lyft", "taxi", "metro", "transit", "mta", "septa", "bart",
              "amtrak", "greyhound", "megabus", "parking", "toll", "ezpass", "e-zpass", "gas station",
              "shell", "exxon", "chevron", "sunoco", "bp ", "mobil", "speedway", "fuel", "dmv", "geico",
              "progressive", "state farm", "car wash", "auto ", "jiffy", "zipcar", "bird", "lime"]),
    ("旅行住宿", ["酒店", "宾馆", "民宿", "携程", "去哪儿", "飞猪", "同程", "航空", "机票", "航班", "旅游", "景区", "门票",
              "签证", "hotel", "airbnb", "marriott", "hilton", "hyatt", "booking", "expedia", "trip.com",
              "airline", "airlines", "delta air", "united", "american air", "southwest", "jetblue",
              "spirit air", "frontier", "air china", "hainan", "cathay", "hertz", "enterprise rent",
              "avis", "motel", "inn ", "resort", "travel", "vrbo", "priceline"]),
    ("娱乐休闲", ["电影", "影院", "影城", "猫眼", "淘票票", "ktv", "游戏", "网吧", "网咖", "剧本杀", "密室", "健身", "游泳",
              "演出", "演唱会", "大麦", "steam", "米哈游", "原神", "腾讯游戏", "网易游戏", "点券", "充值", "直播",
              "打赏", "抖音", "快手", "足浴", "按摩", "酒吧", "台球", "棋牌", "彩票", "playstation", "xbox",
              "nintendo", "epic games", "riot", "blizzard", "twitch", "cinema", "movie", "theatre", "theater",
              "amc ", "regal", "ticketmaster", "stubhub", "gym", "fitness", "planet fit", "bowling", "golf",
              "club", "concert", "museum", "zoo", "arcade", "hoyoverse", "mihoyo", "game"]),
    ("医疗健康", ["医院", "诊所", "药房", "药店", "门诊", "挂号", "体检", "医疗", "医保", "牙科", "口腔", "眼科", "药业",
              "大药房", "hospital", "clinic", "pharmacy", "medical", "dental", "dentist", "doctor", "health",
              "urgent care", "optical", "vision", "lab corp", "quest diag", "therapy"]),
    ("教育学习", ["学费", "培训", "教育", "课程", "书店", "图书", "当当", "考试", "报名费", "学校", "大学", "学院", "网课",
              "知识付费", "得到", "文具", "打印", "tuition", "university", "college", "school", "bursar",
              "coursera", "udemy", "edx", "textbook", "bookstore", "chegg", "ets ",
              "gre", "toefl", "kaplan", "pearson", "mcgraw", "course", "education", "student"]),
    ("购物消费", ["淘宝", "天猫", "京东", "拼多多", "唯品会", "苏宁", "得物", "闲鱼", "小红书", "抖音电商", "服饰", "服装",
              "鞋", "数码", "电器", "家具", "宜家", "优衣库", "zara", "耐克", "阿迪", "苹果", "小米", "华为", "商城",
              "旗舰店", "专卖店", "商场", "购物", "化妆", "美妆", "丝芙兰", "amazon", "amzn", "ebay", "etsy",
              "best buy", "bestbuy", "apple store", "nike", "adidas", "uniqlo", "h&m", "macy", "nordstrom",
              "tj maxx", "marshalls", "ross", "old navy", "gap", "ikea", "home depot", "lowe's", "lowes",
              "sephora", "ulta", "shein", "temu", "aliexpress", "wayfair", "newegg", "micro center",
              "shop", "store", "outlet", "mall", "paypal"]),
    ("人情往来", ["红包", "转账给", "转账-", "礼物", "礼金", "份子", "捐款", "捐赠", "慈善", "zelle payment to", "zelle to",
              "venmo", "cash app", "gift", "donation", "charity", "gofundme"]),
]

INCOME_RULES = [
    ("工资薪酬", ["工资", "薪资", "薪酬", "薪金", "代发", "劳务", "实发", "payroll", "salary", "direct dep", "dir dep",
              "paycheck", "wages", "stipend", "gusto", "adp", "paychex", "workday", "net pay"]),
    ("奖金补贴", ["奖金", "绩效", "年终", "补贴", "津贴", "奖学金", "助学金", "补助", "bonus", "scholarship", "fellowship",
              "grant", "award", "allowance", "assistantship"]),
    ("投资理财", ["利息", "结息", "分红", "股息", "收益", "理财", "基金赎回", "赎回", "interest paid", "interest payment",
              "interest earned", "dividend", "capital gain", "apy"]),
    ("退款报销", ["退款", "退货", "退回", "报销", "返现", "退税", "refund", "reimburse", "return", "cashback",
              "cash back", "rebate", "tax ref", "irs treas", "reversal", "credit adj"]),
    ("转账收入", ["转入", "收款", "汇入", "转账", "红包", "二维码收款", "zelle payment from", "zelle from", "venmo",
              "cash app", "wire in", "incoming wire", "remittance", "transfer from", "deposit"]),
]

# 仅在金额没有正负号、也没有其他线索时，用来猜测“这是一笔收入”
INCOME_HINTS = [
    "工资", "薪资", "薪酬", "代发", "奖金", "补贴", "津贴", "奖学金", "结息", "利息收入", "退款", "退回", "报销",
    "转入", "汇入", "收款", "存入", "入账", "payroll", "salary", "direct dep", "dir dep", "paycheck",
    "stipend", "bonus", "scholarship", "refund", "reimburse", "cashback", "interest paid",
    "interest earned", "dividend", "zelle payment from", "zelle from", "incoming wire", "deposit",
    "tax ref", "irs treas",
]


def _compile(keys):
    """英文关键词要求前面不是字母（避免 steam 命中 tea），短词还要求后面不是字母。"""
    parts = []
    for k in keys:
        if re.fullmatch(r"[\x00-\x7f]+", k):
            p = r"(?<![a-z])" + re.escape(k)
            if len(k.strip()) <= 3:
                p += r"(?![a-z])"
            parts.append(p)
        else:
            parts.append(re.escape(k))
    return re.compile("|".join(parts))


_EXP_RE = [(c, _compile(ks)) for c, ks in EXPENSE_RULES]
_INC_RE = [(c, _compile(ks)) for c, ks in INCOME_RULES]
_TRANSFER_RE = _compile(TRANSFER_KEYWORDS)
_HINT_RE = _compile(INCOME_HINTS)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def rule_key(desc: str) -> str:
    """把描述归一化为可学习规则的键（去掉数字编号等易变部分）。"""
    s = _norm(desc)
    s = re.sub(r"[#*]?\d{4,}", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/|")
    return s[:40]


def is_transfer(desc: str) -> bool:
    return bool(_TRANSFER_RE.search(_norm(desc)))


def looks_like_income(desc: str) -> bool:
    return bool(_HINT_RE.search(_norm(desc)))


def categorize(desc: str, kind: str, learned: dict | None = None) -> str:
    """返回分类名称。kind: expense / income / transfer"""
    if kind == "transfer":
        return TRANSFER_CATEGORY
    s = _norm(desc)
    if learned:
        hit = learned.get(rule_key(desc))
        if hit and hit.get("kind") == kind:
            return hit["category"]
    for cat, rx in (_INC_RE if kind == "income" else _EXP_RE):
        if rx.search(s):
            return cat
    return "其他收入" if kind == "income" else "其他支出"
