/* 界面多语言（电脑端与手机端共用）。
 * 源码里的界面文字一律写中文；这里在渲染后把页面上的中文替换成所选语言：
 *   1. SUBS  —— 带数字的句式（正则）      2. DICT —— 整句 / 短语对照（最长优先）
 * 用户自己的数据（商户名、描述）放在带 data-raw 或 .desc 的元素里，不会被翻译。
 * 后端生成的建议文案由 app/i18n.py 按语言直接生成，不走这里。
 * 新增语言：在 LANGS 加一项，并给 SUBS / DICT 每行补一列。列顺序：en, fr, es, ko。 */
(function () {
  'use strict';
  const LANGS = [['zh', '中文'], ['en', 'English'], ['fr', 'Français'], ['es', 'Español'], ['ko', '한국어']];
  const LOCALE = { zh: 'zh-CN', en: 'en-US', fr: 'fr-FR', es: 'es-ES', ko: 'ko-KR' };
  const COL = { en: 0, fr: 1, es: 2, ko: 3 };
  let lang = 'zh';
  const rev = new Map();

  const month = m => lang === 'zh' ? `${m.slice(0, 4)}年${+m.slice(5, 7)}月`
    : new Intl.DateTimeFormat(LOCALE[lang], { year: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(m.slice(0, 7) + '-01T00:00:00Z'));
  const mshort = n => lang === 'zh' ? `${+n}月` : new Intl.DateTimeFormat(LOCALE[lang], { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, n - 1, 1)));
  const mday = (mo, d) => lang === 'zh' ? `${+mo}月${+d}日` : new Intl.DateTimeFormat(LOCALE[lang], { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, mo - 1, d)));
  const weekday = i => new Intl.DateTimeFormat(LOCALE[lang], { weekday: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, 0, 1 + i))); // 2024-01-01 是周一

  /* 带数字的句式：[正则, [en, fr, es, ko]]，$1 $2 为捕获组 */
  const SUBS = [
    [/(\d+) 笔手机记账待同步，连上电脑后计入分析/g, ['$1 phone entries waiting to sync — counted once connected', '$1 saisies en attente de synchronisation', '$1 apuntes pendientes de sincronizar', '휴대폰 기록 $1건 동기화 대기 중']],
    [/已导入 (\d+) 笔交易/g, ['Imported $1 transactions', '$1 opérations importées', '$1 movimientos importados', '거래 $1건 가져옴']],
    [/，另识别出 (\d+) 笔内部转账（不计入收支）/g, [' — $1 recognised as internal/excluded', ' — $1 reconnues comme internes/exclues', ' — $1 reconocidos como internos/excluidos', ' — $1건은 내부 이체/제외로 인식']],
    [/，与已有账单对上 (\d+) 对转账/g, [' — $1 transfer pairs matched with earlier statements', ' — $1 paires de virements rapprochées des relevés précédents', ' — $1 pares de transferencias casados con extractos anteriores', ' — 이전 명세서와 이체 $1쌍 매칭']],
    [/新识别出 (\d+) 笔内部转账/g, ['$1 more recognised as internal/excluded', '$1 de plus reconnues comme internes', '$1 más reconocidos como internos', '추가로 $1건을 내부 이체로 인식']],
    [/手机同步来 (\d+) 笔新记账/g, ['$1 new entries synced from phone', '$1 nouvelles saisies du téléphone', '$1 apuntes nuevos del móvil', '휴대폰에서 새 기록 $1건 동기화']],
    [/共 (\d+) 个文件，已选 (\d+) 笔交易/g, ['$1 files, $2 transactions selected', '$1 fichiers, $2 opérations sélectionnées', '$1 archivos, $2 movimientos seleccionados', '파일 $1개, 거래 $2건 선택']],
    [/识别到 (\d+) 笔/g, ['$1 found', '$1 trouvées', '$1 encontrados', '$1건 인식']],
    [/(\d+) 笔与已有记录重复/g, ['$1 already imported', '$1 déjà importées', '$1 ya importados', '$1건은 기존 기록과 중복']],
    [/导入 (\d+) 笔/g, ['Import $1', 'Importer $1', 'Importar $1', '$1건 가져오기']],
    [/共 (\d+) 笔支出/g, ['$1 expenses', '$1 dépenses', '$1 gastos', '지출 $1건']],
    [/已过 (\d+) 天/g, ['day $1', 'jour $1', 'día $1', '$1일 경과']],
    [/共 (\d+) 笔交易/g, ['$1 transactions', '$1 opérations', '$1 movimientos', '거래 $1건']],
    [/共 (\d+) 笔/g, ['$1 transactions', '$1 opérations', '$1 movimientos', '총 $1건']],
    [/(\d+) 笔收支/g, ['$1 transactions', '$1 opérations', '$1 movimientos', '거래 $1건']],
    [/(\d+) 笔支出/g, ['$1 expenses', '$1 dépenses', '$1 gastos', '지출 $1건']],
    [/(\d+) 笔/g, ['$1 txns', '$1 op.', '$1 mov.', '$1건']],
    [/近 (\d+) 个月支出结构/g, ['Spending mix, last $1 months', 'Structure des dépenses, $1 derniers mois', 'Estructura del gasto, últimos $1 meses', '최근 $1개월 지출 구성']],
    [/本月 vs 近 (\d+) 月均值/g, ['This month vs $1-month average', 'Ce mois / moyenne sur $1 mois', 'Este mes / media de $1 meses', '이번 달 / 최근 $1개월 평균']],
    [/参考近 (\d+) 月均值/g, ['Based on the $1-month average', 'Selon la moyenne sur $1 mois', 'Según la media de $1 meses', '최근 $1개월 평균 기준']],
    [/右侧为较近 (\d+) 月均值/g, ['right: vs $1-month average', 'à droite : vs moyenne $1 mois', 'derecha: vs media $1 meses', '오른쪽: $1개월 평균 대비']],
    [/环比＝较上月\s*较均值＝较近 (\d+) 月平均/g, ['MoM = vs last month · vs avg = vs $1-month average', 'M/M = vs mois dernier · vs moy. = moyenne $1 mois', 'M/M = vs mes anterior · vs media = $1 meses', '전월비 = 지난달 대비 · 평균비 = $1개월 평균 대비']],
    [/近 (\d+) 月均值/g, ['$1-month average', 'Moyenne $1 mois', 'Media $1 meses', '$1개월 평균']],
    [/近 (\d+) 个月收支/g, ['Income & spending, last $1 months', 'Revenus & dépenses, $1 derniers mois', 'Ingresos y gastos, últimos $1 meses', '최근 $1개월 수입·지출']],
    [/近 (\d+) 个月/g, ['Last $1 months', '$1 derniers mois', 'Últimos $1 meses', '최근 $1개월']],
    [/(\d+) 个月/g, ['$1 months', '$1 mois', '$1 meses', '$1개월']],
    [/全部 (\d+) 条 ›/g, ['All $1 ›', 'Les $1 ›', 'Los $1 ›', '전체 $1개 ›']],
    [/(\d+) 条建议 →/g, ['$1 tips →', '$1 conseils →', '$1 consejos →', '조언 $1개 →']],
    [/(\d+) 项需立即关注/g, ['$1 need attention', '$1 à traiter', '$1 urgentes', '즉시 확인 $1개']],
    [/(\d+) 项建议调整/g, ['$1 to adjust', '$1 à ajuster', '$1 por ajustar', '조정 권장 $1개']],
    [/(\d+) 项做得不错/g, ['$1 going well', '$1 positifs', '$1 bien', '양호 $1개']],
    [/收 (\S+) · 支 (\S+)/g, ['in $1 · out $2', 'entrées $1 · sorties $2', 'ingr. $1 · gasto $2', '수입 $1 · 지출 $2']],
    [/一年约 /g, ['about per year: ', 'par an env. ', 'al año aprox. ', '연 약 ']],
    [/显示 (.+?) 同步的数据/g, ['Showing data synced $1', 'Données synchronisées le $1', 'Datos sincronizados el $1', '$1 동기화 데이터 표시']],
    [/显示 (.+?) 的数据/g, ['showing data from $1', 'données du $1', 'datos del $1', '$1 데이터 표시']],
    [/(\d{4})年(\d{1,2})月/g, m => month(`${m[1]}-${String(m[2]).padStart(2, '0')}`)],
    [/(\d{1,2})月(\d{1,2})日/g, m => mday(+m[1], +m[2])],
    [/^(\d{1,2})月$/g, m => mshort(+m[1])],
  ];

  /* 整句 / 短语对照：中文 → [en, fr, es, ko] */
  const DICT = {
    // 分类与类型
    '餐饮美食': ['Dining', 'Restauration', 'Restaurantes', '식비'], '超市日用': ['Groceries', 'Courses', 'Supermercado', '장보기'],
    '购物消费': ['Shopping', 'Shopping', 'Compras', '쇼핑'], '交通出行': ['Transport', 'Transport', 'Transporte', '교통'],
    '住房物业': ['Housing & bills', 'Logement', 'Vivienda', '주거·공과금'], '通讯订阅': ['Subscriptions', 'Abonnements', 'Suscripciones', '통신·구독'],
    '娱乐休闲': ['Entertainment', 'Loisirs', 'Ocio', '여가'], '医疗健康': ['Health', 'Santé', 'Salud', '의료'],
    '教育学习': ['Education', 'Éducation', 'Educación', '교육'], '旅行住宿': ['Travel', 'Voyages', 'Viajes', '여행'],
    '人情往来': ['Gifts & friends', 'Cadeaux & amis', 'Regalos y amigos', '경조사·지인'], '金融费用': ['Fees & interest', 'Frais & intérêts', 'Comisiones', '수수료·이자'],
    '其他支出': ['Other spending', 'Autres dépenses', 'Otros gastos', '기타 지출'], '工资薪酬': ['Salary', 'Salaire', 'Salario', '급여'],
    '奖金补贴': ['Bonus & grants', 'Primes & bourses', 'Bonos y becas', '상여·보조금'], '投资理财': ['Investments', 'Placements', 'Inversiones', '투자'],
    '退款报销': ['Refunds', 'Remboursements', 'Reembolsos', '환불'], '转账收入': ['Transfers in', 'Virements reçus', 'Transferencias', '이체 수입'],
    '其他收入': ['Other income', 'Autres revenus', 'Otros ingresos', '기타 수입'], '内部转账': ['Internal transfer', 'Virement interne', 'Transferencia interna', '내부 이체'],
    '已退货': ['Returned', 'Retourné', 'Devuelto', '반품'], '其他': ['Other', 'Autres', 'Otros', '기타'],
    '收入': ['Income', 'Revenus', 'Ingresos', '수입'], '支出': ['Spending', 'Dépenses', 'Gastos', '지출'], '结余': ['Balance', 'Solde', 'Saldo', '잔액'],
    '不计收支': ['Excluded', 'Exclu', 'Excluido', '집계 제외'], '退款冲减': ['Refund (offsets spending)', 'Remboursement (déduit)', 'Reembolso (descuenta)', '환불(지출 차감)'],
    // 导航与标题
    '流水分析助手': ['Ledger Lens', 'Ledger Lens', 'Ledger Lens', 'Ledger Lens'],
    '本月概览': ['Overview', 'Aperçu', 'Resumen', '이번 달 요약'], '收支分析': ['Analysis', 'Analyse', 'Análisis', '수입·지출 분석'],
    '开销建议': ['Advice', 'Conseils', 'Consejos', '지출 조언'], '交易明细': ['Transactions', 'Opérations', 'Movimientos', '거래 내역'],
    '手机同步': ['Phone sync', 'Synchro mobile', 'Sincronizar móvil', '휴대폰 동기화'], '导入与数据': ['Import & data', 'Import & données', 'Importar y datos', '가져오기·데이터'],
    '概览': ['Overview', 'Aperçu', 'Resumen', '요약'], '分析': ['Analysis', 'Analyse', 'Análisis', '분석'], '建议': ['Advice', 'Conseils', 'Consejos', '조언'],
    '明细': ['Details', 'Détails', 'Detalle', '내역'], '同步': ['Sync', 'Synchro', 'Sincronizar', '동기화'],
    '深色模式': ['Dark mode', 'Mode sombre', 'Modo oscuro', '다크 모드'], '浅色模式': ['Light mode', 'Mode clair', 'Modo claro', '라이트 모드'],
    '数据仅保存在本机': ['Data stays on this device', 'Données stockées sur cet appareil', 'Los datos no salen de este equipo', '데이터는 이 기기에만 저장'],
    '导入文件': ['Import files', 'Importer', 'Importar', '파일 가져오기'], '上个月': ['Previous month', 'Mois précédent', 'Mes anterior', '이전 달'], '下个月': ['Next month', 'Mois suivant', 'Mes siguiente', '다음 달'],
    '语言': ['Language', 'Langue', 'Idioma', '언어'],
    // 概览
    '本月结余': ['Balance this month', 'Solde du mois', 'Saldo del mes', '이번 달 잔액'], '储蓄率': ['Savings rate', "Taux d'épargne", 'Tasa de ahorro', '저축률'],
    '未导入收入，暂无储蓄率': ['No income imported yet', 'Aucun revenu importé', 'Sin ingresos importados', '수입 미등록'],
    '日均支出': ['Daily average', 'Moyenne par jour', 'Media diaria', '일평균 지출'], '较上月': ['vs last month', 'vs mois dernier', 'vs mes anterior', '전월 대비'],
    '持平': ['flat', 'stable', 'igual', '변동 없음'], '其中工资': ['salary', 'dont salaire', 'salario', '급여'],
    '支出构成': ['Spending breakdown', 'Répartition des dépenses', 'Desglose del gasto', '지출 구성'], '点击分类查看每一笔': ['Click a category to see every transaction', 'Cliquez une catégorie pour le détail', 'Pulsa una categoría para ver el detalle', '분류를 누르면 건별 내역'],
    '点分类看每一笔': ['Tap a category for details', 'Touchez une catégorie', 'Toca una categoría', '분류를 눌러 내역 보기'],
    '总支出': ['Total spending', 'Dépenses totales', 'Gasto total', '총지출'], '总收入': ['Total income', 'Revenus totaux', 'Ingresos totales', '총수입'],
    '财务健康': ['Financial health', 'Santé financière', 'Salud financiera', '재무 건강'], '财务健康评分': ['Financial health score', 'Score de santé financière', 'Puntuación financiera', '재무 건강 점수'],
    '全部建议 →': ['All advice →', 'Tous les conseils →', 'Todos los consejos →', '모든 조언 →'], '全部明细 →': ['All transactions →', 'Toutes les opérations →', 'Todos los movimientos →', '전체 내역 →'],
    '优秀': ['Excellent', 'Excellent', 'Excelente', '우수'], '良好': ['Good', 'Bon', 'Bueno', '양호'], '一般': ['Fair', 'Moyen', 'Regular', '보통'], '需改善': ['Needs work', 'À améliorer', 'Mejorable', '개선 필요'], '暂无': ['n/a', 'n/d', 's/d', '없음'],
    '数据不足，无法评分': ['Not enough data to score', 'Données insuffisantes', 'Datos insuficientes', '데이터 부족'], '满分 100': ['out of 100', 'sur 100', 'sobre 100', '100점 만점'],
    '近 12 个月收支': ['Last 12 months', '12 derniers mois', 'Últimos 12 meses', '최근 12개월'], '柱：收入 / 支出　线：结余': ['Bars: income / spending · Line: balance', 'Barres : revenus / dépenses · Ligne : solde', 'Barras: ingresos / gastos · Línea: saldo', '막대: 수입/지출 · 선: 잔액'],
    '重点提醒': ['Key alerts', 'Points clés', 'Avisos clave', '주요 알림'], '本月累计支出': ['Cumulative spending', 'Dépenses cumulées', 'Gasto acumulado', '누적 지출'],
    '对比上月同期': ['vs same point last month', 'vs même date le mois dernier', 'vs mismo punto del mes anterior', '지난달 같은 시점 대비'], '逐日累计': ['day by day', 'jour par jour', 'día a día', '일별 누적'], '虚线为上月': ['dashed: last month', 'pointillé : mois dernier', 'discontinua: mes anterior', '점선: 지난달'],
    '最大的几笔支出': ['Largest expenses', 'Plus grosses dépenses', 'Mayores gastos', '가장 큰 지출'], '本月没有支出': ['No spending this month', 'Aucune dépense ce mois-ci', 'Sin gastos este mes', '이번 달 지출 없음'],
    '本月': ['This month', 'Ce mois', 'Este mes', '이번 달'], '上月': ['Last month', 'Mois dernier', 'Mes anterior', '지난달'], '累计': [' cumulative', ' cumulé', ' acumulado', ' 누적'],
    '本月进行中': ['month in progress', 'mois en cours', 'mes en curso', '진행 중'], '导入账单后即可开始': ['Import a statement to get started', 'Importez un relevé pour commencer', 'Importa un extracto para empezar', '명세서를 가져오면 시작됩니다'],
    '不计入收支': ['Not counted', 'Non comptabilisé', 'No contabilizado', '집계 제외'], '查看': ['View', 'Voir', 'Ver', '보기'],
    '退款已冲减支出': ['refunds deducted from spending', 'remboursements déduits', 'reembolsos descontados', '환불로 지출 차감'],
    '这些记录既不是收入也不是开销，点击可逐笔核对': ['Neither income nor spending — click to review each one', 'Ni revenu ni dépense — cliquez pour vérifier', 'Ni ingreso ni gasto: pulsa para revisar', '수입도 지출도 아님 — 눌러서 건별 확인'],
    // 分析
    '各类支出对比': ['Spending by category', 'Dépenses par catégorie', 'Gasto por categoría', '분류별 지출 비교'], '支出分类表': ['Category table', 'Tableau des catégories', 'Tabla de categorías', '지출 분류표'], '支出分类': ['Spending categories', 'Catégories de dépenses', 'Categorías de gasto', '지출 분류'],
    '本月未结束，对比仅供参考': ['Month not finished — comparisons are indicative', 'Mois en cours — comparaisons indicatives', 'Mes sin terminar: comparación orientativa', '월 진행 중 — 비교는 참고용'],
    '分类': ['Category', 'Catégorie', 'Categoría', '분류'], '金额': ['Amount', 'Montant', 'Importe', '금액'], '占比': ['Share', 'Part', 'Peso', '비중'], '笔数': ['Count', 'Nb', 'N.º', '건수'],
    '环比': ['MoM', 'M/M', 'M/M', '전월비'], '较均值': ['vs avg', 'vs moy.', 'vs media', '평균비'], '收入来源': ['Income sources', 'Sources de revenus', 'Fuentes de ingresos', '수입원'],
    '分类趋势': ['Category trend', 'Tendance par catégorie', 'Tendencia por categoría', '분류 추세'], '每日支出': ['Daily spending', 'Dépenses par jour', 'Gasto diario', '일별 지출'],
    '看清钱是哪几天花出去的': ['See which days the money went out', "Voir quels jours l'argent est sorti", 'Mira qué días salió el dinero', '어느 날 돈이 나갔는지 확인'],
    '星期分布': ['By weekday', 'Par jour de semaine', 'Por día de la semana', '요일별 분포'], '本月各星期几的支出合计': ['Total spending by day of week', 'Total des dépenses par jour', 'Gasto total por día', '요일별 지출 합계'],
    '花钱最多的商户': ['Top merchants', 'Principaux commerçants', 'Principales comercios', '지출 상위 가맹점'], 'Top 10 · 点击查看明细': ['Top 10 · click for details', 'Top 10 · cliquez pour le détail', 'Top 10 · pulsa para ver detalle', '상위 10 · 눌러서 내역'],
    '商户': ['Merchant', 'Commerçant', 'Comercio', '가맹점'], '占支出': ['% of spending', '% des dépenses', '% del gasto', '지출 비중'],
    '账户分布': ['By account', 'Par compte', 'Por cuenta', '계좌별'], '各银行 / 支付渠道 · 点击查看明细': ['Banks & payment methods · click for details', 'Banques & moyens de paiement · cliquez', 'Bancos y medios de pago · pulsa', '은행·결제수단 · 눌러서 내역'],
    '账户': ['Account', 'Compte', 'Cuenta', '계좌'], '月度汇总': ['Monthly summary', 'Synthèse mensuelle', 'Resumen mensual', '월별 요약'], '历史对比': ['history', 'historique', 'histórico', '기간 비교'], '月份': ['Month', 'Mois', 'Mes', '월'],
    '本月没有支出记录': ['No spending recorded this month', 'Aucune dépense ce mois-ci', 'Sin gastos este mes', '이번 달 지출 기록 없음'], '本月没有记录': ['Nothing this month', 'Rien ce mois-ci', 'Nada este mes', '이번 달 기록 없음'], '这个月没有记录': ['Nothing recorded this month', 'Aucune donnée ce mois-ci', 'Sin datos este mes', '이번 달 기록 없음'],
    // 建议
    '按建议预算执行，下月可少花': ['Follow the suggested budget and spend less next month by', 'En suivant le budget conseillé, économisez le mois prochain', 'Con el presupuesto sugerido, el mes próximo ahorras', '권장 예산대로면 다음 달 절감액'],
    '主要来自：': ['Mainly: ', 'Surtout : ', 'Sobre todo: ', '주요: '], '当前各类开销都在合理范围内，保持即可。': ['Spending is within a reasonable range — keep it up.', 'Vos dépenses sont raisonnables : continuez ainsi.', 'Tu gasto está en un rango razonable: sigue así.', '모든 지출이 적정 범위입니다. 유지하세요.'],
    '各类开销都在合理范围内，保持即可。': ['Spending is within a reasonable range — keep it up.', 'Vos dépenses sont raisonnables : continuez ainsi.', 'Tu gasto está en un rango razonable: sigue así.', '모든 지출이 적정 범위입니다. 유지하세요.'],
    '需立即关注': ['Needs attention', 'À traiter', 'Urgente', '즉시 확인'], '建议调整': ['Adjust', 'À ajuster', 'Ajustar', '조정 권장'], '提示': ['Tip', 'Info', 'Aviso', '안내'], '保持': ['Keep it up', 'À maintenir', 'Mantener', '유지'],
    '现状': ['Now', 'Actuel', 'Actual', '현재'], '目标': ['Target', 'Objectif', 'Objetivo', '목표'],
    '下月建议预算': ['Suggested budget for next month', 'Budget conseillé le mois prochain', 'Presupuesto sugerido para el mes próximo', '다음 달 권장 예산'], '本月实际 vs 建议上限': ['Actual vs suggested cap', 'Réel / plafond conseillé', 'Real / tope sugerido', '실제 / 권장 상한'],
    '本月实际': ['Actual', 'Réel', 'Real', '실제'], '建议预算': ['Suggested', 'Conseillé', 'Sugerido', '권장'], '预算明细': ['Budget details', 'Détail du budget', 'Detalle del presupuesto', '예산 상세'], '仅基于本月': ['Based on this month only', 'Selon ce mois uniquement', 'Solo según este mes', '이번 달만 기준'],
    '可省': ['Save', 'Économie', 'Ahorro', '절감'], '必需': ['essential', 'essentiel', 'esencial', '필수'], '合计': ['Total', 'Total', 'Total', '합계'],
    '固定扣费清单': ['Recurring charges', 'Prélèvements récurrents', 'Cargos fijos', '고정 결제 목록'], '固定扣费': ['Recurring charges', 'Prélèvements', 'Cargos fijos', '고정 결제'],
    '订阅、会员与每月金额稳定的支出，逐项确认是否仍需要': ['Subscriptions and steady monthly charges — check each is still needed', 'Abonnements et prélèvements réguliers — vérifiez leur utilité', 'Suscripciones y cargos estables: revisa si aún los necesitas', '구독·정기 결제 — 아직 필요한지 항목별 확인'],
    '逐项确认是否还需要': ['check each is still needed', 'vérifiez leur utilité', 'revisa si aún los necesitas', '아직 필요한지 확인'],
    '项目': ['Item', 'Poste', 'Concepto', '항목'], '本月金额': ['This month', 'Ce mois', 'Este mes', '이번 달'], '折合每年': ['Per year', 'Par an', 'Al año', '연 환산'], '已出现': ['Seen for', 'Depuis', 'Desde hace', '반복'],
    // 明细
    '搜索描述、商户、金额…': ['Search description, merchant, amount…', 'Rechercher libellé, commerçant, montant…', 'Buscar concepto, comercio, importe…', '설명·가맹점·금액 검색…'], '搜索描述、分类、金额…': ['Search description, category, amount…', 'Rechercher libellé, catégorie, montant…', 'Buscar concepto, categoría, importe…', '설명·분류·금액 검색…'],
    '仅本月': ['This month', 'Ce mois', 'Este mes', '이번 달'], '全部': ['All', 'Tout', 'Todo', '전체'], '全部类型': ['All types', 'Tous les types', 'Todos los tipos', '모든 유형'], '全部分类': ['All categories', 'Toutes catégories', 'Todas las categorías', '모든 분류'], '全部账户': ['All accounts', 'Tous les comptes', 'Todas las cuentas', '모든 계좌'],
    '手动记一笔': ['Add manually', 'Saisie manuelle', 'Añadir a mano', '직접 입력'], '记一笔': ['Add entry', 'Nouvelle saisie', 'Nuevo apunte', '기록 추가'], '日期': ['Date', 'Date', 'Fecha', '날짜'], '描述': ['Description', 'Libellé', 'Concepto', '설명'], '类型': ['Type', 'Type', 'Tipo', '유형'],
    '编辑': ['Edit', 'Modifier', 'Editar', '수정'], '删除': ['Delete', 'Supprimer', 'Eliminar', '삭제'], '上一页': ['Previous', 'Précédent', 'Anterior', '이전'], '下一页': ['Next', 'Suivant', 'Siguiente', '다음'],
    '没有符合条件的交易': ['No matching transactions', 'Aucune opération correspondante', 'Sin movimientos coincidentes', '조건에 맞는 거래 없음'], '这个月没有符合条件的交易': ['No matching transactions this month', 'Aucune opération correspondante ce mois-ci', 'Sin movimientos coincidentes este mes', '이번 달 조건에 맞는 거래 없음'],
    '已修改，并记住了这类交易的分类': ['Updated — this category will be remembered', 'Modifié — catégorie mémorisée', 'Actualizado: se recordará la categoría', '수정됨 — 이 분류를 기억합니다'], '已修改': ['Updated', 'Modifié', 'Actualizado', '수정됨'], '已删除': ['Deleted', 'Supprimé', 'Eliminado', '삭제됨'], '已保存': ['Saved', 'Enregistré', 'Guardado', '저장됨'], '已记录': ['Recorded', 'Enregistré', 'Anotado', '기록됨'],
    '删除这笔交易？': ['Delete this transaction?', 'Supprimer cette opération ?', '¿Eliminar este movimiento?', '이 거래를 삭제할까요?'], '编辑交易': ['Edit transaction', "Modifier l'opération", 'Editar movimiento', '거래 수정'],
    '卡片 / 支付方式': ['Card / payment method', 'Carte / moyen de paiement', 'Tarjeta / medio de pago', '카드 / 결제수단'], '例如：储蓄卡尾号1234、信用卡、花呗': ['e.g. debit ••1234, credit card', 'ex. débit ••1234, carte de crédit', 'p. ej. débito ••1234, crédito', '예: 체크카드 ••1234, 신용카드'],
    '例如：房租、工资、和朋友聚餐': ['e.g. rent, salary, dinner with friends', 'ex. loyer, salaire, dîner entre amis', 'p. ej. alquiler, nómina, cena con amigos', '예: 월세, 급여, 친구와 식사'], '例如：午饭、打车、工资': ['e.g. lunch, taxi, salary', 'ex. déjeuner, taxi, salaire', 'p. ej. comida, taxi, nómina', '예: 점심, 택시, 급여'],
    '保存': ['Save', 'Enregistrer', 'Guardar', '저장'], '取消': ['Cancel', 'Annuler', 'Cancelar', '취소'], '关闭': ['Close', 'Fermer', 'Cerrar', '닫기'], '请填写日期和大于 0 的金额': ['Enter a date and an amount above 0', 'Saisissez une date et un montant > 0', 'Indica fecha e importe mayor que 0', '날짜와 0보다 큰 금액을 입력하세요'], '请输入金额': ['Enter an amount', 'Saisissez un montant', 'Indica un importe', '금액을 입력하세요'],
    '币种': ['Currency', 'Devise', 'Moneda', '통화'], '现金': ['Cash', 'Espèces', 'Efectivo', '현금'], '手机记账': ['Phone entry', 'Saisie mobile', 'Apunte móvil', '휴대폰 기록'], '手动添加': ['Added manually', 'Saisie manuelle', 'Añadido a mano', '직접 입력'], '手动': ['Manual', 'Manuel', 'Manual', '수동'],
    // 明细钻取
    '每一笔': ['Every transaction', 'Chaque opération', 'Cada movimiento', '건별 내역'], '按日期': ['By date', 'Par date', 'Por fecha', '날짜순'], '按金额': ['By amount', 'Par montant', 'Por importe', '금액순'], '商家 / 描述': ['Merchant / description', 'Commerçant / libellé', 'Comercio / concepto', '가맹점 / 설명'],
    '银行 / 账户': ['Bank / account', 'Banque / compte', 'Banco / cuenta', '은행 / 계좌'], '未识别': ['unknown', 'inconnu', 'desconocido', '미확인'], '单笔平均': ['average', 'moyenne', 'media', '건당 평균'], '在交易明细中打开': ['Open in Transactions', 'Ouvrir dans Opérations', 'Abrir en Movimientos', '거래 내역에서 열기'],
    '卡片信息来自账单里的卡号 / 支付方式；没识别到的可在“交易明细”里补上': ['Card info comes from the statement; fill in missing ones under Transactions', 'Infos carte issues du relevé ; complétez dans Opérations', 'La tarjeta sale del extracto; completa las que falten en Movimientos', '카드 정보는 명세서에서 가져옵니다. 누락분은 거래 내역에서 입력하세요'],
    '没有记录': ['No records', 'Aucune donnée', 'Sin registros', '기록 없음'], '未命名账户': ['Unnamed account', 'Compte sans nom', 'Cuenta sin nombre', '이름 없는 계좌'],
    // 导入
    '点击选择文件，或直接把文件拖进窗口': ['Click to choose files, or drop them into the window', 'Cliquez pour choisir des fichiers ou déposez-les ici', 'Pulsa para elegir archivos o suéltalos aquí', '눌러서 파일 선택 또는 창에 끌어다 놓기'],
    '支持 PDF、截图 / 照片、Excel、CSV、Word、OFX —— 可一次选多个银行的流水': ['PDF, screenshots / photos, Excel, CSV, Word, OFX — several banks at once', "PDF, captures / photos, Excel, CSV, Word, OFX — plusieurs banques à la fois", 'PDF, capturas / fotos, Excel, CSV, Word, OFX: varios bancos a la vez', 'PDF, 스크린샷/사진, Excel, CSV, Word, OFX — 여러 은행을 한 번에'],
    '导入收入凭证': ['Import income proof', 'Importer un justificatif de revenu', 'Importar justificante de ingreso', '수입 증빙 가져오기'],
    '工资条、到账截图、收入证明 PDF 等 —— 图片会自动识别金额和日期，导入前可核对修改': ['Payslips, deposit screenshots, income PDFs — amount and date are read automatically; review before importing', 'Fiches de paie, captures de virement, PDF — montant et date lus automatiquement, à vérifier avant import', 'Nóminas, capturas de abono, PDF: importe y fecha se leen solos; revisa antes de importar', '급여명세서, 입금 캡처, 소득 PDF — 금액·날짜 자동 인식, 가져오기 전 확인'],
    '导入记录': ['Import history', 'Historique des imports', 'Historial de importaciones', '가져오기 기록'], '删除某次导入会一并移除它带来的交易': ['Deleting an import also removes its transactions', 'Supprimer un import retire aussi ses opérations', 'Eliminar una importación borra sus movimientos', '가져오기를 삭제하면 해당 거래도 삭제됩니다'],
    '文件': ['File', 'Fichier', 'Archivo', '파일'], '识别方式': ['Method', 'Méthode', 'Método', '인식 방식'], '覆盖日期': ['Period', 'Période', 'Periodo', '기간'], '交易数': ['Transactions', 'Opérations', 'Movimientos', '거래 수'], '导入时间': ['Imported', 'Importé le', 'Importado', '가져온 시각'],
    '还没有导入过文件': ['Nothing imported yet', 'Aucun import pour le moment', 'Aún no has importado nada', '아직 가져온 파일 없음'], '删除这次导入': ['Delete this import', 'Supprimer cet import', 'Eliminar esta importación', '이 가져오기 삭제'], '删除这次导入？': ['Delete this import?', 'Supprimer cet import ?', '¿Eliminar esta importación?', '이 가져오기를 삭제할까요?'],
    '这次导入带来的所有交易都会被移除。': ['All transactions from this import will be removed.', 'Toutes ses opérations seront supprimées.', 'Se eliminarán todos sus movimientos.', '이 가져오기의 모든 거래가 삭제됩니다.'],
    '数据管理': ['Data', 'Données', 'Datos', '데이터 관리'], '所有数据只保存在这台电脑上，不会上传': ['Everything stays on this computer; nothing is uploaded', 'Tout reste sur cet ordinateur ; rien n\'est envoyé', 'Todo queda en este equipo; no se sube nada', '모든 데이터는 이 컴퓨터에만 저장되며 업로드되지 않습니다'],
    '导出 Excel 报告': ['Export Excel report', 'Exporter en Excel', 'Exportar a Excel', 'Excel 보고서 내보내기'], '载入示例数据': ['Load sample data', 'Charger des données de démonstration', 'Cargar datos de ejemplo', '샘플 데이터 불러오기'], '清空全部数据': ['Erase all data', 'Tout effacer', 'Borrar todo', '모든 데이터 지우기'],
    '清空全部数据？': ['Erase all data?', 'Tout effacer ?', '¿Borrar todo?', '모든 데이터를 지울까요?'], '所有交易和导入记录都会被删除，且无法恢复。': ['All transactions and import history will be deleted permanently.', 'Toutes les opérations et imports seront supprimés définitivement.', 'Se borrarán todos los movimientos e importaciones sin vuelta atrás.', '모든 거래와 가져오기 기록이 영구 삭제됩니다.'], '清空': ['Erase', 'Effacer', 'Borrar', '지우기'], '已清空': ['Erased', 'Effacé', 'Borrado', '삭제 완료'],
    '还没有数据可导出': ['Nothing to export yet', 'Rien à exporter', 'Nada que exportar', '내보낼 데이터 없음'], '已导出：': ['Exported: ', 'Exporté : ', 'Exportado: ', '내보냄: '], '已载入 6 个月的示例数据': ['Loaded 6 months of sample data', '6 mois de données de démonstration chargés', 'Cargados 6 meses de ejemplo', '샘플 데이터 6개월 불러옴'],
    '每次导入新账单，程序都会拿它和之前导入的所有账单核对，对上的两笔会互相标注“↔ 对方账户”；同一条转账路线对上过两次后，以后即使另一头的账单还没导入也会直接识别。': ['Every new statement is checked against everything imported before; matched records are tagged “↔ other account”. Once the same transfer route has matched twice, it is recognised even before the other side is imported.', 'Chaque nouveau relevé est comparé à tous les relevés déjà importés ; les deux écritures rapprochées portent la mention « ↔ autre compte ». Après deux rapprochements du même trajet, il est reconnu même si l’autre relevé n’est pas encore importé.', 'Cada extracto nuevo se compara con todo lo importado antes; los dos apuntes casados se marcan con «↔ otra cuenta». Cuando una misma ruta ha casado dos veces, se reconoce aunque aún no esté importado el otro extracto.', '새 명세서를 가져올 때마다 이전에 가져온 모든 명세서와 대조하며, 맞는 두 건에는 “↔ 상대 계좌”가 표시됩니다. 같은 이체 경로가 두 번 매칭되면 이후에는 반대편 명세서가 없어도 바로 인식합니다.'],
    '内部转账识别': ['Internal transfer detection', 'Détection des virements internes', 'Detección de transferencias internas', '내부 이체 인식'], '信用卡还款、自己账户之间互转不算收入也不算开销': ['Card payments and moves between your own accounts are neither income nor spending', 'Paiements de carte et virements entre vos comptes : ni revenu ni dépense', 'Pagos de tarjeta y traspasos entre tus cuentas: ni ingreso ni gasto', '카드 대금 납부와 본인 계좌 간 이체는 수입도 지출도 아닙니다'],
    '程序会自动识别三类记录并标为“内部转账”：① 账单里的还款 / 转账字样（如 Payment Thank You、Payment from CHK、Ext Trnsfr、信用卡还款）；② 对方是你本人的转账（如 Zelle payment to 你的名字）；③ 两个账户之间金额相同、日期相近的一出一进。你手动改过类型的交易不会被再次改动。': ['Three kinds of records are marked as internal automatically: ① payment / transfer wording on the statement (Payment Thank You, Payment from CHK, Ext Trnsfr…); ② transfers where the other party is you (Zelle payment to your name); ③ an outflow and an inflow of the same amount between two accounts within a few days. Types you changed by hand are never touched again.', 'Trois cas sont marqués automatiquement comme internes : ① libellés de paiement / virement (Payment Thank You, Ext Trnsfr…) ; ② virements dont le bénéficiaire est vous ; ③ une sortie et une entrée du même montant entre deux comptes à quelques jours. Les types modifiés à la main ne sont plus touchés.', 'Se marcan como internos tres casos: ① textos de pago / traspaso (Payment Thank You, Ext Trnsfr…); ② transferencias en las que la otra parte eres tú; ③ una salida y una entrada del mismo importe entre dos cuentas en pocos días. Lo que cambies a mano no se vuelve a tocar.', '세 가지 기록을 자동으로 내부 이체로 표시합니다: ① 명세서의 납부/이체 문구(Payment Thank You, Ext Trnsfr 등) ② 상대가 본인인 이체 ③ 두 계좌 사이 같은 금액·비슷한 날짜의 출금과 입금. 직접 바꾼 유형은 다시 변경하지 않습니다.'],
    '你在银行账单上的姓名，多个用逗号分隔，例如：Zhang San, 张三': ['Your name as it appears on statements, comma-separated', 'Votre nom tel qu\'il figure sur les relevés, séparé par des virgules', 'Tu nombre tal como aparece en los extractos, separado por comas', '명세서에 표시되는 본인 이름(쉼표로 구분)'],
    '保存并重新识别': ['Save and re-scan', 'Enregistrer et réanalyser', 'Guardar y volver a analizar', '저장 후 다시 인식'], '已保存，没有发现新的内部转账': ['Saved — no new internal transfers found', 'Enregistré — aucun nouveau virement interne', 'Guardado: no hay nuevas transferencias internas', '저장됨 — 새 내부 이체 없음'],
    '确认导入内容': ['Review before importing', "Vérifier avant d'importer", 'Revisar antes de importar', '가져오기 전 확인'], '核对识别结果，可直接修改；灰色的重复记录默认不导入': ['Check the results and edit if needed; greyed-out duplicates are skipped by default', 'Vérifiez et corrigez si besoin ; les doublons grisés sont ignorés', 'Revisa y corrige si hace falta; los duplicados en gris se omiten', '인식 결과를 확인·수정하세요. 회색 중복 기록은 기본적으로 제외됩니다'],
    '正在识别…截图和扫描件需要几秒钟': ['Reading… screenshots and scans take a few seconds', 'Lecture… captures et scans prennent quelques secondes', 'Leyendo… capturas y escaneos tardan unos segundos', '인식 중… 스크린샷·스캔은 몇 초 걸립니다'], '正在识别…': ['Reading…', 'Lecture…', 'Leyendo…', '인식 중…'],
    '自动判断': ['Auto', 'Auto', 'Auto', '자동'], '银行流水': ['Bank statement', 'Relevé bancaire', 'Extracto bancario', '은행 명세서'], '收入凭证': ['Income proof', 'Justificatif de revenu', 'Justificante de ingreso', '수입 증빙'], '文件类型': ['File type', 'Type de fichier', 'Tipo de archivo', '파일 유형'],
    '账户名称': ['Account name', 'Nom du compte', 'Nombre de la cuenta', '계좌 이름'], '卡片 / 卡号后四位': ['Card / last four digits', 'Carte / 4 derniers chiffres', 'Tarjeta / últimos 4 dígitos', '카드 / 끝 4자리'], '卡片（如尾号1234）': ['Card (e.g. ••1234)', 'Carte (ex. ••1234)', 'Tarjeta (p. ej. ••1234)', '카드(예: ••1234)'],
    '补一行': ['Add a row', 'Ajouter une ligne', 'Añadir fila', '행 추가'], '这份 PDF 有密码保护': ['This PDF is password-protected', 'Ce PDF est protégé par mot de passe', 'Este PDF tiene contraseña', '암호로 보호된 PDF입니다'], '输入 PDF 密码': ['PDF password', 'Mot de passe du PDF', 'Contraseña del PDF', 'PDF 암호'], '解锁': ['Unlock', 'Déverrouiller', 'Desbloquear', '잠금 해제'], '未能读取': ['Could not read', 'Lecture impossible', 'No se pudo leer', '읽을 수 없음'],
    '松开即可导入': ['Drop to import', 'Déposez pour importer', 'Suelta para importar', '놓으면 가져옵니다'], 'PDF · 截图 · Excel · CSV · Word': ['PDF · screenshots · Excel · CSV · Word', 'PDF · captures · Excel · CSV · Word', 'PDF · capturas · Excel · CSV · Word', 'PDF · 스크린샷 · Excel · CSV · Word'],
    'PDF 文本解析': ['PDF text', 'Texte PDF', 'Texto PDF', 'PDF 텍스트'], 'PDF 扫描件识别': ['Scanned PDF (OCR)', 'PDF scanné (OCR)', 'PDF escaneado (OCR)', '스캔 PDF(OCR)'], '截图文字识别': ['Screenshot OCR', "OCR de capture d'écran", 'OCR de captura', '스크린샷 OCR'], 'CSV / 文本': ['CSV / text', 'CSV / texte', 'CSV / texto', 'CSV / 텍스트'], 'Excel 表格': ['Excel sheet', 'Feuille Excel', 'Hoja Excel', 'Excel 시트'], 'Word 文档': ['Word document', 'Document Word', 'Documento Word', 'Word 문서'], '网页表格': ['HTML table', 'Tableau HTML', 'Tabla HTML', 'HTML 표'], 'OFX 账务文件': ['OFX file', 'Fichier OFX', 'Archivo OFX', 'OFX 파일'], '内置示例': ['Built-in sample', 'Exemple intégré', 'Ejemplo incluido', '내장 샘플'], '示例数据': ['Sample data', 'Données de démonstration', 'Datos de ejemplo', '샘플 데이터'], '多个账户': ['Several accounts', 'Plusieurs comptes', 'Varias cuentas', '여러 계좌'],
    '来自图片识别，个别数字可能有误，请在确认前核对。': ['Read from an image — a digit may be wrong; please check before confirming.', "Lu depuis une image : un chiffre peut être erroné, vérifiez avant de confirmer.", 'Leído de una imagen: puede haber algún dígito mal; revisa antes de confirmar.', '이미지에서 인식한 결과입니다. 숫자가 틀릴 수 있으니 확인하세요.'],
    '没有识别出交易记录。可以在下方手动添加，或换一种导出格式再试。': ['No transactions found. Add rows below, or try another export format.', "Aucune opération trouvée. Ajoutez des lignes ou essayez un autre format d'export.", 'No se encontraron movimientos. Añade filas o prueba otro formato.', '거래를 찾지 못했습니다. 아래에서 직접 추가하거나 다른 형식으로 내보내 보세요.'],
    '没有读到任何文字，文件可能是空白或损坏的。': ['No text could be read; the file may be blank or damaged.', 'Aucun texte lisible ; le fichier est peut-être vide ou endommagé.', 'No se pudo leer texto; el archivo puede estar vacío o dañado.', '텍스트를 읽지 못했습니다. 파일이 비었거나 손상되었을 수 있습니다.'],
    '未找到明确的“实发/到账”字样，已取凭证中最大的金额，请核对。': ['No clear “net pay / deposited” label found; the largest amount was used — please check.', 'Pas de mention « net à payer » trouvée ; le plus gros montant a été retenu, à vérifier.', 'No se encontró «neto / abonado»; se tomó el importe mayor: revísalo.', '‘실수령/입금’ 표시를 찾지 못해 가장 큰 금액을 사용했습니다. 확인하세요.'],
    '找不到这个文件': ['File not found', 'Fichier introuvable', 'Archivo no encontrado', '파일을 찾을 수 없음'], '无法解析：': ['Could not parse: ', 'Analyse impossible : ', 'No se pudo analizar: ', '분석 실패: '], '暂不支持这种文件格式': ['This file format is not supported yet', "Ce format n'est pas encore pris en charge", 'Este formato aún no es compatible', '아직 지원하지 않는 형식입니다'],
    // 欢迎页
    '把流水丢进来，看清钱去了哪': ['Drop in your statements and see where the money went', "Déposez vos relevés et voyez où va l'argent", 'Suelta tus extractos y mira adónde va el dinero', '명세서를 넣고 돈의 흐름을 확인하세요'],
    '导入各家银行、微信、支付宝的账单和工资凭证，自动汇总成一份清晰的月度收支报告。': ['Import statements from any bank or wallet plus your payslips, and get one clear monthly report.', 'Importez les relevés de vos banques et vos fiches de paie pour obtenir un rapport mensuel clair.', 'Importa extractos de tus bancos y tus nóminas y obtén un informe mensual claro.', '여러 은행·간편결제 명세서와 급여 증빙을 가져오면 월별 보고서로 정리합니다.'],
    '先用示例数据看看效果': ['Try it with sample data', 'Essayer avec des données de démonstration', 'Probar con datos de ejemplo', '샘플 데이터로 체험'],
    '多格式识别': ['Reads many formats', 'Nombreux formats', 'Muchos formatos', '다양한 형식'], 'PDF 对账单、手机截图、Excel / CSV 都能读，截图走离线文字识别。': ['PDF statements, phone screenshots, Excel / CSV — screenshots use offline OCR.', "Relevés PDF, captures d'écran, Excel / CSV — OCR hors ligne pour les images.", 'Extractos PDF, capturas, Excel / CSV: OCR sin conexión para imágenes.', 'PDF 명세서, 스크린샷, Excel/CSV 지원 — 이미지는 오프라인 OCR.'],
    '全面分析': ['Full analysis', 'Analyse complète', 'Análisis completo', '종합 분석'], '分类占比、月度趋势、环比变化、商户与账户分布一目了然。': ['Category shares, monthly trends, month-over-month changes, merchants and accounts at a glance.', "Parts par catégorie, tendances, évolutions, commerçants et comptes d'un coup d'œil.", 'Categorías, tendencias, variaciones, comercios y cuentas de un vistazo.', '분류 비중, 월별 추세, 전월 대비, 가맹점·계좌 분포를 한눈에.'],
    '可执行建议': ['Actionable advice', 'Conseils concrets', 'Consejos prácticos', '실행 가능한 조언'], '给出每一类的建议预算和具体做法，而不是空话。': ['A suggested budget and concrete steps for each category — not platitudes.', 'Un budget conseillé et des actions concrètes par catégorie.', 'Presupuesto sugerido y pasos concretos por categoría.', '분류별 권장 예산과 구체적 방법을 제시합니다.'],
    // 手机同步（电脑端）
    '在手机上查看分析、随手记账，回到同一 Wi-Fi 自动同步': ['View the analysis and add entries on your phone; it syncs when back on the same Wi-Fi', 'Consultez et saisissez sur votre téléphone ; synchro au retour sur le même Wi-Fi', 'Consulta y anota en el móvil; se sincroniza al volver a la misma Wi-Fi', '휴대폰에서 분석 확인·기록, 같은 Wi-Fi에서 자동 동기화'],
    '同步未开启': ['Sync is off', 'Synchro désactivée', 'Sincronización desactivada', '동기화 꺼짐'], '开启后才能扫码': ['Turn it on to scan', 'Activez-la pour scanner', 'Actívala para escanear', '켜야 스캔할 수 있습니다'], '开启手机同步': ['Turn on phone sync', 'Activer la synchro mobile', 'Activar sincronización', '휴대폰 동기화 켜기'], '关闭手机同步': ['Turn off phone sync', 'Désactiver la synchro mobile', 'Desactivar sincronización', '휴대폰 동기화 끄기'],
    '手机与这台电脑连同一个 Wi-Fi，用相机扫一扫': ['Put your phone on the same Wi-Fi and scan with the camera', 'Mettez le téléphone sur le même Wi-Fi et scannez', 'Conecta el móvil a la misma Wi-Fi y escanea', '휴대폰을 같은 Wi-Fi에 연결하고 카메라로 스캔'], '关闭时，局域网内的任何设备都无法访问你的数据': ['While off, no device on the network can reach your data', 'Désactivée, aucun appareil du réseau ne peut accéder à vos données', 'Desactivada, ningún dispositivo de la red accede a tus datos', '꺼져 있으면 네트워크의 어떤 기기도 접근할 수 없습니다'],
    '连接信息': ['Connection', 'Connexion', 'Conexión', '연결 정보'], '同步服务运行中': ['Sync is running', 'Synchro active', 'Sincronización activa', '동기화 실행 중'], '未开启': ['Off', 'Désactivé', 'Desactivado', '꺼짐'], '电脑地址': ['Computer address', "Adresse de l'ordinateur", 'Dirección del equipo', '컴퓨터 주소'], '配对码': ['Pairing code', "Code d'appairage", 'Código de emparejamiento', '페어링 코드'], '更换': ['Change', 'Changer', 'Cambiar', '변경'], '这台电脑': ['This computer', 'Cet ordinateur', 'Este equipo', '이 컴퓨터'],
    '更换配对码？': ['Change the pairing code?', "Changer le code d'appairage ?", '¿Cambiar el código?', '페어링 코드를 변경할까요?'], '已配对的手机需要用新的配对码重新连接。': ['Paired phones must reconnect with the new code.', 'Les téléphones appairés devront se reconnecter.', 'Los móviles emparejados tendrán que reconectarse.', '페어링된 휴대폰은 새 코드로 다시 연결해야 합니다.'],
    '三种用法': ['Three ways to use it', "Trois façons de l'utiliser", 'Tres formas de usarlo', '세 가지 사용법'], '扫码即用（任何手机）': ['Scan and go (any phone)', 'Scannez et utilisez (tout téléphone)', 'Escanea y listo (cualquier móvil)', '스캔 즉시 사용(모든 휴대폰)'],
    '相机扫左侧二维码，在浏览器里直接打开手机版，可“添加到主屏幕”。': ['Scan the QR code to open the mobile version in the browser; you can add it to the home screen.', "Scannez le QR code pour ouvrir la version mobile ; ajoutez-la à l'écran d'accueil.", 'Escanea el QR para abrir la versión móvil; puedes añadirla a la pantalla de inicio.', 'QR을 스캔해 브라우저에서 모바일 버전을 열고 홈 화면에 추가할 수 있습니다.'],
    '安卓 App': ['Android app', 'App Android', 'App Android', '안드로이드 앱'], '手机记账': ['Phone entry', 'Saisie mobile', 'Apunte móvil', '휴대폰 기록'],
    '下载 APK 安装；扫码后点“在 App 中打开”，或在 App 里手动填上面的地址和配对码。App 会保存上次同步的数据，离开电脑也能看。': [' — download the APK; after scanning tap “Open in app”, or type the address and code into the app. The app keeps the last synced data for offline viewing.', " — téléchargez l'APK ; après le scan, touchez « Ouvrir dans l'app » ou saisissez l'adresse et le code. L'app garde les dernières données hors ligne.", ' — descarga el APK; tras escanear pulsa «Abrir en la app» o escribe la dirección y el código. La app guarda los últimos datos sin conexión.', ' — APK를 내려받아 설치하고, 스캔 후 ‘앱에서 열기’를 누르거나 주소와 코드를 직접 입력하세요. 앱은 마지막 동기화 데이터를 저장합니다.'],
    '在手机上记的每一笔，下次连上同一 Wi-Fi 时自动传回电脑并计入分析。': ['Entries made on the phone are sent back to the computer next time you are on the same Wi-Fi.', "Les saisies du téléphone reviennent à l'ordinateur au prochain passage sur le même Wi-Fi.", 'Lo que anotes en el móvil vuelve al equipo cuando estés en la misma Wi-Fi.', '휴대폰에서 기록한 내용은 같은 Wi-Fi에 연결되면 컴퓨터로 전송됩니다.'],
    '首次开启时 Windows 防火墙可能弹窗询问，请勾选“专用网络”并允许。配对码相当于密码，不要发给别人；怀疑泄露就点“更换”。': ['The first time, Windows Firewall may ask — allow “Private networks”. The pairing code is a password: do not share it, and change it if in doubt.', 'La première fois, le pare-feu Windows peut demander : autorisez « Réseaux privés ». Le code est un mot de passe : ne le partagez pas.', 'La primera vez, el cortafuegos de Windows puede preguntar: permite «Redes privadas». El código es una contraseña: no lo compartas.', '처음 켤 때 Windows 방화벽이 물으면 ‘개인 네트워크’를 허용하세요. 페어링 코드는 비밀번호이므로 공유하지 마세요.'],
    '已关闭手机同步': ['Phone sync turned off', 'Synchro mobile désactivée', 'Sincronización desactivada', '휴대폰 동기화를 껐습니다'], '已开启，可以扫码了': ['On — ready to scan', 'Activée — prêt à scanner', 'Activada: lista para escanear', '켜짐 — 스캔할 수 있습니다'], '端口被占用，无法开启同步服务': ['Port in use — cannot start sync', 'Port occupé : synchro impossible', 'Puerto en uso: no se puede iniciar', '포트 사용 중 — 동기화를 시작할 수 없음'],
    // 手机端
    '连接你的电脑': ['Connect your computer', 'Connectez votre ordinateur', 'Conecta tu equipo', '컴퓨터에 연결'], '在电脑端打开“手机同步”，把收支分析带到手机上。': ['Open “Phone sync” on the computer to bring your analysis to the phone.', "Ouvrez « Synchro mobile » sur l'ordinateur pour retrouver l'analyse ici.", 'Abre «Sincronizar móvil» en el equipo para ver aquí tu análisis.', '컴퓨터에서 ‘휴대폰 동기화’를 열어 분석을 휴대폰으로 가져오세요.'],
    '连接状态': ['Connection status', 'État de la connexion', 'Estado de conexión', '연결 상태'], '已连接': ['Connected', 'Connecté', 'Conectado', '연결됨'], '未连接': ['Not connected', 'Non connecté', 'Sin conexión', '연결 안 됨'], '电脑': ['Computer', 'Ordinateur', 'Equipo', '컴퓨터'], '上次同步': ['Last sync', 'Dernière synchro', 'Última sincronización', '마지막 동기화'], '从未': ['never', 'jamais', 'nunca', '없음'],
    '待同步的记账': ['Entries waiting to sync', 'Saisies en attente', 'Apuntes pendientes', '동기화 대기 기록'], '立即同步': ['Sync now', 'Synchroniser', 'Sincronizar ahora', '지금 동기화'], '电脑地址与配对码': ['Computer address & pairing code', 'Adresse et code', 'Dirección y código', '컴퓨터 주소와 페어링 코드'],
    '例如 192.168.1.8:8756': ['e.g. 192.168.1.8:8756', 'ex. 192.168.1.8:8756', 'p. ej. 192.168.1.8:8756', '예: 192.168.1.8:8756'], '电脑端“手机同步”页上的 8 位码': ['8-character code shown on the computer', "Code à 8 caractères affiché sur l'ordinateur", 'Código de 8 caracteres del equipo', '컴퓨터에 표시된 8자리 코드'], '保存并连接': ['Save and connect', 'Enregistrer et connecter', 'Guardar y conectar', '저장 후 연결'],
    '在 App 中打开': ['Open in app', "Ouvrir dans l'app", 'Abrir en la app', '앱에서 열기'], '装了 App 的话，点下面的按钮把这台电脑的配对信息带进 App。App 会保存数据，离开电脑也能查看。': ['If the app is installed, tap below to pass this pairing to it. The app keeps the data for offline viewing.', "Si l'app est installée, touchez ci-dessous pour lui transmettre l'appairage. Elle garde les données hors ligne.", 'Si tienes la app, pulsa abajo para pasarle el emparejamiento. Guarda los datos sin conexión.', '앱이 설치되어 있으면 아래 버튼으로 페어링 정보를 전달하세요. 앱은 데이터를 저장합니다.'],
    '怎么连？': ['How do I connect?', 'Comment se connecter ?', '¿Cómo me conecto?', '어떻게 연결하나요?'], '电脑上打开“流水分析助手 → 手机同步 → 开启”，手机和电脑连同一个 Wi-Fi，': ['On the computer open Ledger Lens → Phone sync → turn on, with phone and computer on the same Wi-Fi, then ', "Sur l'ordinateur : Ledger Lens → Synchro mobile → activer, même Wi-Fi, puis ", 'En el equipo: Ledger Lens → Sincronizar móvil → activar, misma Wi-Fi, y ', '컴퓨터에서 Ledger Lens → 휴대폰 동기화 → 켜기, 같은 Wi-Fi에서 '],
    '填入页面上显示的地址和配对码。': ['enter the address and code shown there.', "saisissez l'adresse et le code affichés.", 'escribe la dirección y el código que aparecen.', '표시된 주소와 코드를 입력하세요.'], '用相机扫二维码即可。': ['scan the QR code with the camera.', "scannez le QR code avec l'appareil photo.", 'escanea el QR con la cámara.', '카메라로 QR을 스캔하세요.'],
    '离开电脑还能用吗？': ['Does it work away from the computer?', "Fonctionne-t-il loin de l'ordinateur ?", '¿Funciona lejos del equipo?', '컴퓨터 없이도 쓸 수 있나요?'], '能。App 显示上次同步的数据；在外面记的账会先存在手机里，回到同一 Wi-Fi 后自动传回电脑。': ['Yes. The app shows the last synced data; entries you add are stored on the phone and sent back on the same Wi-Fi.', "Oui. L'app affiche les dernières données ; vos saisies sont gardées puis renvoyées sur le même Wi-Fi.", 'Sí. La app muestra los últimos datos; tus apuntes se guardan y se envían en la misma Wi-Fi.', '네. 앱은 마지막 동기화 데이터를 보여 주고, 밖에서 기록한 내용은 같은 Wi-Fi에서 전송됩니다.'],
    '浏览器版需要连着电脑才能打开；想离线查看请安装安卓 App。': ['The browser version needs the computer; install the Android app for offline viewing.', "La version navigateur nécessite l'ordinateur ; installez l'app Android pour le hors-ligne.", 'La versión web necesita el equipo; instala la app Android para verlo sin conexión.', '브라우저 버전은 컴퓨터 연결이 필요합니다. 오프라인은 안드로이드 앱을 설치하세요.'],
    '数据安全': ['Data safety', 'Sécurité des données', 'Seguridad de los datos', '데이터 보안'], '数据只在你的手机和电脑之间通过家里的局域网传输，不经过任何服务器。': ['Data travels only between your phone and computer over your home network — no servers involved.', 'Les données circulent uniquement entre téléphone et ordinateur sur votre réseau local, sans serveur.', 'Los datos viajan solo entre tu móvil y tu equipo por la red local, sin servidores.', '데이터는 가정 내 네트워크로 휴대폰과 컴퓨터 사이에서만 전송되며 서버를 거치지 않습니다.'],
    '尚未连接电脑': ['Not connected to a computer yet', "Pas encore connecté à l'ordinateur", 'Aún sin conectar al equipo', '아직 컴퓨터에 연결되지 않음'], '正在同步…': ['Syncing…', 'Synchronisation…', 'Sincronizando…', '동기화 중…'], '已同步': ['Synced', 'Synchronisé', 'Sincronizado', '동기화됨'], '同步完成': ['Sync complete', 'Synchro terminée', 'Sincronización completa', '동기화 완료'], '已配对，正在同步': ['Paired — syncing', 'Appairé — synchronisation', 'Emparejado: sincronizando', '페어링됨 — 동기화 중'],
    '连不上电脑：确认同一 Wi-Fi，且电脑端已开启手机同步': ['Cannot reach the computer: same Wi-Fi? Is phone sync turned on?', "Ordinateur injoignable : même Wi-Fi ? Synchro activée ?", 'No se llega al equipo: ¿misma Wi-Fi? ¿sincronización activada?', '컴퓨터에 연결할 수 없음: 같은 Wi-Fi인지, 동기화가 켜져 있는지 확인'], '连不上电脑': ['Cannot reach the computer', 'Ordinateur injoignable', 'No se llega al equipo', '컴퓨터에 연결할 수 없음'],
    '请填写地址和配对码': ['Enter the address and pairing code', "Saisissez l'adresse et le code", 'Indica dirección y código', '주소와 페어링 코드를 입력하세요'], '请求失败': ['Request failed', 'Échec de la requête', 'Error en la solicitud', '요청 실패'], '配对码不正确': ['Wrong pairing code', "Code d'appairage incorrect", 'Código incorrecto', '페어링 코드가 올바르지 않습니다'], '尝试次数过多，请 5 分钟后再试': ['Too many attempts — try again in 5 minutes', 'Trop de tentatives — réessayez dans 5 minutes', 'Demasiados intentos: prueba en 5 minutos', '시도 횟수 초과 — 5분 후 다시 시도'],
    '待同步（点按可撤销）': ['pending (tap to undo)', 'en attente (touchez pour annuler)', 'pendiente (toca para deshacer)', '대기 중(눌러서 취소)'], '撤销这笔还没同步的记账？': ['Undo this unsynced entry?', 'Annuler cette saisie non synchronisée ?', '¿Deshacer este apunte sin sincronizar?', '동기화 전 기록을 취소할까요?'],
    '电脑端还没有数据，先在电脑上导入账单，或点右下角 + 记一笔': ['No data on the computer yet — import a statement there, or tap + to add an entry', "Aucune donnée sur l'ordinateur — importez un relevé ou touchez +", 'Sin datos en el equipo: importa un extracto o toca +', '컴퓨터에 데이터가 없습니다. 명세서를 가져오거나 +를 눌러 기록하세요'],
  };

  const HAN = /[一-鿿]/;
  let phrases = [];
  function build() {
    phrases = Object.keys(DICT).filter(k => k.length >= 2).sort((a, b) => b.length - a.length);
  }
  function tr(s) {
    if (lang === 'zh' || typeof s !== 'string' || !HAN.test(s)) return s;
    const c = COL[lang], key = s.trim();
    if (DICT[key]) { const out = s.replace(key, DICT[key][c]); rev.set(out.trim(), key); return out; }
    let out = s;
    for (const [rx, to] of SUBS) out = out.replace(rx, typeof to === 'function' ? (...m) => to(m) : to[c]);
    if (HAN.test(out)) for (const p of phrases) if (out.includes(p)) out = out.split(p).join(DICT[p][c]);
    out = out.replace(/，/g, ', ').replace(/。/g, '. ').replace(/：/g, ': ').replace(/；/g, '; ').replace(/、/g, ', ').replace(/（/g, ' (').replace(/）/g, ') ').replace(/[“”]/g, '"').replace(/　/g, '  ').replace(/＝/g, '=');
    rev.set(out.trim(), key);
    return out;
  }
  const SKIP = '[data-raw], .desc, script, style, textarea, .code';
  function walk(root) {
    if (lang === 'zh' || !root) return;
    if (root.nodeType === 3) { if (!root.parentElement || !root.parentElement.closest(SKIP)) { const v = tr(root.nodeValue); if (v !== root.nodeValue) root.nodeValue = v; } return; }
    if (root.nodeType !== 1 || root.closest(SKIP)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = []; while (w.nextNode()) nodes.push(w.currentNode);
    for (const n of nodes) { if (!HAN.test(n.nodeValue) || n.parentElement.closest(SKIP)) continue; const v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; }
    const els = root.querySelectorAll ? [root, ...root.querySelectorAll('[placeholder],[title]')] : [];
    for (const e of els) for (const a of ['placeholder', 'title']) { const v = e.getAttribute && e.getAttribute(a); if (v && HAN.test(v) && !e.closest('.desc,[data-raw]')) e.setAttribute(a, tr(v)); }
  }
  function deep(o) { // 翻译图表配置里的字符串（系列名、坐标轴类目）
    if (lang === 'zh') return o;
    if (typeof o === 'string') return tr(o);
    if (Array.isArray(o)) return o.map(deep);
    if (o && typeof o === 'object' && o.constructor === Object) { const r = {}; for (const k in o) r[k] = typeof o[k] === 'function' ? o[k] : deep(o[k]); return r; }
    return o;
  }
  let observer;
  function start() {
    if (observer) return;
    observer = new MutationObserver(list => {
      for (const m of list) {
        if (m.type === 'characterData') walk(m.target);
        else m.addedNodes.forEach(walk);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  function set(l) {
    lang = COL[l] !== undefined || l === 'zh' ? l : 'zh';
    document.documentElement.lang = LOCALE[lang];
    build(); start(); rev.clear();
  }
  window.I18N = {
    LANGS, set, t: tr, deep, month, weekday, walk,
    get lang() { return lang; },
    zh: s => rev.get(String(s).trim()) || s,       // 译文 → 中文键（图表点击时用）
    big: v => lang === 'zh' || lang === 'ko' ? (Math.abs(v) >= 10000 ? (v / 10000) + (lang === 'ko' ? '만' : '万') : Math.abs(v) >= 1000 ? (v / 1000) + 'k' : v)
      : (Math.abs(v) >= 1e6 ? (v / 1e6) + 'M' : Math.abs(v) >= 1000 ? (v / 1000) + 'k' : v),
  };
  build();
})();
