/* 流水分析助手 —— 前端逻辑 */
'use strict';
const DEV = new URLSearchParams(location.search).has('dev');
const api = new Proxy({}, {
  get: (_, name) => (...args) => DEV
    ? fetch('/api/' + name, { method: 'POST', body: JSON.stringify(args) }).then(r => r.json())
    : window.pywebview.api[name](...args),
});

const S = { boot: null, currency: null, month: null, a: null, txns: null, page: 'overview', charts: {}, filter: { q: '', kind: '', cat: '', acc: '', scope: 'month', page: 0 } };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icon = (n, cls = '') => `<svg class="${cls}"><use href="#i-${n}"/></svg>`;
const sym = () => (S.a && S.a.symbol) || (S.boot.currencies.find(c => c.code === S.currency) || {}).symbol || '¥';
const num = (v, d = 2) => Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const money = (v, d = 2) => (v < 0 ? '−' : '') + sym() + num(Math.abs(v), d);
const monthLabel = m => `${m.slice(0, 4)}年${+m.slice(5)}月`;
const KIND = { income: '收入', expense: '支出', transfer: '内部转账' };
const LEVEL = { alert: ['需立即关注', 'alert'], warn: ['建议调整', 'alert'], info: ['提示', 'info'], good: ['保持', 'check'] };
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('on');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('on'), 2600);
}

/* ───────── 图表基础 ───────── */
const FIXED = { '交通出行': 1, '餐饮美食': 2, '超市日用': 3, '通讯订阅': 4, '购物消费': 5, '医疗健康': 6, '住房物业': 7, '娱乐休闲': 8,
  '工资薪酬': 1, '奖金补贴': 4, '投资理财': 3, '退款报销': 7, '转账收入': 2, '其他收入': 5 };
function colorMap(names) { // 颜色跟随类别本身；冲突时取尚未使用的色位
  const used = new Set(), out = {};
  names.forEach(n => { const s = FIXED[n]; if (s && !used.has(s)) { out[n] = s; used.add(s); } });
  names.forEach(n => { if (out[n]) return; for (let i = 1; i <= 8; i++) if (!used.has(i)) { out[n] = i; used.add(i); break; } });
  const m = {}; names.forEach(n => m[n] = n === '其他' || !out[n] ? css('--s-other') : css('--s' + out[n])); return m;
}
function chart(id, option) {
  const el = document.getElementById(id); if (!el) return;
  if (S.charts[id]) S.charts[id].dispose();
  const c = echarts.init(el, null, { renderer: 'svg' });
  const ink2 = css('--ink-2'), ink3 = css('--ink-3');
  const base = {
    animationDuration: 600, textStyle: { fontFamily: 'Segoe UI Variable Text, Segoe UI, Microsoft YaHei UI, sans-serif', color: ink2 },
    grid: { left: 8, right: 14, top: 34, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(128,128,128,.08)' } }, backgroundColor: css('--surface'), borderColor: css('--line-2'), borderWidth: 1, padding: [10, 14], textStyle: { color: css('--ink'), fontSize: 13 }, extraCssText: 'border-radius:12px;box-shadow:0 12px 32px -12px rgba(0,0,0,.3);', valueFormatter: v => v == null ? '—' : money(v) },
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, itemGap: 16, textStyle: { color: ink2, fontSize: 12.5 } },
  };
  c.setOption(Object.assign(base, option));
  S.charts[id] = c; return c;
}
const axisCat = (data, extra = {}) => Object.assign({ type: 'category', data, axisLine: { lineStyle: { color: css('--axis') } }, axisTick: { show: false }, axisLabel: { color: css('--ink-3'), fontSize: 12 } }, extra);
const axisVal = (extra = {}) => Object.assign({ type: 'value', splitLine: { lineStyle: { color: css('--grid') } }, axisLabel: { color: css('--ink-3'), fontSize: 12, formatter: v => Math.abs(v) >= 10000 ? (v / 10000) + '万' : Math.abs(v) >= 1000 ? (v / 1000) + 'k' : v } }, extra);
window.addEventListener('resize', () => Object.values(S.charts).forEach(c => c.resize()));

/* ───────── 明细钻取：点分类 / 商户 / 账户，看每一笔来自哪家银行哪张卡 ───────── */
const srcName = t => (t.account || '未命名账户') + (t.card ? ' · ' + t.card : '');
const DR = { f: null, sort: 'date' };
async function drill(f) {
  if (f) { DR.f = f; DR.sort = 'date'; }
  f = DR.f;
  if (!S.txns) S.txns = await api.get_transactions(S.currency);
  const mer = (f.merchant || '').toLowerCase();
  const rows = S.txns.filter(t => t.date.startsWith(S.month) && (!f.kind || t.kind === f.kind) && (!f.category || t.category === f.category)
    && (!f.cats || f.cats.includes(t.category)) && (!f.account || (t.account || '未命名账户') === f.account) && (!mer || t.desc.toLowerCase().startsWith(mer)))
    .sort((x, y) => DR.sort === 'amount' ? y.amount - x.amount : y.date.localeCompare(x.date) || y.id - x.id);
  const total = rows.reduce((s, t) => s + t.amount, 0), by = {};
  rows.forEach(t => { const k = srcName(t); by[k] = by[k] || { n: 0, amt: 0 }; by[k].n++; by[k].amt += t.amount; });
  const srcs = Object.entries(by).sort((a, b) => b[1].amt - a[1].amt);
  const title = f.title || f.category || f.merchant || f.account || '明细';
  openModal(`<div class="m-head"><div><h2>${esc(title)} · 明细</h2><p>${monthLabel(S.month)} · ${rows.length} 笔 · 合计 <b class="num" style="color:var(--ink)">${money(total)}</b>${rows.length ? ` · 单笔平均 ${money(total / rows.length)}` : ''}</p></div><button class="icon-btn" data-close>${icon('x')}</button></div>
    <div class="m-body">
      <div class="src-grid">${srcs.map(([k, v]) => `<div class="src"><span>${esc(k)}</span><b class="num">${money(v.amt)}</b><div class="track"><i style="width:${total ? v.amt / total * 100 : 0}%"></i></div><em class="num">${v.n} 笔 · ${total ? (v.amt / total * 100).toFixed(0) : 0}%</em></div>`).join('')}</div>
      <div class="toolbar" style="margin:14px 0 6px"><b style="font-size:14px">每一笔</b><div class="seg sp" id="drSort"><button data-v="date" class="${DR.sort === 'date' ? 'on' : ''}">按日期</button><button data-v="amount" class="${DR.sort === 'amount' ? 'on' : ''}">按金额</button></div></div>
      <table class="tbl"><thead><tr><th>日期</th><th>商家 / 描述</th><th>分类</th><th>银行 / 账户</th><th>卡片 / 支付方式</th><th class="r">金额</th></tr></thead><tbody>
      ${rows.map(t => `<tr><td class="num muted">${t.date}</td><td class="desc" style="max-width:300px" title="${esc(t.desc)}">${esc(t.desc)}</td><td><span class="tag">${esc(t.category)}</span></td><td>${esc(t.account || '—')}</td><td class="${t.card ? '' : 'muted'}">${esc(t.card || '未识别')}</td><td class="r num ${t.kind === 'income' ? 'amt-in' : ''}"><b>${t.kind === 'income' ? '+' : t.kind === 'expense' ? '−' : ''}${sym()}${num(t.amount)}</b></td></tr>`).join('') || '<tr><td colspan="6" class="note">没有记录</td></tr>'}</tbody></table>
    </div>
    <div class="m-foot"><span>卡片信息来自账单里的卡号 / 支付方式；没识别到的可在“交易明细”里补上</span><div><button class="btn" id="drOpen">在交易明细中打开</button><button class="btn primary" data-close>关闭</button></div></div>`);
  $$('#drSort button').forEach(b => b.onclick = () => { DR.sort = b.dataset.v; drill(); });
  $('#drOpen').onclick = () => { Object.assign(S.filter, { q: f.merchant || '', kind: f.kind || '', cat: f.category || '', acc: f.account || '', scope: 'month', page: 0 }); closeModal(); go('txns'); };
}

function donut(id, rows, label, kind) {
  const top = rows.filter(r => r.amount > 0).slice(0, 7), rest = rows.filter(r => r.amount > 0).slice(7);
  const data = top.map(r => ({ name: r.name, value: r.amount, share: r.share, count: r.count }));
  if (rest.length) data.push({ name: '其他', value: +rest.reduce((s, r) => s + r.amount, 0).toFixed(2), share: +rest.reduce((s, r) => s + r.share, 0).toFixed(1), count: rest.reduce((s, r) => s + r.count, 0) });
  const colors = colorMap(data.map(d => d.name)), total = data.reduce((s, d) => s + d.value, 0);
  const html = `<div class="donut-wrap"><div class="donut"><div class="chart" id="${id}"></div><div class="donut-c"><span>${label}</span><b class="num">${money(total, 0)}</b></div></div>
    <ul class="legend">${data.map((d, i) => `<li data-i="${i}"><i style="background:${colors[d.name]}"></i><span>${esc(d.name)}</span><b class="num">${money(d.value)}</b><em class="num">${d.share}%</em></li>`).join('')}</ul></div>`;
  const open = name => drill(name === '其他' && rest.length ? { kind, cats: rest.map(r => r.name), title: '其他' } : { kind, category: name });
  const draw = () => {
    const c = chart(id, { tooltip: { trigger: 'item', formatter: p => `<b>${p.name}</b><br>${money(p.value)} · ${p.data.share}%<br><span style="color:${css('--ink-3')}">${p.data.count} 笔</span>` }, legend: { show: false },
      series: [{ type: 'pie', radius: ['62%', '88%'], padAngle: 1.5, itemStyle: { borderRadius: 5 }, label: { show: false }, emphasis: { scaleSize: 5 }, data: data.map(d => ({ ...d, itemStyle: { color: colors[d.name] } })) }] });
    $$(`#${id}`)[0].closest('.donut-wrap').querySelectorAll('li').forEach(li => {
      li.onmouseenter = () => c.dispatchAction({ type: 'highlight', dataIndex: +li.dataset.i });
      li.onmouseleave = () => c.dispatchAction({ type: 'downplay', dataIndex: +li.dataset.i });
      li.onclick = () => open(data[+li.dataset.i].name);
    });
    c.on('click', p => open(p.name));
  };
  return { html: data.length ? html : '<div class="note">本月没有记录</div>', draw: data.length ? draw : () => {} };
}

/* ───────── 小组件 ───────── */
function delta(pct, goodWhenUp) {
  if (pct == null) return '';
  const up = pct > 0, flat = Math.abs(pct) < 0.05;
  const cls = flat ? '' : (up === goodWhenUp ? 'good' : 'bad');
  return `<span class="delta ${cls}">${flat ? '持平' : (up ? '▲' : '▼') + ' ' + Math.abs(pct).toFixed(1) + '%'}</span>`;
}
function chg(p) { // 表格内的涨跌（支出语境：涨为红）
  if (p == null) return '<span class="muted">—</span>';
  return `<span class="${p > 0 ? 'up' : p < 0 ? 'down' : 'muted'}">${p > 0 ? '+' : ''}${p.toFixed(1)}%</span>`;
}
function pill(level) { const [t, ic] = LEVEL[level]; return `<span class="pill ${level}">${icon(ic)}${t}</span>`; }
function scoreRing(score) {
  const r = 64, c = 2 * Math.PI * r, v = score == null ? 0 : score;
  const word = score == null ? '暂无' : score >= 85 ? '优秀' : score >= 70 ? '良好' : score >= 55 ? '一般' : '需改善';
  return `<div class="ring"><svg viewBox="0 0 150 150"><circle class="bg" cx="75" cy="75" r="${r}"/><circle class="fg" cx="75" cy="75" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}" data-to="${c * (1 - v / 100)}"/></svg><div><b class="num">${score ?? '—'}</b><span>财务健康 · ${word}</span></div></div>`;
}
function scoreParts(parts) {
  return `<div class="parts">${parts.map(p => `<div class="part"><span>${p.name}</span><div class="track"><i style="width:${p.score / p.max * 100}%"></i></div><em class="num">${p.score}/${p.max}</em><small>${esc(p.note)}</small></div>`).join('') || '<span class="muted" style="color:var(--ink-3)">数据不足，无法评分</span>'}</div>`;
}
function animateRings() { requestAnimationFrame(() => $$('.ring .fg').forEach(e => e.style.strokeDashoffset = e.dataset.to)); }

/* ───────── 页面：概览 ───────── */
function pageOverview() {
  const a = S.a, k = a.kpi, prevTxt = k.prev_month ? '较上月' : '';
  const sr = k.savings_rate;
  const d1 = donut('c-exp', a.expense_cats, '总支出', 'expense');
  const top3 = a.advice.slice(0, 4);
  const html = `
  <div class="grid g4">
    <div class="card kpi hero"><label>本月结余</label><div class="v num"><small>${k.net < 0 ? '−' : ''}${sym()}</small>${num(Math.abs(k.net))}</div>
      <div class="d">${sr == null ? '未导入收入，暂无储蓄率' : `储蓄率 <span class="delta">${sr}%</span>`}</div></div>
    <div class="card kpi" style="--dot:var(--s1)"><label>收入</label><div class="v num"><small>${sym()}</small>${num(k.income)}</div>
      <div class="d">${delta(k.income_change, true)} ${k.income_change != null ? prevTxt : k.income_count + ' 笔'}</div></div>
    <div class="card kpi" style="--dot:var(--s2)"><label>支出</label><div class="v num"><small>${sym()}</small>${num(k.expense)}</div>
      <div class="d">${delta(k.expense_change, false)} ${k.expense_change != null ? prevTxt : k.expense_count + ' 笔'}</div></div>
    <div class="card kpi" style="--dot:var(--s3)"><label>日均支出</label><div class="v num"><small>${sym()}</small>${num(k.daily_avg)}</div>
      <div class="d">共 ${k.expense_count} 笔支出${k.is_current ? ` · 已过 ${k.days_elapsed} 天` : ''}</div></div>
  </div>
  <div class="grid g32">
    <div class="card"><div class="card-h"><h3>支出构成</h3><span>点击分类查看每一笔</span></div>${d1.html}</div>
    <div class="card"><div class="card-h"><h3>财务健康</h3><a data-go="advice">全部建议 →</a></div>
      <div class="score">${scoreRing(a.score.total)}${scoreParts(a.score.parts)}</div></div>
  </div>
  <div class="grid g32">
    <div class="card"><div class="card-h"><h3>近 12 个月收支</h3><span>柱：收入 / 支出　线：结余</span></div><div class="chart" id="c-trend"></div></div>
    <div class="card"><div class="card-h"><h3>重点提醒</h3><a data-go="advice">${a.advice.length} 条建议 →</a></div>
      <div class="mini-adv">${top3.map(x => `<div data-go="advice">${pill(x.level)}<span>${esc(x.title)}</span></div>`).join('') || '<span class="note">暂无</span>'}</div></div>
  </div>
  <div class="grid g32">
    <div class="card"><div class="card-h"><h3>本月累计支出</h3><span>${k.prev_month ? '对比上月同期' : '逐日累计'}</span></div><div class="chart" id="c-cum"></div></div>
    <div class="card"><div class="card-h"><h3>最大的几笔支出</h3><a data-go="txns">全部明细 →</a></div>
      <table class="tbl"><tbody>${a.top_expenses.slice(0, 6).map(t => `<tr data-drill='${esc(JSON.stringify({ kind: 'expense', category: t.category }))}'><td class="muted num">${t.date.slice(5)}</td><td class="desc" style="max-width:190px" title="${esc(t.desc)}">${esc(t.desc)}</td><td><span class="tag">${esc(t.category)}</span></td><td class="r num">${money(t.amount)}</td></tr>`).join('') || '<tr><td class="note">本月没有支出</td></tr>'}</tbody></table></div>
  </div>`;
  return { html, draw() { d1.draw(); drawTrend('c-trend'); drawCum('c-cum'); animateRings(); } };
}
function drawTrend(id) {
  const t = S.a.trend;
  chart(id, { xAxis: axisCat(t.map(r => r.month.slice(2).replace('-', '/'))), yAxis: axisVal(),
    series: [
      { name: '收入', type: 'bar', data: t.map(r => r.income), barMaxWidth: 16, barGap: '20%', itemStyle: { color: css('--s1'), borderRadius: [4, 4, 0, 0] } },
      { name: '支出', type: 'bar', data: t.map(r => r.expense), barMaxWidth: 16, itemStyle: { color: css('--s2'), borderRadius: [4, 4, 0, 0] } },
      { name: '结余', type: 'line', data: t.map(r => r.net), symbol: 'circle', symbolSize: 7, lineStyle: { width: 2, color: css('--ink') }, itemStyle: { color: css('--ink'), borderColor: css('--surface'), borderWidth: 2 } },
    ] });
}
function drawCum(id) {
  const d = S.a.daily, series = [{ name: '本月', type: 'line', data: d.cum, showSymbol: false, smooth: .25, lineStyle: { width: 2.5, color: css('--s1') }, itemStyle: { color: css('--s1') },
    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(42,120,214,.22)' }, { offset: 1, color: 'rgba(42,120,214,0)' }]) } }];
  if (d.prev_cum) series.push({ name: '上月', type: 'line', data: d.prev_cum, showSymbol: false, smooth: .25, lineStyle: { width: 2, type: [5, 5], color: css('--ink-3') }, itemStyle: { color: css('--ink-3') } });
  chart(id, { tooltip: { trigger: 'axis', axisPointer: { type: 'line', lineStyle: { color: css('--axis') } }, formatter: ps => `<b>${+S.month.slice(5)}月${ps[0].axisValue}日</b><br>` + ps.map(p => `${p.marker}${p.seriesName}累计　<b>${p.value == null ? '—' : money(p.value)}</b>`).join('<br>') },
    xAxis: axisCat(d.days, { boundaryGap: false, axisLabel: { color: css('--ink-3'), interval: 4 } }), yAxis: axisVal(), series });
}

/* ───────── 页面：分析 ───────── */
function pageAnalysis() {
  const a = S.a, k = a.kpi, hasAvg = k.hist_months > 0;
  const d2 = donut('c-inc', a.income_cats, '总收入', 'income');
  const maxAmt = Math.max(1, ...a.expense_cats.map(r => r.amount));
  const html = `
  <div class="grid g23">
    <div class="card"><div class="card-h"><h3>各类支出对比</h3><span>${hasAvg ? `本月 vs 近 ${k.hist_months} 月均值` : '本月'}</span></div><div class="chart tall" id="c-cmp"></div></div>
    <div class="card"><div class="card-h"><h3>支出分类表</h3><span>${k.is_current ? '本月未结束，对比仅供参考　' : ''}环比＝较上月　较均值＝较近 ${k.hist_months || 3} 月平均</span></div>
      <table class="tbl"><thead><tr><th>分类</th><th class="r">金额</th><th>占比</th><th class="r">笔数</th><th class="r">上月</th><th class="r">环比</th><th class="r">较均值</th></tr></thead>
      <tbody>${a.expense_cats.map(r => `<tr data-drill='${esc(JSON.stringify({ kind: 'expense', category: r.name }))}'><td>${esc(r.name)}</td><td class="r num"><b>${money(r.amount)}</b></td><td><div class="bar-cell"><div><i style="width:${r.amount / maxAmt * 100}%"></i></div><span class="num muted">${r.share}%</span></div></td><td class="r num">${r.count}</td><td class="r num muted">${r.prev == null ? '—' : money(r.prev, 0)}</td><td class="r num">${chg(r.change)}</td><td class="r num">${chg(r.vs_avg)}</td></tr>`).join('') || '<tr><td colspan="7" class="note">本月没有支出记录</td></tr>'}</tbody></table></div>
  </div>
  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>收入来源</h3><span>${k.income_count} 笔</span></div>${d2.html}</div>
    <div class="card"><div class="card-h"><h3>分类趋势</h3><span>近 ${a.cat_trend.months.length} 个月支出结构</span></div><div class="chart" id="c-ct"></div></div>
  </div>
  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>每日支出</h3><span>看清钱是哪几天花出去的</span></div><div class="chart" id="c-day"></div></div>
    <div class="card"><div class="card-h"><h3>星期分布</h3><span>本月各星期几的支出合计</span></div><div class="chart" id="c-wd"></div></div>
  </div>
  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>花钱最多的商户</h3><span>Top 10 · 点击查看明细</span></div>
      <table class="tbl"><thead><tr><th>商户</th><th>分类</th><th class="r">笔数</th><th class="r">金额</th><th class="r">占支出</th></tr></thead><tbody>
      ${a.merchants.map(m => `<tr data-drill='${esc(JSON.stringify({ kind: 'expense', merchant: m.name }))}'><td class="desc" style="max-width:200px">${esc(m.name)}</td><td><span class="tag">${esc(m.category)}</span></td><td class="r num">${m.count}</td><td class="r num">${money(m.amount)}</td><td class="r num muted">${m.share}%</td></tr>`).join('') || '<tr><td colspan="5" class="note">暂无</td></tr>'}</tbody></table></div>
    <div class="card"><div class="card-h"><h3>账户分布</h3><span>各银行 / 支付渠道 · 点击查看明细</span></div>
      <table class="tbl"><thead><tr><th>账户</th><th class="r">笔数</th><th class="r">收入</th><th class="r">支出</th></tr></thead><tbody>
      ${a.accounts.map(m => `<tr data-drill='${esc(JSON.stringify({ account: m.name }))}'><td>${esc(m.name)}</td><td class="r num">${m.count}</td><td class="r num amt-in">${m.income ? money(m.income) : '<span class="muted">—</span>'}</td><td class="r num">${m.expense ? money(m.expense) : '<span class="muted">—</span>'}</td></tr>`).join('') || '<tr><td colspan="4" class="note">暂无</td></tr>'}</tbody></table>
      <div class="card-h" style="margin-top:22px"><h3>月度汇总</h3><span>历史对比</span></div>
      <table class="tbl"><thead><tr><th>月份</th><th class="r">收入</th><th class="r">支出</th><th class="r">结余</th><th class="r">储蓄率</th></tr></thead><tbody>
      ${[...a.trend].reverse().map(r => `<tr${r.month === S.month ? ' style="font-weight:600"' : ''}><td>${monthLabel(r.month)}</td><td class="r num">${money(r.income, 0)}</td><td class="r num">${money(r.expense, 0)}</td><td class="r num ${r.net < 0 ? 'up' : ''}">${money(r.net, 0)}</td><td class="r num muted">${r.savings_rate == null ? '—' : r.savings_rate + '%'}</td></tr>`).join('')}</tbody></table></div>
  </div>`;
  return { html, draw() {
    d2.draw();
    const rows = a.expense_cats.filter(r => r.amount > 0 || r.avg3 > 0).slice(0, 10).reverse();
    const ser = [{ name: '本月', type: 'bar', data: rows.map(r => r.amount), barMaxWidth: 12, itemStyle: { color: css('--s1'), borderRadius: [0, 4, 4, 0] } }];
    if (hasAvg) ser.push({ name: `近 ${k.hist_months} 月均值`, type: 'bar', data: rows.map(r => r.avg3), barMaxWidth: 12, itemStyle: { color: css('--s-other'), borderRadius: [0, 4, 4, 0] } });
    $('#c-cmp').style.height = Math.max(220, rows.length * 38 + 70) + 'px';
    const cmp = chart('c-cmp', { xAxis: axisVal(), yAxis: axisCat(rows.map(r => r.name), { axisLabel: { color: css('--ink-2'), fontSize: 12.5 } }), series: ser });
    cmp.on('click', p => drill({ kind: 'expense', category: p.name }));
    const ct = a.cat_trend, cm = colorMap(ct.series.map(s => s.name));
    chart('c-ct', { xAxis: axisCat(ct.months.map(m => m.slice(2).replace('-', '/'))), yAxis: axisVal(),
      series: ct.series.map(s => ({ name: s.name, type: 'bar', stack: 'a', data: s.data, barMaxWidth: 34, itemStyle: { color: cm[s.name], borderColor: css('--surface'), borderWidth: 1 } })) });
    chart('c-day', { legend: { show: false }, xAxis: axisCat(a.daily.days, { axisLabel: { color: css('--ink-3'), interval: 4 } }), yAxis: axisVal(),
      tooltip: { trigger: 'axis', formatter: ps => `<b>${+S.month.slice(5)}月${ps[0].axisValue}日</b><br>支出　<b>${money(ps[0].value)}</b>` },
      series: [{ type: 'bar', data: a.daily.daily, barMaxWidth: 12, itemStyle: { color: css('--s2'), borderRadius: [3, 3, 0, 0] } }] });
    chart('c-wd', { legend: { show: false }, xAxis: axisCat(a.weekday.map(w => w.name)), yAxis: axisVal(),
      series: [{ name: '支出', type: 'bar', data: a.weekday.map((w, i) => ({ value: w.amount, itemStyle: { color: i >= 5 ? css('--s2') : css('--s1') } })), barMaxWidth: 30, itemStyle: { borderRadius: [4, 4, 0, 0] } }] });
  } };
}

/* ───────── 页面：建议 ───────── */
function meter(m) {
  if (!m) return '';
  const max = Math.max(m.current, m.target, 1e-9) * 1.12;
  const f = v => m.unit === 'pct' ? v + '%' : money(v, 0);
  return `<div class="meter"><div class="row"><span>${esc(m.label)}　现状 <b class="num">${f(m.current)}</b></span><span>目标 <b class="num">${m.lower_better ? '≤ ' : '≥ '}${f(m.target)}</b></span></div>
    <div class="track"><div class="fill" style="width:${Math.max(0, m.current) / max * 100}%"></div><div class="mark" style="left:${m.target / max * 100}%"></div></div></div>`;
}
function pageAdvice() {
  const a = S.a, k = a.kpi, n = { alert: 0, warn: 0, info: 0, good: 0 };
  a.advice.forEach(x => n[x.level]++);
  const flex = a.budget.filter(b => b.save > 0);
  const html = `
  <div class="grid g32">
    <div class="card"><div class="card-h"><h3>财务健康评分</h3><span>${monthLabel(S.month)}</span></div>
      <div class="score">${scoreRing(a.score.total)}${scoreParts(a.score.parts)}</div></div>
    <div class="card hero-save"><span>按建议预算执行，下月可少花</span><b class="num">${money(a.saving_potential, 0)}</b>
      <p>${a.saving_potential > 0 ? `主要来自：${flex.sort((x, y) => y.save - x.save).slice(0, 3).map(b => `${b.name} ${money(b.save, 0)}`).join('、')}` : '当前各类开销都在合理范围内，保持即可。'}</p>
      <p style="margin-top:10px;opacity:.75">${[n.alert && `${n.alert} 项需立即关注`, n.warn && `${n.warn} 项建议调整`, n.good && `${n.good} 项做得不错`].filter(Boolean).join(' · ')}</p></div>
  </div>
  <div class="advice">${a.advice.map(x => `<div class="card adv ${x.level}">${pill(x.level)}<h4>${esc(x.title)}</h4><p>${esc(x.detail)}</p>${meter(x.metric)}<div class="act">${icon('check')}<span>${esc(x.action)}</span></div></div>`).join('')}</div>
  <div class="grid g32">
    <div class="card"><div class="card-h"><h3>下月建议预算</h3><span>本月实际 vs 建议上限</span></div><div class="chart tall" id="c-bud"></div></div>
    <div class="card"><div class="card-h"><h3>预算明细</h3><span>${k.hist_months ? `参考近 ${k.hist_months} 月均值` : '仅基于本月'}</span></div>
      <table class="tbl"><thead><tr><th>分类</th><th class="r">本月</th><th class="r">建议</th><th class="r">可省</th></tr></thead><tbody>
      ${a.budget.map(b => `<tr data-drill='${esc(JSON.stringify({ kind: 'expense', category: b.name }))}'><td>${esc(b.name)} ${b.flexible ? '' : '<span class="tag">必需</span>'}</td><td class="r num">${money(b.current, 0)}</td><td class="r num"><b>${money(b.suggested, 0)}</b></td><td class="r num ${b.save > 0 ? 'down' : 'muted'}">${b.save > 0 ? money(b.save, 0) : '—'}</td></tr>`).join('')}
      <tr style="font-weight:650"><td>合计</td><td class="r num">${money(a.budget.reduce((s, b) => s + b.current, 0), 0)}</td><td class="r num">${money(a.budget.reduce((s, b) => s + b.suggested, 0), 0)}</td><td class="r num down">${money(a.saving_potential, 0)}</td></tr></tbody></table></div>
  </div>
  ${a.recurring.length ? `<div class="card" style="margin-bottom:18px"><div class="card-h"><h3>固定扣费清单</h3><span>订阅、会员与每月金额稳定的支出，逐项确认是否仍需要</span></div>
    <table class="tbl"><thead><tr><th>项目</th><th class="r">本月金额</th><th class="r">折合每年</th><th class="r">已出现</th></tr></thead><tbody>
    ${a.recurring.map(r => `<tr><td>${esc(r.name)}</td><td class="r num">${money(r.amount)}</td><td class="r num muted">${money(r.amount * 12, 0)}</td><td class="r num muted">${r.months} 个月</td></tr>`).join('')}</tbody></table></div>` : ''}`;
  return { html, draw() {
    animateRings();
    const rows = [...a.budget].sort((x, y) => x.current - y.current);
    $('#c-bud').style.height = Math.max(220, rows.length * 38 + 70) + 'px';
    const bud = S.charts['c-bud'] = chart('c-bud', { xAxis: axisVal(), yAxis: axisCat(rows.map(r => r.name), { axisLabel: { color: css('--ink-2'), fontSize: 12.5 } }),
      series: [{ name: '本月实际', type: 'bar', data: rows.map(r => r.current), barMaxWidth: 12, itemStyle: { color: css('--s2'), borderRadius: [0, 4, 4, 0] } },
        { name: '建议预算', type: 'bar', data: rows.map(r => r.suggested), barMaxWidth: 12, itemStyle: { color: css('--s3'), borderRadius: [0, 4, 4, 0] } }] });
    bud.on('click', p => drill({ kind: 'expense', category: p.name }));
  } };
}

/* ───────── 页面：交易明细 ───────── */
const catOptions = (kind, cur) => (kind === 'income' ? S.boot.income_categories : kind === 'transfer' ? [S.boot.transfer_category] : S.boot.expense_categories)
  .map(c => `<option${c === cur ? ' selected' : ''}>${c}</option>`).join('');
const kindOptions = cur => Object.entries(KIND).map(([k, v]) => `<option value="${k}"${k === cur ? ' selected' : ''}>${v}</option>`).join('');
function filtered() {
  const f = S.filter, q = f.q.trim().toLowerCase();
  return S.txns.filter(t => (f.scope === 'all' || t.date.startsWith(S.month)) && (!f.kind || t.kind === f.kind) && (!f.cat || t.category === f.cat)
    && (!f.acc || t.account === f.acc) && (!q || (t.desc + ' ' + t.category + ' ' + t.account + ' ' + t.amount).toLowerCase().includes(q)));
}
function pageTxns() {
  const f = S.filter, cats = [...new Set(S.txns.map(t => t.category))].sort(), accs = [...new Set(S.txns.map(t => t.account).filter(Boolean))].sort();
  const html = `<div class="card">
    <div class="toolbar">
      <input class="input grow" id="fq" placeholder="搜索描述、商户、金额…" value="${esc(f.q)}">
      <div class="seg" id="fscope"><button data-v="month" class="${f.scope === 'month' ? 'on' : ''}">仅本月</button><button data-v="all" class="${f.scope === 'all' ? 'on' : ''}">全部</button></div>
      <select class="select" id="fkind"><option value="">全部类型</option>${kindOptions(f.kind)}</select>
      <select class="select" id="fcat"><option value="">全部分类</option>${cats.map(c => `<option${c === f.cat ? ' selected' : ''}>${c}</option>`).join('')}</select>
      <select class="select" id="facc"><option value="">全部账户</option>${accs.map(c => `<option${c === f.acc ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>
      <button class="btn sp" id="addTxn">${icon('plus')}手动记一笔</button>
    </div><div id="txnTable"></div></div>`;
  return { html, draw() {
    const rerender = () => { f.page = 0; renderTxnTable(); };
    $('#fq').oninput = e => { f.q = e.target.value; rerender(); };
    $$('#fscope button').forEach(b => b.onclick = () => { f.scope = b.dataset.v; $$('#fscope button').forEach(x => x.classList.toggle('on', x === b)); rerender(); });
    $('#fkind').onchange = e => { f.kind = e.target.value; rerender(); };
    $('#fcat').onchange = e => { f.cat = e.target.value; rerender(); };
    $('#facc').onchange = e => { f.acc = e.target.value; rerender(); };
    $('#addTxn').onclick = () => editTxn(null);
    renderTxnTable();
  } };
}
function renderTxnTable() {
  const rows = filtered(), per = 60, f = S.filter, pages = Math.max(1, Math.ceil(rows.length / per));
  f.page = Math.min(f.page, pages - 1);
  const view = rows.slice(f.page * per, f.page * per + per);
  const inc = rows.filter(t => t.kind === 'income').reduce((s, t) => s + t.amount, 0), exp = rows.filter(t => t.kind === 'expense').reduce((s, t) => s + t.amount, 0);
  $('#txnTable').innerHTML = `<table class="tbl"><thead><tr><th>日期</th><th>描述</th><th>类型</th><th>分类</th><th>账户</th><th class="r">金额</th><th></th></tr></thead><tbody>
    ${view.map(t => `<tr data-id="${t.id}"><td class="num muted">${t.date}</td><td class="desc" title="${esc(t.desc)}">${esc(t.desc)}</td>
      <td><select class="cell-select" data-f="kind">${kindOptions(t.kind)}</select></td>
      <td><select class="cell-select" data-f="category"${t.kind === 'transfer' ? ' disabled' : ''}>${catOptions(t.kind, t.category)}</select></td>
      <td class="muted">${esc(t.account)}${t.card ? ' · ' + esc(t.card) : ''}</td>
      <td class="r num ${t.kind === 'income' ? 'amt-in' : t.kind === 'transfer' ? 'amt-tr' : ''}"><b>${t.kind === 'income' ? '+' : t.kind === 'expense' ? '−' : ''}${sym()}${num(t.amount)}</b></td>
      <td class="r" style="white-space:nowrap"><button class="icon-btn" data-act="edit" title="编辑">${icon('edit')}</button><button class="icon-btn" data-act="del" title="删除">${icon('trash')}</button></td></tr>`).join('')
      || '<tr><td colspan="7" class="note">没有符合条件的交易</td></tr>'}</tbody></table>
    <div class="pager"><span>共 ${rows.length} 笔　收入 <b class="amt-in num">${money(inc)}</b>　支出 <b class="num" style="color:var(--ink)">${money(exp)}</b></span>
      <div><button class="btn sm" id="pgPrev" ${f.page ? '' : 'disabled'}>上一页</button><span class="num">${f.page + 1} / ${pages}</span><button class="btn sm" id="pgNext" ${f.page < pages - 1 ? '' : 'disabled'}>下一页</button></div></div>`;
  $('#pgPrev').onclick = () => { f.page--; renderTxnTable(); };
  $('#pgNext').onclick = () => { f.page++; renderTxnTable(); };
  $$('#txnTable select').forEach(sel => sel.onchange = async () => {
    const id = +sel.closest('tr').dataset.id, t = await api.update_transaction(id, { [sel.dataset.f]: sel.value });
    Object.assign(S.txns.find(x => x.id === id), t); S.a = null; renderTxnTable();
    toast(sel.dataset.f === 'category' ? '已修改，并记住了这类交易的分类' : '已修改');
  });
  $$('#txnTable [data-act]').forEach(b => b.onclick = async () => {
    const id = +b.closest('tr').dataset.id, t = S.txns.find(x => x.id === id);
    if (b.dataset.act === 'edit') return editTxn(t);
    if (!await confirmBox('删除这笔交易？', `${t.date}　${t.desc}　${money(t.amount)}`, '删除')) return;
    await api.delete_transactions([id]); S.txns = S.txns.filter(x => x.id !== id); S.a = null; renderTxnTable(); toast('已删除');
  });
}
function editTxn(t) {
  const isNew = !t; t = t || { date: S.boot.today, amount: '', kind: 'expense', category: '餐饮美食', desc: '', account: S.boot.accounts[0] || '现金' };
  openModal(`<div class="m-head"><div><h2>${isNew ? '手动记一笔' : '编辑交易'}</h2></div><button class="icon-btn" data-close>${icon('x')}</button></div>
    <div class="m-body"><div class="form">
      <label>日期<input class="input" type="date" id="eDate" value="${t.date}"></label>
      <label>金额（${sym()}）<input class="input" type="number" step="0.01" min="0" id="eAmt" value="${t.amount}"></label>
      <label>类型<select class="select" id="eKind">${kindOptions(t.kind)}</select></label>
      <label>分类<select class="select" id="eCat">${catOptions(t.kind, t.category)}</select></label>
      <label class="wide">描述<input class="input" id="eDesc" value="${esc(t.desc)}" placeholder="例如：房租、工资、和朋友聚餐"></label>
      <label class="wide">账户<input class="input" id="eAcc" value="${esc(t.account)}" list="accList"><datalist id="accList">${S.boot.accounts.map(a => `<option value="${esc(a)}">`).join('')}</datalist></label>
      <label class="wide">卡片 / 支付方式<input class="input" id="eCard" value="${esc(t.card || '')}" placeholder="例如：储蓄卡尾号1234、信用卡、花呗"></label>
    </div></div>
    <div class="m-foot"><span></span><div><button class="btn" data-close>取消</button><button class="btn primary" id="eSave">保存</button></div></div>`, true);
  $('#eKind').onchange = e => $('#eCat').innerHTML = catOptions(e.target.value);
  $('#eSave').onclick = async () => {
    const v = { date: $('#eDate').value, amount: parseFloat($('#eAmt').value), kind: $('#eKind').value, category: $('#eCat').value, desc: $('#eDesc').value.trim() || '(无描述)', account: $('#eAcc').value.trim(), card: $('#eCard').value.trim() };
    if (!v.date || !(v.amount > 0)) return toast('请填写日期和大于 0 的金额');
    if (isNew) await api.commit_import({ file: '手动添加', account: v.account, currency: S.currency || 'CNY', method: '手动', txns: [v] });
    else await api.update_transaction(t.id, v);
    closeModal(); toast('已保存'); await reload(isNew ? v.date.slice(0, 7) : null);
  };
}

/* ───────── 页面：导入与数据 ───────── */
function dropHtml() { return `<div class="drop" data-import>${icon('inbox')}<b>点击选择文件，或直接把文件拖进窗口</b><span>支持 PDF、截图 / 照片、Excel、CSV、Word、OFX —— 可一次选多个银行的流水</span></div>
  <div class="income-entry" data-income>${icon('plus')}<div><b>导入收入凭证</b><span>工资条、到账截图、收入证明 PDF 等 —— 图片会自动识别金额和日期，导入前可核对修改</span></div></div>`; }
async function pageImports() {
  const list = await api.list_imports();
  const html = `<div class="card" style="margin-bottom:18px">${dropHtml()}</div>
  <div class="card" style="margin-bottom:18px"><div class="card-h"><h3>导入记录</h3><span>删除某次导入会一并移除它带来的交易</span></div>
    <table class="tbl"><thead><tr><th>文件</th><th>账户</th><th>识别方式</th><th>覆盖日期</th><th class="r">交易数</th><th>导入时间</th><th></th></tr></thead><tbody>
    ${list.map(i => `<tr data-id="${i.id}"><td class="desc" style="max-width:260px" title="${esc(i.filename)}">${esc(i.filename)}</td><td>${esc(i.account)}</td><td class="muted">${esc(i.method)}</td><td class="num muted">${i.first_date ? i.first_date + ' ~ ' + i.last_date.slice(5) : '—'}</td><td class="r num">${i.remaining}</td><td class="num muted">${i.imported_at}</td><td class="r"><button class="icon-btn" title="删除这次导入">${icon('trash')}</button></td></tr>`).join('') || '<tr><td colspan="7" class="note">还没有导入过文件</td></tr>'}</tbody></table></div>
  <div class="card"><div class="card-h"><h3>数据管理</h3><span>所有数据只保存在这台电脑上，不会上传</span></div>
    <div class="toolbar" style="margin:0"><button class="btn" id="exportBtn">${icon('download')}导出 Excel 报告</button><button class="btn" id="demoBtn">载入示例数据</button><button class="btn danger" id="clearBtn">${icon('trash')}清空全部数据</button></div></div>`;
  return { html, draw() {
    $$('#content tr[data-id] .icon-btn').forEach(b => b.onclick = async () => {
      if (!await confirmBox('删除这次导入？', '这次导入带来的所有交易都会被移除。', '删除')) return;
      await api.delete_import(+b.closest('tr').dataset.id); toast('已删除'); await reload();
    });
    $('#exportBtn').onclick = async () => { if (!S.currency) return toast('还没有数据可导出'); const p = await api.export_excel(S.currency); if (p) toast('已导出：' + p); };
    $('#demoBtn').onclick = loadDemo;
    $('#clearBtn').onclick = async () => { if (!await confirmBox('清空全部数据？', '所有交易和导入记录都会被删除，且无法恢复。', '清空')) return; await api.clear_all(); toast('已清空'); await reload(); };
  } };
}
async function loadDemo() { await api.load_demo(); toast('已载入 6 个月的示例数据'); S.page = 'overview'; await reload(); }

/* ───────── 页面：手机同步 ───────── */
async function pageSync() {
  const st = await api.sync_status(), on = st.running;
  const html = `<div class="grid g23">
    <div class="card sync-qr">
      <div class="qr ${on ? '' : 'off'}">${st.qr}${on ? '' : '<div><b>同步未开启</b><span>开启后才能扫码</span></div>'}</div>
      <button class="btn ${on ? '' : 'primary'}" id="syncToggle" style="width:100%;justify-content:center">${on ? '关闭手机同步' : '开启手机同步'}</button>
      <p class="sync-tip">${on ? '手机与这台电脑连同一个 Wi-Fi，用相机扫一扫' : '关闭时，局域网内的任何设备都无法访问你的数据'}</p>
    </div>
    <div class="card">
      <div class="card-h"><h3>连接信息</h3><span>${on ? '<span class="pill good">' + icon('check') + '同步服务运行中</span>' : '<span class="pill info">' + icon('info') + '未开启</span>'}</span></div>
      <table class="tbl"><tbody>
        <tr><td class="muted" style="width:110px">电脑地址</td><td class="num" style="user-select:text"><b>${on ? esc(st.base) : '—'}</b></td></tr>
        <tr><td class="muted">配对码</td><td><b class="code">${esc(st.token)}</b> <button class="btn sm" id="syncReset" style="margin-left:10px">更换</button></td></tr>
        <tr><td class="muted">这台电脑</td><td>${esc(st.device)}</td></tr>
      </tbody></table>
      <div class="card-h" style="margin-top:22px"><h3>三种用法</h3></div>
      <ol class="steps">
        <li><b>扫码即用（任何手机）</b>相机扫左侧二维码，在浏览器里直接打开手机版，可“添加到主屏幕”。</li>
        <li><b>安卓 App</b>从 <a id="repoLink">${esc(st.repo)}/releases</a> 下载 APK 安装；扫码后点“在 App 中打开”，或在 App 里手动填上面的地址和配对码。App 会保存上次同步的数据，离开电脑也能看。</li>
        <li><b>手机记账</b>在手机上记的每一笔，下次连上同一 Wi-Fi 时自动传回电脑并计入分析。</li>
      </ol>
      <p class="sync-tip" style="text-align:left;margin-top:12px">首次开启时 Windows 防火墙可能弹窗询问，请勾选“专用网络”并允许。配对码相当于密码，不要发给别人；怀疑泄露就点“更换”。</p>
    </div></div>`;
  return { html, draw() {
    $('#syncToggle').onclick = async () => { const r = await api.sync_enable(!on); if (r.error) toast(r.error); else toast(on ? '已关闭手机同步' : '已开启，可以扫码了'); render(); };
    $('#syncReset').onclick = async () => { if (!await confirmBox('更换配对码？', '已配对的手机需要用新的配对码重新连接。', '更换')) return; await api.sync_reset(); render(); };
  } };
}
window.onPhonePush = n => { toast(`手机同步来 ${n} 笔新记账`); reload(); };

function pageEmpty() {
  return { html: `<div class="empty"><div class="welcome"><svg class="brand-logo"><use href="#logo"/></svg>
    <h2>把流水丢进来，看清钱去了哪</h2><p>导入各家银行、微信、支付宝的账单和工资凭证，自动汇总成一份清晰的月度收支报告。</p>
    ${dropHtml()}
    <div class="links"><button class="btn" id="demoBtn">先用示例数据看看效果</button><button class="btn" id="manualBtn">${icon('plus')}手动记一笔</button></div>
    <div class="feat"><div><b>多格式识别</b>PDF 对账单、手机截图、Excel / CSV 都能读，截图走离线文字识别。</div><div><b>全面分析</b>分类占比、月度趋势、环比变化、商户与账户分布一目了然。</div><div><b>可执行建议</b>给出每一类的建议预算和具体做法，而不是空话。</div></div>
  </div></div>`, draw() { $('#demoBtn').onclick = loadDemo; $('#manualBtn').onclick = () => editTxn(null); } };
}

/* ───────── 导入流程 ───────── */
const IMP = { items: [] };
async function startImport(paths, mode = 'auto') {
  if (!paths) paths = await api.pick_files();
  if (!paths || !paths.length) return;
  IMP.items = paths.map(p => ({ path: p, file: p.split(/[\\/]/).pop(), loading: true }));
  renderImport();
  for (const it of IMP.items) { Object.assign(it, await api.parse_file(it.path, mode, null), { loading: false }); prep(it); renderImport(); }
}
function prep(it) { (it.txns || []).forEach(t => t.on = !t.dup); }
function renderImport() {
  const total = IMP.items.reduce((s, it) => s + (it.txns || []).filter(t => t.on).length, 0), busy = IMP.items.some(i => i.loading);
  openModal(`<div class="m-head"><div><h2>确认导入内容</h2><p>核对识别结果，可直接修改；灰色的重复记录默认不导入</p></div><button class="icon-btn" data-close>${icon('x')}</button></div>
    <div class="m-body">${IMP.items.map((it, i) => fileCard(it, i)).join('')}</div>
    <div class="m-foot"><span>${busy ? '正在识别…截图和扫描件需要几秒钟' : `共 ${IMP.items.length} 个文件，已选 ${total} 笔交易`}</span>
      <div><button class="btn" data-close>取消</button><button class="btn primary" id="impOk" ${busy || !total ? 'disabled' : ''}>导入 ${total} 笔</button></div></div>`);
  bindImport();
}
function fileCard(it, i) {
  const head = (meta, extra = '') => `<div class="fhead"><div class="fi">${it.loading ? '<div class="spin"></div>' : icon('file')}</div><div class="fn"><b title="${esc(it.file)}">${esc(it.file)}</b><span>${meta}</span></div>${extra}</div>`;
  if (it.loading) return `<div class="fcard">${head('正在识别…')}</div>`;
  if (it.need_password) return `<div class="fcard" data-i="${i}">${head('这份 PDF 有密码保护', `<input class="input" type="password" placeholder="输入 PDF 密码" data-pw><button class="btn sm" data-retry>解锁</button>`)}</div>`;
  if (it.error) return `<div class="fcard">${head('未能读取')}<div class="fwarn ferr">${icon('alert')}${esc(it.error)}</div></div>`;
  const dups = it.txns.filter(t => t.dup).length;
  return `<div class="fcard" data-i="${i}">${head(`${esc(it.method)} · 识别到 ${it.txns.length} 笔${dups ? ` · ${dups} 笔与已有记录重复` : ''}`,
    `<select class="select" data-mode title="文件类型"><option value="auto"${it.mode === 'auto' ? ' selected' : ''}>自动判断</option><option value="statement"${it.mode === 'statement' ? ' selected' : ''}>银行流水</option><option value="income"${it.mode === 'income' ? ' selected' : ''}>收入凭证</option></select>
     <input class="input" style="width:130px" data-acc value="${esc(it.account)}" title="账户名称" placeholder="账户名称">
     <input class="input" style="width:130px" data-card value="${esc(it.card || '')}" title="卡片 / 卡号后四位" placeholder="卡片（如尾号1234）">
     <select class="select" data-cur title="币种">${['CNY', 'USD', 'HKD', 'EUR', 'GBP'].map(c => `<option${c === it.currency ? ' selected' : ''}>${c}</option>`).join('')}</select>`)}
    ${(it.warnings || []).map(w => `<div class="fwarn">${icon('info')}${esc(w)}</div>`).join('')}
    ${it.txns.length ? `<div class="ftable"><table class="tbl"><thead><tr><th style="width:30px"><input type="checkbox" data-all ${it.txns.every(t => t.on) ? 'checked' : ''}></th><th style="width:138px">日期</th><th>描述</th><th style="width:104px">类型</th><th style="width:118px">分类</th><th class="r" style="width:110px">金额</th></tr></thead><tbody>
    ${it.txns.map((t, j) => `<tr data-j="${j}" class="${t.on ? '' : 'off'}"><td><input type="checkbox" data-f="on" ${t.on ? 'checked' : ''}></td><td><input class="input num" type="date" data-f="date" value="${t.date}"></td><td><input class="input" data-f="desc" value="${esc(t.desc)}"></td>
      <td><select class="select" data-f="kind">${kindOptions(t.kind)}</select></td><td><select class="select" data-f="category">${catOptions(t.kind, t.category)}</select></td>
      <td><input class="input num r" style="text-align:right" type="number" step="0.01" data-f="amount" value="${t.amount}"></td></tr>`).join('')}</tbody></table></div>` : ''}
    <div style="padding:8px 14px"><button class="btn sm" data-addrow>${icon('plus')}补一行</button></div></div>`;
}
function bindImport() {
  $$('#modalCard .fcard[data-i]').forEach(card => {
    const it = IMP.items[+card.dataset.i];
    const reparse = async (mode, pw) => { it.loading = true; renderImport(); Object.assign(it, { need_password: false, error: null }, await api.parse_file(it.path, mode, pw), { loading: false }); prep(it); renderImport(); };
    const q = s => $(s, card);
    if (q('[data-retry]')) { q('[data-retry]').onclick = () => reparse('auto', q('[data-pw]').value); return; }
    q('[data-mode]').onchange = e => reparse(e.target.value, null);
    q('[data-acc]').oninput = e => it.account = e.target.value;
    q('[data-card]').oninput = e => { it.card = e.target.value; it.txns.forEach(t => t.card = it.card); };
    q('[data-cur]').onchange = e => it.currency = e.target.value;
    q('[data-addrow]').onclick = () => { it.txns.push({ date: (it.txns[0] || {}).date || S.boot.today, desc: '', kind: it.mode === 'income' ? 'income' : 'expense', category: it.mode === 'income' ? '其他收入' : '其他支出', amount: '', on: true }); renderImport(); };
    if (q('[data-all]')) q('[data-all]').onchange = e => { it.txns.forEach(t => t.on = e.target.checked); renderImport(); };
    $$('tr[data-j]', card).forEach(tr => {
      const t = it.txns[+tr.dataset.j];
      $$('[data-f]', tr).forEach(inp => inp.onchange = () => {
        const f = inp.dataset.f;
        if (f === 'on') { t.on = inp.checked; renderImport(); return; }
        t[f] = f === 'amount' ? parseFloat(inp.value) : inp.value;
        if (f === 'kind') { t.category = t.kind === 'income' ? '其他收入' : t.kind === 'transfer' ? S.boot.transfer_category : '其他支出'; renderImport(); }
      });
    });
  });
  const ok = $('#impOk');
  if (ok) ok.onclick = async () => {
    ok.disabled = true; let count = 0, last = null, cur = null;
    for (const it of IMP.items) {
      const txns = (it.txns || []).filter(t => t.on && t.date && t.amount > 0);
      if (!txns.length) continue;
      const r = await api.commit_import({ file: it.file, account: it.account, card: it.card, currency: it.currency, method: it.method, txns });
      count += r.count; if (r.months && (!last || r.months.at(-1) > last)) { last = r.months.at(-1); cur = r.currency; }
    }
    closeModal(); toast(`已导入 ${count} 笔交易`);
    if (cur) S.currency = cur; S.page = 'overview'; await reload(last);
  };
}

/* ───────── 弹窗 ───────── */
function openModal(html, narrow = false) {
  const m = $('#modal'), c = $('#modalCard'), sc = $('.m-body', c)?.scrollTop || 0;
  c.className = 'modal-card' + (narrow ? ' narrow' : ''); c.innerHTML = html; m.hidden = false;
  if ($('.m-body', c)) $('.m-body', c).scrollTop = sc;
  $$('[data-close]', c).forEach(b => b.onclick = closeModal);
}
function closeModal() { $('#modal').hidden = true; $('#modalCard').innerHTML = ''; }
function confirmBox(title, text, okText) {
  return new Promise(res => {
    openModal(`<div class="m-head"><div><h2>${esc(title)}</h2></div></div><div class="m-body"><p style="color:var(--ink-2);padding-bottom:10px;user-select:text">${esc(text)}</p></div>
      <div class="m-foot"><span></span><div><button class="btn" id="cNo">取消</button><button class="btn primary" id="cYes">${esc(okText)}</button></div></div>`, true);
    $('#cNo').onclick = () => { closeModal(); res(false); }; $('#cYes').onclick = () => { closeModal(); res(true); };
  });
}

/* ───────── 导航与渲染 ───────── */
const TITLES = { overview: '本月概览', analysis: '收支分析', advice: '开销建议', txns: '交易明细', imports: '导入与数据', sync: '手机同步' };
function months() { return (S.boot.currencies.find(c => c.code === S.currency) || { months: [] }).months; }
function renderTop() {
  const ms = months(), has = ms.length > 0;
  $('#curSeg').innerHTML = S.boot.currencies.length > 1 ? S.boot.currencies.map(c => `<button data-c="${c.code}" class="${c.code === S.currency ? 'on' : ''}">${c.code}</button>`).join('') : '';
  $$('#curSeg button').forEach(b => b.onclick = () => { S.currency = b.dataset.c; S.month = null; S.a = null; S.txns = null; pickMonth(); render(); });
  $('#monthNav').style.display = has ? '' : 'none';
  if (has) {
    $('#mSel').innerHTML = [...ms].reverse().map(m => `<option value="${m}"${m === S.month ? ' selected' : ''}>${monthLabel(m)}</option>`).join('');
    const i = ms.indexOf(S.month); $('#mPrev').disabled = i <= 0; $('#mNext').disabled = i >= ms.length - 1;
  }
  $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.page === S.page));
  $('#pageTitle').textContent = TITLES[S.page];
}
function pickMonth(prefer) {
  const ms = months();
  if (prefer && ms.includes(prefer)) S.month = prefer; else if (!ms.includes(S.month)) S.month = ms.at(-1) || null;
}
async function render() {
  renderTop();
  Object.values(S.charts).forEach(c => c.dispose()); S.charts = {};
  const has = S.boot.total > 0 && S.month;
  let page;
  if (S.page === 'sync') page = await pageSync();
  else if (!has && S.page !== 'imports') page = pageEmpty();
  else {
    if (has && !S.a) S.a = await api.get_analysis(S.month, S.currency);
    if (has && S.page === 'txns' && !S.txns) S.txns = await api.get_transactions(S.currency);
    page = S.page === 'imports' ? await pageImports() : S.a.has_data || S.page === 'txns' ? { overview: pageOverview, analysis: pageAnalysis, advice: pageAdvice, txns: pageTxns }[S.page]() : { html: '<div class="note">这个月没有记录</div>', draw() {} };
  }
  const k = S.a && S.a.kpi;
  $('#pageSub').textContent = S.page === 'sync' ? '在手机上查看分析、随手记账，回到同一 Wi-Fi 自动同步' : !has ? '导入账单后即可开始' : S.page === 'imports' ? `共 ${S.boot.total} 笔交易` : `${monthLabel(S.month)} · ${k.count} 笔收支${k.is_current ? ' · 本月进行中' : ''}`;
  const urgent = S.a ? S.a.advice.filter(x => x.level === 'alert' || x.level === 'warn').length : 0;
  $('#adviceBadge').textContent = urgent || '';
  $('#content').innerHTML = page.html; $('#content').scrollTop = 0;
  page.draw();
  $$('#content [data-go]').forEach(e => e.onclick = () => go(e.dataset.go));
  $$('#content [data-drill]').forEach(e => e.onclick = () => drill(JSON.parse(e.dataset.drill)));
  $$('#content [data-income]').forEach(e => e.onclick = () => startImport(null, 'income'));
  $$('#content [data-import]').forEach(e => e.onclick = () => startImport());
}
function go(p) { S.page = p; render(); }
async function reload(preferMonth) {
  S.boot = await api.bootstrap(); S.a = null; S.txns = null;
  if (!S.boot.currencies.find(c => c.code === S.currency)) S.currency = S.boot.currencies[0]?.code || null;
  pickMonth(preferMonth); await render();
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $('#themeBtn').innerHTML = t === 'dark' ? `${icon('sun')}<span>浅色模式</span>` : `${icon('moon')}<span>深色模式</span>`;
}

async function init() {
  S.boot = await api.bootstrap(); setTheme(S.boot.theme);
  if (DEV) { // 调试参数：?dev=1&page=advice&theme=dark&noanim=1
    const q = new URLSearchParams(location.search);
    if (q.get('page')) S.page = q.get('page');
    if (q.get('theme')) setTheme(q.get('theme'));
    if (q.has('noanim')) document.head.insertAdjacentHTML('beforeend', '<style>*{animation:none!important;transition:none!important}</style>');
  }
  S.currency = S.boot.currencies[0]?.code || null; pickMonth();
  $$('#nav button').forEach(b => b.onclick = () => go(b.dataset.page));
  $('#importBtn').onclick = () => startImport();
  $('#mSel').onchange = e => { S.month = e.target.value; S.a = null; render(); };
  $('#mPrev').onclick = () => { const ms = months(); S.month = ms[ms.indexOf(S.month) - 1]; S.a = null; render(); };
  $('#mNext').onclick = () => { const ms = months(); S.month = ms[ms.indexOf(S.month) + 1]; S.a = null; render(); };
  $('#themeBtn').onclick = () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; setTheme(t); api.set_theme(t); render(); };
  $('#modal').onmousedown = e => { if (e.target.id === 'modal' && !$('#impOk')) closeModal(); };
  let depth = 0; const mask = $('#dropMask');
  window.addEventListener('dragenter', e => { e.preventDefault(); if (e.dataTransfer?.types?.includes('Files')) { depth++; mask.classList.add('on'); } });
  window.addEventListener('dragleave', e => { e.preventDefault(); if (--depth <= 0) { depth = 0; mask.classList.remove('on'); } });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => { e.preventDefault(); depth = 0; mask.classList.remove('on'); });
  await render();
  if (DEV && new URLSearchParams(location.search).has('import')) startImport();
  if (DEV && new URLSearchParams(location.search).get('drill')) drill({ kind: 'expense', category: new URLSearchParams(location.search).get('drill') });
}
window.onFilesDropped = paths => startImport(paths);
if (DEV) init(); else if (window.pywebview && window.pywebview.api) init(); else window.addEventListener('pywebviewready', init);
