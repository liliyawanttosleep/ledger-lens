# -*- coding: utf-8 -*-
"""后端文案的多语言模板（分类名、健康分、建议）。界面文字的翻译在 web/mobile/i18n.js。
数据库里的分类名始终是中文键，显示时再翻译。新增语言：给每个字典补一列即可。"""

LANGS = ["zh", "en", "fr", "es", "ko"]

CAT = {
    "餐饮美食": ("Dining", "Restauration", "Restaurantes", "식비"),
    "超市日用": ("Groceries", "Courses", "Supermercado", "장보기"),
    "购物消费": ("Shopping", "Shopping", "Compras", "쇼핑"),
    "交通出行": ("Transport", "Transport", "Transporte", "교통"),
    "住房物业": ("Housing & bills", "Logement", "Vivienda", "주거·공과금"),
    "通讯订阅": ("Subscriptions", "Abonnements", "Suscripciones", "통신·구독"),
    "娱乐休闲": ("Entertainment", "Loisirs", "Ocio", "여가"),
    "医疗健康": ("Health", "Santé", "Salud", "의료"),
    "教育学习": ("Education", "Éducation", "Educación", "교육"),
    "旅行住宿": ("Travel", "Voyages", "Viajes", "여행"),
    "人情往来": ("Gifts & friends", "Cadeaux & amis", "Regalos y amigos", "경조사·지인"),
    "金融费用": ("Fees & interest", "Frais & intérêts", "Comisiones", "수수료·이자"),
    "其他支出": ("Other spending", "Autres dépenses", "Otros gastos", "기타 지출"),
    "工资薪酬": ("Salary", "Salaire", "Salario", "급여"),
    "奖金补贴": ("Bonus & grants", "Primes & bourses", "Bonos y becas", "상여·보조금"),
    "投资理财": ("Investments", "Placements", "Inversiones", "투자"),
    "退款报销": ("Refunds", "Remboursements", "Reembolsos", "환불"),
    "转账收入": ("Transfers in", "Virements reçus", "Transferencias", "이체 수입"),
    "其他收入": ("Other income", "Autres revenus", "Otros ingresos", "기타 수입"),
    "内部转账": ("Internal transfer", "Virement interne", "Transferencia interna", "내부 이체"),
    "已退货": ("Returned", "Retourné", "Devuelto", "반품"),
    "其他": ("Other", "Autres", "Otros", "기타"),
}


def cat(name: str, lang: str) -> str:
    if lang == "zh" or name not in CAT:
        return name
    return CAT[name][LANGS.index(lang) - 1]


def _t(table, key, lang, **kw):
    row = table[key]
    s = row.get(lang) or row["en"]
    if isinstance(s, tuple):
        return tuple(x.format(**kw) for x in s)
    return s.format(**kw)


MISC = {
    "of_income": {"zh": "收入", "en": "income", "fr": "revenus", "es": "ingresos", "ko": "수입"},
    "of_expense": {"zh": "总支出", "en": "total spending", "fr": "dépenses totales", "es": "gasto total", "ko": "총지출"},
    "many_small": {"zh": "多个类别小幅上涨", "en": "small increases across several categories",
                   "fr": "petites hausses dans plusieurs catégories", "es": "pequeñas subidas en varias categorías",
                   "ko": "여러 분류의 소폭 증가"},
    "etc": {"zh": " 等", "en": " and more", "fr": " etc.", "es": " y más", "ko": " 등"},
    "sep": {"zh": "、", "en": ", ", "fr": ", ", "es": ", ", "ko": ", "},
    "m_exp_inc": {"zh": "支出 / 收入", "en": "Spending vs income", "fr": "Dépenses / revenus", "es": "Gasto / ingresos", "ko": "지출 / 수입"},
    "m_sr": {"zh": "储蓄率", "en": "Savings rate", "fr": "Taux d'épargne", "es": "Tasa de ahorro", "ko": "저축률"},
    "m_exp_avg": {"zh": "本月支出 vs 月均", "en": "This month vs average", "fr": "Ce mois / moyenne", "es": "Este mes / media", "ko": "이번 달 / 평균"},
    "m_fixed": {"zh": "固定扣费", "en": "Recurring charges", "fr": "Prélèvements", "es": "Cargos fijos", "ko": "고정 결제"},
    "m_small": {"zh": "小额消费", "en": "Small purchases", "fr": "Petits achats", "es": "Compras pequeñas", "ko": "소액 지출"},
    "m_fees": {"zh": "手续费/利息", "en": "Fees & interest", "fr": "Frais & intérêts", "es": "Comisiones", "ko": "수수료·이자"},
    "m_inc_avg": {"zh": "本月收入 vs 月均", "en": "Income vs average", "fr": "Revenus / moyenne", "es": "Ingresos / media", "ko": "수입 / 평균"},
    "m_proj": {"zh": "预计全月支出", "en": "Projected spending", "fr": "Dépenses projetées", "es": "Gasto previsto", "ko": "예상 지출"},
    # 健康分
    "p_save": {"zh": "储蓄能力", "en": "Saving", "fr": "Épargne", "es": "Ahorro", "ko": "저축"},
    "p_stable": {"zh": "支出稳定", "en": "Stability", "fr": "Stabilité", "es": "Estabilidad", "ko": "안정성"},
    "p_struct": {"zh": "消费结构", "en": "Mix", "fr": "Structure", "es": "Estructura", "ko": "구성"},
    "p_fee": {"zh": "费用控制", "en": "Fees", "fr": "Frais", "es": "Comisiones", "ko": "수수료"},
    "p_income": {"zh": "收入稳定", "en": "Income", "fr": "Revenus", "es": "Ingresos", "ko": "수입"},
    "n_save": {"zh": "储蓄率 {sr}%（目标 ≥ 20%）", "en": "Savings rate {sr}% (target ≥ 20%)", "fr": "Taux d'épargne {sr} % (objectif ≥ 20 %)",
               "es": "Ahorro {sr} % (objetivo ≥ 20 %)", "ko": "저축률 {sr}% (목표 ≥ 20%)"},
    "n_vs_avg": {"zh": "为近 {n} 月均值的 {pct}%", "en": "{pct}% of the {n}-month average", "fr": "{pct} % de la moyenne sur {n} mois",
                 "es": "{pct} % de la media de {n} meses", "ko": "최근 {n}개월 평균의 {pct}%"},
    "n_flex": {"zh": "弹性消费占 {pct}%", "en": "Discretionary: {pct}%", "fr": "Dépenses flexibles : {pct} %", "es": "Gasto flexible: {pct} %", "ko": "선택 지출 {pct}%"},
    "n_fee0": {"zh": "无手续费/利息", "en": "No fees or interest", "fr": "Aucun frais ni intérêt", "es": "Sin comisiones", "ko": "수수료·이자 없음"},
    "n_fee": {"zh": "手续费/利息 {amt}", "en": "Fees & interest {amt}", "fr": "Frais & intérêts {amt}", "es": "Comisiones {amt}", "ko": "수수료·이자 {amt}"},
}

TIP = {
    "餐饮美食": {"zh": "外卖和堂食是最容易压缩的一项：每周固定 2–3 天自己做饭或带饭，通常能省下 20%–30%。",
              "en": "Eating out is the easiest line to trim: cook or pack lunch 2–3 days a week and you typically save 20–30%.",
              "fr": "Les repas à l'extérieur sont le poste le plus facile à réduire : cuisinez 2 à 3 jours par semaine pour économiser 20 à 30 %.",
              "es": "Comer fuera es lo más fácil de recortar: cocina o lleva comida 2–3 días por semana y ahorrarás un 20–30 %.",
              "ko": "외식·배달은 가장 줄이기 쉬운 항목입니다. 주 2~3일만 직접 해 먹어도 보통 20~30% 절약됩니다."},
    "住房物业": {"zh": "住房成本短期难降。续租时可以比较合租/更远一站的房源，或核对水电网套餐是否有更优惠的档位。",
              "en": "Housing is hard to cut quickly. At renewal compare shared or slightly farther places, and check for cheaper utility and internet plans.",
              "fr": "Le logement se réduit difficilement à court terme. Au renouvellement, comparez colocation ou quartiers voisins et vérifiez vos forfaits.",
              "es": "La vivienda es difícil de bajar a corto plazo. Al renovar, compara pisos compartidos o algo más lejos y revisa tus tarifas.",
              "ko": "주거비는 단기간에 줄이기 어렵습니다. 재계약 때 셰어하우스나 한 정거장 먼 곳을 비교하고 공과금·인터넷 요금제를 점검하세요."},
    "购物消费": {"zh": "给非必需购物设“24 小时冷静期”：先加购物车，隔天还想要再下单。",
              "en": "Give non-essential purchases a 24-hour cooling-off: add to cart, and buy only if you still want it tomorrow.",
              "fr": "Imposez 24 h de réflexion aux achats non essentiels : mettez au panier et n'achetez que si l'envie persiste le lendemain.",
              "es": "Aplica 24 horas de espera a las compras no esenciales: al carrito, y compra solo si mañana lo sigues queriendo.",
              "ko": "꼭 필요하지 않은 구매는 ‘24시간 보류’하세요. 장바구니에 담고 다음 날에도 원하면 결제합니다."},
    "娱乐休闲": {"zh": "给娱乐设一个固定月额度，用完即止；游戏充值、直播打赏建议关闭免密支付。",
              "en": "Set a fixed monthly fun budget and stop when it is used up; turn off one-tap payments for games and tipping.",
              "fr": "Fixez un budget loisirs mensuel et arrêtez-vous une fois épuisé ; désactivez le paiement en un clic pour les jeux.",
              "es": "Fija un presupuesto mensual de ocio y para cuando se agote; desactiva el pago con un toque en juegos.",
              "ko": "여가 예산을 월 고정액으로 정하고 다 쓰면 멈추세요. 게임 결제·후원은 간편결제를 꺼 두는 것이 좋습니다."},
}

ADV = {
    "no_income": {
        "zh": ("还没有本月的收入记录", "只导入了支出流水，无法计算结余和储蓄率。", "导入工资条、到账截图或含入账记录的流水（导入时选“收入凭证”），分析会更完整。"),
        "en": ("No income recorded this month", "Only spending was imported, so balance and savings rate cannot be calculated.", "Import a payslip, a deposit screenshot or a statement that shows deposits (choose “Income proof”) for a complete picture."),
        "fr": ("Aucun revenu enregistré ce mois-ci", "Seules des dépenses ont été importées : solde et taux d'épargne ne peuvent pas être calculés.", "Importez une fiche de paie, une capture de virement ou un relevé avec des crédits (choisissez « Justificatif de revenu »)."),
        "es": ("Sin ingresos registrados este mes", "Solo se importaron gastos, así que no se puede calcular el saldo ni el ahorro.", "Importa una nómina, una captura del abono o un extracto con ingresos (elige «Justificante de ingreso»)."),
        "ko": ("이번 달 수입 기록이 없습니다", "지출 내역만 가져와서 잔액과 저축률을 계산할 수 없습니다.", "급여명세서, 입금 캡처 또는 입금 내역이 있는 명세서를 가져오세요(‘수입 증빙’ 선택)."),
    },
    "overspend": {
        "zh": ("本月入不敷出，超支 {over}", "收入 {income}，支出 {expense}，支出是收入的 {ratio}%。", "下月先把总支出压回收入以内：按下方“建议预算”执行可减少约 {potential}；同时检查超支是否来自一次性大额（学费、房租押金等），若是则无需过度担心。"),
        "en": ("You spent {over} more than you earned", "Income {income}, spending {expense} — spending is {ratio}% of income.", "Next month, bring spending back under income first: the suggested budget below cuts about {potential}. Also check whether a one-off item (tuition, deposit) caused it; if so, no need to worry too much."),
        "fr": ("Vous avez dépensé {over} de plus que vos revenus", "Revenus {income}, dépenses {expense} — soit {ratio} % des revenus.", "Le mois prochain, ramenez d'abord les dépenses sous les revenus : le budget conseillé ci-dessous économise environ {potential}. Vérifiez aussi s'il s'agit d'une dépense ponctuelle (scolarité, caution)."),
        "es": ("Gastaste {over} más de lo que ingresaste", "Ingresos {income}, gasto {expense}: el gasto es el {ratio} % de los ingresos.", "El mes próximo, primero vuelve a gastar menos de lo que ingresas: el presupuesto sugerido recorta unos {potential}. Revisa si fue un gasto puntual (matrícula, fianza)."),
        "ko": ("이번 달 {over} 초과 지출", "수입 {income}, 지출 {expense} — 지출이 수입의 {ratio}%입니다.", "다음 달에는 먼저 총지출을 수입 안으로 줄이세요. 아래 ‘권장 예산’대로면 약 {potential} 절감됩니다. 등록금·보증금 같은 일회성 지출 때문인지도 확인하세요."),
    },
    "low_save": {
        "zh": ("储蓄率偏低：{sr}%", "本月结余 {net}。常用的参考线是把收入的 20% 留作储蓄。", "要达到 20%，每月需再多留出 {gap}。建议发薪当天先把这笔钱转入单独的储蓄账户，剩下的再用于开销。"),
        "en": ("Low savings rate: {sr}%", "You kept {net} this month. A common guideline is to save 20% of income.", "To reach 20% you need to set aside {gap} more each month. Move it to a separate savings account on payday and spend from what is left."),
        "fr": ("Taux d'épargne faible : {sr} %", "Il vous reste {net} ce mois-ci. On conseille généralement d'épargner 20 % de ses revenus.", "Pour atteindre 20 %, mettez {gap} de plus de côté chaque mois, dès le jour de paie, sur un compte séparé."),
        "es": ("Tasa de ahorro baja: {sr} %", "Este mes te quedaron {net}. La referencia habitual es ahorrar el 20 % de los ingresos.", "Para llegar al 20 % necesitas apartar {gap} más al mes. Pásalo a una cuenta de ahorro el día de cobro."),
        "ko": ("저축률이 낮습니다: {sr}%", "이번 달 남은 금액은 {net}입니다. 보통 수입의 20% 저축을 권장합니다.", "20%에 도달하려면 매달 {gap}을 더 남겨야 합니다. 월급날 바로 별도 저축 계좌로 옮기세요."),
    },
    "near_save": {
        "zh": ("储蓄率 {sr}%，接近 20% 目标", "本月结余 {net}，再多留 {gap} 即可达标。", "从弹性最大的一两类开销里各减一点，比全面压缩更容易坚持。"),
        "en": ("Savings rate {sr}% — close to the 20% target", "You kept {net}; {gap} more gets you there.", "Trim a little from the one or two most flexible categories — easier to sustain than cutting everything."),
        "fr": ("Taux d'épargne {sr} % — proche de l'objectif de 20 %", "Il vous reste {net} ; encore {gap} et l'objectif est atteint.", "Réduisez un peu une ou deux catégories flexibles : plus tenable que de tout comprimer."),
        "es": ("Ahorro del {sr} %: cerca del objetivo del 20 %", "Te quedaron {net}; con {gap} más lo alcanzas.", "Recorta un poco en una o dos categorías flexibles: es más sostenible que recortar todo."),
        "ko": ("저축률 {sr}% — 목표 20%에 근접", "이번 달 {net} 남았고, {gap}만 더 남기면 달성합니다.", "가장 유동적인 한두 분류에서 조금씩 줄이는 편이 전체를 줄이는 것보다 지키기 쉽습니다."),
    },
    "good_save": {
        "zh": ("储蓄率 {sr}%，状态健康", "本月结余 {net}，已超过 20% 的参考线。", "保持当前节奏。结余可以按“应急金 → 定期/货币基金 → 长期投资”的顺序安排。"),
        "en": ("Savings rate {sr}% — healthy", "You kept {net}, above the 20% guideline.", "Keep this pace. Allocate the surplus in order: emergency fund → savings/money market → long-term investing."),
        "fr": ("Taux d'épargne {sr} % — sain", "Il vous reste {net}, au-dessus du repère de 20 %.", "Gardez ce rythme. Affectez l'excédent : épargne de précaution → livret → investissement long terme."),
        "es": ("Ahorro del {sr} %: saludable", "Te quedaron {net}, por encima de la referencia del 20 %.", "Mantén el ritmo. Destina el excedente: fondo de emergencia → depósito → inversión a largo plazo."),
        "ko": ("저축률 {sr}% — 양호", "이번 달 {net} 남아 기준선 20%를 넘었습니다.", "지금 흐름을 유지하세요. 남는 돈은 비상금 → 예금/MMF → 장기 투자 순으로 배분합니다."),
    },
    "exp_up": {
        "zh": ("总支出比近 {n} 个月均值高 {pct}%", "本月 {expense}，此前月均 {avg}，多花了 {diff}。主要来自：{drivers}。", "逐项看这几类里是否有一次性支出；属于习惯性上涨的，下月按建议预算设上限。"),
        "en": ("Spending is {pct}% above the {n}-month average", "{expense} this month vs {avg} on average — {diff} more. Mainly: {drivers}.", "Check whether those categories include one-off items; for habitual increases, cap them with the suggested budget."),
        "fr": ("Dépenses {pct} % au-dessus de la moyenne sur {n} mois", "{expense} ce mois-ci contre {avg} en moyenne, soit {diff} de plus. Principalement : {drivers}.", "Vérifiez s'il s'agit de dépenses ponctuelles ; sinon, plafonnez-les avec le budget conseillé."),
        "es": ("Gasto un {pct} % por encima de la media de {n} meses", "{expense} este mes frente a {avg} de media: {diff} más. Sobre todo: {drivers}.", "Mira si hay gastos puntuales; si es una subida habitual, ponle tope con el presupuesto sugerido."),
        "ko": ("총지출이 최근 {n}개월 평균보다 {pct}% 높습니다", "이번 달 {expense}, 평균 {avg} — {diff} 더 썼습니다. 주요 원인: {drivers}.", "해당 분류에 일회성 지출이 있는지 확인하고, 습관적 증가라면 권장 예산으로 상한을 두세요."),
    },
    "exp_down": {
        "zh": ("总支出比近 {n} 个月均值低 {pct}%", "本月 {expense}，此前月均 {avg}，少花了 {diff}。", "把省下的部分直接转入储蓄，避免下月被“报复性消费”抵消。"),
        "en": ("Spending is {pct}% below the {n}-month average", "{expense} this month vs {avg} on average — {diff} less.", "Move what you saved straight into savings so it is not spent back next month."),
        "fr": ("Dépenses {pct} % sous la moyenne sur {n} mois", "{expense} ce mois-ci contre {avg} en moyenne, soit {diff} de moins.", "Versez cette économie directement sur votre épargne pour ne pas la redépenser."),
        "es": ("Gasto un {pct} % por debajo de la media de {n} meses", "{expense} este mes frente a {avg} de media: {diff} menos.", "Pasa lo ahorrado directamente a tu cuenta de ahorro para no gastarlo el mes que viene."),
        "ko": ("총지출이 최근 {n}개월 평균보다 {pct}% 낮습니다", "이번 달 {expense}, 평균 {avg} — {diff} 덜 썼습니다.", "아낀 금액은 바로 저축으로 옮겨 다음 달에 다시 쓰지 않도록 하세요."),
    },
    "cat_up_flex": {
        "zh": ("{cat}上涨 {pct}%", "本月 {amount}（{count} 笔），此前月均 {base}，多出 {up}。", "这是弹性开销，下月建议控制在 {cap} 以内。"),
        "en": ("{cat} up {pct}%", "{amount} this month ({count} transactions) vs {base} on average — {up} more.", "This is discretionary; aim to keep it under {cap} next month."),
        "fr": ("{cat} : +{pct} %", "{amount} ce mois-ci ({count} opérations) contre {base} en moyenne, soit {up} de plus.", "C'est une dépense flexible : visez moins de {cap} le mois prochain."),
        "es": ("{cat}: +{pct} %", "{amount} este mes ({count} movimientos) frente a {base} de media: {up} más.", "Es gasto flexible: intenta no pasar de {cap} el mes próximo."),
        "ko": ("{cat} {pct}% 증가", "이번 달 {amount}({count}건), 평균 {base} — {up} 증가.", "선택 지출이므로 다음 달에는 {cap} 이내로 관리하세요."),
    },
    "cat_up_ess": {
        "zh": ("{cat}上涨 {pct}%", "本月 {amount}（{count} 笔），此前月均 {base}，多出 {up}。", "这类属于必需开销，先确认是否为一次性（如年付、押金）；若是持续上涨，考虑换更便宜的方案。"),
        "en": ("{cat} up {pct}%", "{amount} this month ({count} transactions) vs {base} on average — {up} more.", "This is an essential cost. Check whether it is a one-off (annual payment, deposit); if it keeps rising, look for a cheaper plan."),
        "fr": ("{cat} : +{pct} %", "{amount} ce mois-ci ({count} opérations) contre {base} en moyenne, soit {up} de plus.", "Dépense essentielle : vérifiez si elle est ponctuelle (paiement annuel, caution) ; sinon, cherchez une offre moins chère."),
        "es": ("{cat}: +{pct} %", "{amount} este mes ({count} movimientos) frente a {base} de media: {up} más.", "Es un gasto esencial: comprueba si es puntual (pago anual, fianza); si sigue subiendo, busca una opción más barata."),
        "ko": ("{cat} {pct}% 증가", "이번 달 {amount}({count}건), 평균 {base} — {up} 증가.", "필수 지출입니다. 연납·보증금 같은 일회성인지 확인하고, 계속 오른다면 더 저렴한 요금제를 알아보세요."),
    },
    "share": {
        "zh": ("{cat}占{base_name}的 {pct}%，偏高", "本月{cat} {amount}，一般建议不超过{base_name}的 {limit}%（约 {target}）。", "{tip}"),
        "en": ("{cat} is {pct}% of {base_name} — high", "{cat} was {amount}; a common guideline is at most {limit}% of {base_name} (about {target}).", "{tip}"),
        "fr": ("{cat} : {pct} % des {base_name} — élevé", "{cat} : {amount} ; on conseille au plus {limit} % des {base_name} (environ {target}).", "{tip}"),
        "es": ("{cat}: {pct} % de {base_name}, alto", "{cat}: {amount}; se recomienda como máximo el {limit} % de {base_name} (unos {target}).", "{tip}"),
        "ko": ("{cat}이(가) {base_name}의 {pct}% — 높음", "이번 달 {cat} {amount}. 보통 {base_name}의 {limit}%(약 {target}) 이내를 권장합니다.", "{tip}"),
    },
    "subs": {
        "zh": ("发现 {n} 项固定扣费，合计 {total}/月", "包括：{names}。一年约 {year}。", "逐项问自己“过去 30 天用过吗？”，没用过的直接退订；视频/音乐类可以改成需要时再开一个月。"),
        "en": ("{n} recurring charges, {total} per month", "Including: {names}. About {year} a year.", "For each one ask “did I use it in the last 30 days?” Cancel the ones you did not; subscribe to video or music only in the months you need them."),
        "fr": ("{n} prélèvements récurrents, {total} par mois", "Dont : {names}. Environ {year} par an.", "Pour chacun : « l'ai-je utilisé ces 30 derniers jours ? » Résiliez les autres ; ne prenez vidéo ou musique que les mois utiles."),
        "es": ("{n} cargos fijos, {total} al mes", "Incluye: {names}. Unos {year} al año.", "Pregúntate por cada uno: «¿lo usé en los últimos 30 días?». Cancela los que no; contrata vídeo o música solo cuando los necesites."),
        "ko": ("고정 결제 {n}건, 월 {total}", "포함: {names}. 연 약 {year}.", "항목마다 ‘최근 30일에 썼나?’를 확인하고 안 쓴 것은 해지하세요. 영상·음악은 필요한 달에만 구독해도 됩니다."),
    },
    "small": {
        "zh": ("{n} 笔小额消费累计 {sum}", "单笔不超过 {cap} 的零散支出（咖啡、奶茶、零食、小件）占总支出的 {share}%，平均每天 {perday} 笔。", "不用全戒：把频率减掉三分之一，一个月就能省约 {save}。"),
        "en": ("{n} small purchases add up to {sum}", "Purchases of {cap} or less (coffee, snacks, small items) are {share}% of spending — {perday} a day on average.", "No need to quit: cut the frequency by a third and you save about {save} a month."),
        "fr": ("{n} petits achats totalisent {sum}", "Les achats de {cap} ou moins (café, en-cas, petits articles) font {share} % des dépenses, soit {perday} par jour.", "Inutile d'arrêter : réduisez la fréquence d'un tiers et économisez environ {save} par mois."),
        "es": ("{n} compras pequeñas suman {sum}", "Las compras de {cap} o menos (café, snacks, cosas pequeñas) son el {share} % del gasto: {perday} al día.", "No hace falta eliminarlas: reduce la frecuencia un tercio y ahorras unos {save} al mes."),
        "ko": ("소액 지출 {n}건, 합계 {sum}", "{cap} 이하 소액 지출(커피·간식·소품)이 총지출의 {share}%, 하루 평균 {perday}건입니다.", "끊을 필요는 없습니다. 빈도를 3분의 1만 줄여도 월 약 {save} 절약됩니다."),
    },
    "big": {
        "zh": ("单笔最大支出占全月 {pct}%", "{date} {desc}：{amount}（{cat}）。", "如果是房租、学费这类可预见的大额支出，建议每月提前预留等额资金，避免集中支付时现金吃紧。"),
        "en": ("Largest single expense is {pct}% of the month", "{date} {desc}: {amount} ({cat}).", "If it is predictable (rent, tuition), set the amount aside in advance each month so the payment does not squeeze your cash."),
        "fr": ("La plus grosse dépense représente {pct} % du mois", "{date} {desc} : {amount} ({cat}).", "Si elle est prévisible (loyer, scolarité), provisionnez-la chaque mois pour ne pas tendre votre trésorerie."),
        "es": ("El mayor gasto es el {pct} % del mes", "{date} {desc}: {amount} ({cat}).", "Si es previsible (alquiler, matrícula), aparta el importe cada mes para no quedarte corto al pagarlo."),
        "ko": ("가장 큰 단일 지출이 한 달의 {pct}%", "{date} {desc}: {amount} ({cat}).", "월세·등록금처럼 예측 가능한 지출이라면 매달 미리 같은 금액을 떼어 두세요."),
    },
    "fees": {
        "zh": ("本月支付手续费/利息 {amount}", "这类支出没有换来任何商品或服务，是最应该先消掉的一项。", "信用卡设全额自动还款避免利息；跨行/境外取现改用免手续费的卡；有年费的卡确认是否达到免年费条件。"),
        "en": ("You paid {amount} in fees and interest", "This buys you nothing — it is the first thing to eliminate.", "Set credit cards to autopay the full balance; use a no-fee card for ATM and foreign transactions; check whether annual fees can be waived."),
        "fr": ("{amount} de frais et intérêts ce mois-ci", "Cette dépense ne vous apporte rien : c'est la première à supprimer.", "Réglez la carte en totalité par prélèvement ; utilisez une carte sans frais pour les retraits et l'étranger ; vérifiez les cotisations annuelles."),
        "es": ("Pagaste {amount} en comisiones e intereses", "Este gasto no te da nada a cambio: es lo primero que hay que eliminar.", "Domicilia el pago total de la tarjeta; usa una tarjeta sin comisiones para cajeros y extranjero; revisa las cuotas anuales."),
        "ko": ("이번 달 수수료·이자 {amount}", "아무것도 얻지 못하는 지출이라 가장 먼저 없애야 합니다.", "신용카드는 전액 자동납부로 이자를 피하고, 출금·해외 결제는 수수료 없는 카드를 쓰며, 연회비 면제 조건을 확인하세요."),
    },
    "weekend": {
        "zh": ("周末花掉了全月的 {pct}%", "两天的开销接近或超过五个工作日的总和，支出集中在周末的聚餐、购物和娱乐。", "周末出门前先定一个当日上限；聚餐与购物尽量不安排在同一天。"),
        "en": ("Weekends account for {pct}% of spending", "Two days cost about as much as the five weekdays — mostly meals out, shopping and entertainment.", "Set a daily cap before going out at weekends, and avoid dining out and shopping on the same day."),
        "fr": ("Les week-ends pèsent {pct} % des dépenses", "Deux jours coûtent presque autant que les cinq jours ouvrés : restaurants, achats et loisirs.", "Fixez un plafond journalier avant de sortir le week-end et évitez restaurant et shopping le même jour."),
        "es": ("Los fines de semana son el {pct} % del gasto", "Dos días cuestan casi lo mismo que los cinco laborables: comidas fuera, compras y ocio.", "Ponte un tope diario antes de salir el fin de semana y evita comer fuera y comprar el mismo día."),
        "ko": ("주말 지출이 한 달의 {pct}%", "이틀의 지출이 평일 5일과 비슷합니다. 외식·쇼핑·여가가 주말에 몰려 있습니다.", "주말에 나가기 전 하루 한도를 정하고, 외식과 쇼핑을 같은 날에 잡지 마세요."),
    },
    "inc_down": {
        "zh": ("收入比近 {n} 个月均值少 {pct}%", "本月 {income}，此前月均 {avg}。", "先确认是否有收入尚未到账或未导入；若确实下降，下月的弹性开销建议同比例下调。"),
        "en": ("Income is {pct}% below the {n}-month average", "{income} this month vs {avg} on average.", "First check whether some income has not arrived or was not imported; if it really dropped, cut discretionary spending by the same proportion."),
        "fr": ("Revenus {pct} % sous la moyenne sur {n} mois", "{income} ce mois-ci contre {avg} en moyenne.", "Vérifiez d'abord qu'un revenu n'est pas en attente ou non importé ; sinon, réduisez d'autant les dépenses flexibles."),
        "es": ("Ingresos un {pct} % por debajo de la media de {n} meses", "{income} este mes frente a {avg} de media.", "Comprueba si falta algún ingreso por llegar o importar; si de verdad bajó, reduce el gasto flexible en la misma proporción."),
        "ko": ("수입이 최근 {n}개월 평균보다 {pct}% 적습니다", "이번 달 {income}, 평균 {avg}.", "아직 입금되지 않았거나 가져오지 않은 수입이 있는지 먼저 확인하고, 실제로 줄었다면 선택 지출도 같은 비율로 줄이세요."),
    },
    "inc_up": {
        "zh": ("收入比近 {n} 个月均值高 {pct}%", "本月 {income}，此前月均 {avg}。", "多出来的 {extra} 建议至少存下一半，避免开销随收入同步上涨。"),
        "en": ("Income is {pct}% above the {n}-month average", "{income} this month vs {avg} on average.", "Save at least half of the extra {extra} so spending does not rise with income."),
        "fr": ("Revenus {pct} % au-dessus de la moyenne sur {n} mois", "{income} ce mois-ci contre {avg} en moyenne.", "Épargnez au moins la moitié des {extra} supplémentaires pour ne pas augmenter vos dépenses."),
        "es": ("Ingresos un {pct} % por encima de la media de {n} meses", "{income} este mes frente a {avg} de media.", "Ahorra al menos la mitad de los {extra} extra para que el gasto no suba con los ingresos."),
        "ko": ("수입이 최근 {n}개월 평균보다 {pct}% 많습니다", "이번 달 {income}, 평균 {avg}.", "늘어난 {extra}의 절반 이상은 저축해 지출이 수입과 함께 늘지 않도록 하세요."),
    },
    "inc_other": {
        "zh": ("大部分收入被归为“转账/其他”", "{cat}占收入的 {pct}%，可能包含亲友转账、自己账户互转等。", "在“交易明细”里把不属于真实收入的记录改为“不计收支”，储蓄率才会准确。"),
        "en": ("Most income is “transfers / other”", "{cat} is {pct}% of income and may include money from friends or your own accounts.", "In Transactions, change records that are not real income to “Excluded” so the savings rate is accurate."),
        "fr": ("La plupart des revenus sont « virements / autres »", "{cat} représente {pct} % des revenus et peut inclure des virements d'amis ou entre vos comptes.", "Dans Opérations, passez en « Exclu » ce qui n'est pas un vrai revenu pour un taux d'épargne exact."),
        "es": ("La mayoría de los ingresos son «transferencias / otros»", "{cat} es el {pct} % de los ingresos y puede incluir dinero de amigos o entre tus cuentas.", "En Movimientos, cambia a «Excluido» lo que no sea ingreso real para que el ahorro sea exacto."),
        "ko": ("수입 대부분이 ‘이체/기타’입니다", "{cat}이(가) 수입의 {pct}%이며 지인 송금이나 본인 계좌 간 이체가 섞였을 수 있습니다.", "‘거래 내역’에서 실제 수입이 아닌 기록을 ‘집계 제외’로 바꿔야 저축률이 정확해집니다."),
    },
    "pace_warn": {
        "zh": ("按目前节奏，本月预计支出 {proj}", "已过 {d}/{dm} 天，花了 {expense}；参考值（往月）为 {base}。", "剩余 {left} 天日均控制在 {perday} 以内，才能与往月持平。"),
        "en": ("At this pace you will spend {proj} this month", "{d} of {dm} days gone, {expense} spent; the usual level is {base}.", "Keep to {perday} a day for the remaining {left} days to match previous months."),
        "fr": ("À ce rythme, {proj} de dépenses ce mois-ci", "{d} jours sur {dm} écoulés, {expense} dépensés ; niveau habituel : {base}.", "Limitez-vous à {perday} par jour pendant les {left} jours restants pour rester au niveau habituel."),
        "es": ("A este ritmo gastarás {proj} este mes", "Van {d} de {dm} días y {expense} gastados; lo habitual es {base}.", "No pases de {perday} al día en los {left} días que quedan para igualar meses anteriores."),
        "ko": ("지금 속도면 이번 달 지출 예상 {proj}", "{dm}일 중 {d}일 경과, {expense} 사용. 평소 수준은 {base}.", "남은 {left}일 동안 하루 {perday} 이내로 써야 평소 수준에 맞습니다."),
    },
    "pace_ok": {
        "zh": ("按目前节奏，本月预计支出 {proj}", "已过 {d}/{dm} 天，花了 {expense}；参考值（往月）为 {base}。", "进度正常，保持即可。"),
        "en": ("At this pace you will spend {proj} this month", "{d} of {dm} days gone, {expense} spent; the usual level is {base}.", "On track — keep it up."),
        "fr": ("À ce rythme, {proj} de dépenses ce mois-ci", "{d} jours sur {dm} écoulés, {expense} dépensés ; niveau habituel : {base}.", "Vous êtes dans les clous, continuez ainsi."),
        "es": ("A este ritmo gastarás {proj} este mes", "Van {d} de {dm} días y {expense} gastados; lo habitual es {base}.", "Vas bien, sigue así."),
        "ko": ("지금 속도면 이번 달 지출 예상 {proj}", "{dm}일 중 {d}일 경과, {expense} 사용. 평소 수준은 {base}.", "정상 범위입니다. 그대로 유지하세요."),
    },
    "efund_pos": {
        "zh": ("应急金参考：{lo} – {hi}", "按月均支出 {base} 计算，建议常备 3–6 个月的生活费，放在随时可取的账户里。", "按本月结余 {net} 的速度，约 {months} 个月可以攒够 3 个月应急金。"),
        "en": ("Emergency fund guide: {lo} – {hi}", "Based on average spending of {base}, keep 3–6 months of expenses in an account you can access anytime.", "At this month's surplus of {net}, it takes about {months} months to build 3 months of cover."),
        "fr": ("Épargne de précaution : {lo} – {hi}", "Avec {base} de dépenses mensuelles, gardez 3 à 6 mois de dépenses sur un compte disponible à tout moment.", "Avec l'excédent du mois ({net}), il faut environ {months} mois pour constituer 3 mois de réserve."),
        "es": ("Fondo de emergencia: {lo} – {hi}", "Con un gasto medio de {base}, conviene tener 3–6 meses de gastos en una cuenta disponible.", "Con el excedente de este mes ({net}), tardarías unos {months} meses en reunir 3 meses de colchón."),
        "ko": ("비상금 기준: {lo} – {hi}", "월평균 지출 {base} 기준으로 3~6개월치 생활비를 언제든 찾을 수 있는 계좌에 두세요.", "이번 달 잉여 {net} 속도라면 약 {months}개월이면 3개월치 비상금이 모입니다."),
    },
    "efund_neg": {
        "zh": ("应急金参考：{lo} – {hi}", "按月均支出 {base} 计算，建议常备 3–6 个月的生活费，放在随时可取的账户里。", "当前没有结余，先实现收支平衡，再开始积累应急金。"),
        "en": ("Emergency fund guide: {lo} – {hi}", "Based on average spending of {base}, keep 3–6 months of expenses in an account you can access anytime.", "There is no surplus right now — get to break-even first, then start building the fund."),
        "fr": ("Épargne de précaution : {lo} – {hi}", "Avec {base} de dépenses mensuelles, gardez 3 à 6 mois de dépenses sur un compte disponible à tout moment.", "Pas d'excédent pour l'instant : revenez d'abord à l'équilibre, puis constituez cette réserve."),
        "es": ("Fondo de emergencia: {lo} – {hi}", "Con un gasto medio de {base}, conviene tener 3–6 meses de gastos en una cuenta disponible.", "Ahora no hay excedente: primero equilibra ingresos y gastos y luego empieza el fondo."),
        "ko": ("비상금 기준: {lo} – {hi}", "월평균 지출 {base} 기준으로 3~6개월치 생활비를 언제든 찾을 수 있는 계좌에 두세요.", "지금은 남는 돈이 없습니다. 먼저 수지 균형을 맞춘 뒤 비상금을 모으세요."),
    },
    "more_data": {
        "zh": ("再导入一两个月的数据，建议会更准", "目前只有这一个月的数据，无法判断哪些开销是“比平时多”。", "把前几个月的流水也导入进来，就能看到环比变化、趋势和更贴合你习惯的预算建议。"),
        "en": ("Import another month or two for better advice", "With only one month of data it is impossible to tell what is “more than usual”.", "Import earlier statements to see month-over-month changes, trends and a budget that fits your habits."),
        "fr": ("Importez un ou deux mois de plus pour de meilleurs conseils", "Avec un seul mois, impossible de savoir ce qui est « plus que d'habitude ».", "Importez les relevés précédents pour voir les évolutions, les tendances et un budget adapté à vos habitudes."),
        "es": ("Importa uno o dos meses más para mejores consejos", "Con un solo mes no se puede saber qué es «más de lo habitual».", "Importa extractos anteriores para ver la evolución, las tendencias y un presupuesto adaptado a ti."),
        "ko": ("한두 달 더 가져오면 조언이 정확해집니다", "한 달 데이터만으로는 무엇이 ‘평소보다 많은지’ 판단할 수 없습니다.", "이전 달 명세서도 가져오면 전월 대비 변화, 추세, 습관에 맞는 예산을 볼 수 있습니다."),
    },
}


def adv(key, lang, **kw):
    return _t(ADV, key, lang, **kw)


def misc(key, lang, **kw):
    return _t(MISC, key, lang, **kw)


def tip(category, lang):
    return TIP[category].get(lang) or TIP[category]["en"]
