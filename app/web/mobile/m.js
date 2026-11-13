/* 流水分析助手 · 手机端。同一份代码：① 由电脑端直接提供给手机浏览器 ② 打进安卓 App（离线可看上次同步的数据）。 */
'use strict';
const IN_APP = location.protocol === 'file:';
const LS = {
  get(k, d) { try { const v = localStorage.getItem('ll_' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('ll_' + k, JSON.stringify(v)); } catch (e) { /* 存储满了也不影响使用 */ } },
};
const S = { cfg: LS.get('cfg', null), data: LS.get('data', null), pending: LS.get('pending', []), cur: LS.get('cur', null), month: null, tab: 'overview', charts: {}, online: false, q: '' };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icon = n => `<svg><use href="#i-${n}"/></svg>`;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = () => S.data && (S.data.currencies.find(c => c.code === S.cur) || S.data.currencies[0]);
const A = () => { const c = C(); return c && c.analyses[S.month]; };
const sym = () => (C() || {}).symbol || '¥';
const num = (v, d = 2) => Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const money = (v, d = 2) => (v < 0 ? '−' : '') + sym() + num(Math.abs(v), d);
const mlabel = m => I18N.month(m);
const KIND = { expense: '支出', income: '收入', transfer: '不计收支' };
const SIGN = { income: '+', expense: '−', refund: '↩ ', transfer: '' };
const LEVEL = { alert: ['需立即关注', 'alert'], warn: ['建议调整', 'alert'], info: ['提示', 'info'], good: ['保持', 'check'] };
const TITLES = { overview: '本月概览', analysis: '收支分析', advice: '开销建议', txns: '交易明细', sync: '同步' };
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('on'), 2400); }

/* ───────── 同步 ───────── */
function normHost(h) { h = (h || '').trim().replace(/\/+$/, ''); if (h && !/^https?:\/\//i.test(h)) h = 'http://' + h; return h; }
async function call(path, opt = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), opt.timeout || 8000);
  try {
    const r = await fetch(S.cfg.host + path, { method: opt.body ? 'POST' : 'GET', headers: { 'X-Token': S.cfg.token, ...(opt.body ? { 'Content-Type': 'application/json' } : {}) }, body: opt.body ? JSON.stringify(opt.body) : undefined, signal: ctl.signal });
    const j = await r.json();
    if (!r.ok) throw Object.assign(new Error(j.error || '请求失败'), { status: r.status });
    return j;
  } finally { clearTimeout(timer); }
}
function setStatus(cls, text) { const s = $('#status'); s.className = cls; s.innerHTML = `<i></i>${esc(text)}`; }
async function sync(manual) {
  if (!S.cfg || !S.cfg.host) { setStatus('off', '尚未连接电脑'); return false; }
  setStatus('busy', '正在同步…');
  try {
    if (S.pending.length) {
      await call('/api/push', { body: { txns: S.pending } });
      S.pending = []; LS.set('pending', S.pending);
    }
    S.data = await call('/api/sync?lang=' + I18N.lang, { timeout: 15000 }); LS.set('data', S.data);
    S.online = true; pick(); setStatus('ok', `已同步 · ${S.data.device} · ${S.data.synced_at.slice(5)}`);
    if (manual) toast('同步完成'); render(); return true;
  } catch (e) {
    S.online = false;
    const why = e.status === 401 || e.status === 429 ? e.message : '连不上电脑';
    setStatus('off', S.data ? `${why} · 显示 ${S.data.synced_at.slice(5)} 的数据` : why);
    if (manual) toast(e.status ? e.message : '连不上电脑：确认同一 Wi-Fi，且电脑端已开启手机同步');
    if (S.tab === 'sync') render(); return false;
  }
}
function pick() {
  const c = C(); if (!c) { S.month = null; return; }
  S.cur = c.code; LS.set('cur', S.cur);
  const ms = Object.keys(c.analyses).sort();
  if (!ms.includes(S.month)) S.month = ms.at(-1) || null;
}

/* ───────── 图表 ───────── */
const FIXED = { '交通出行': 1, '餐饮美食': 2, '超市日用': 3, '通讯订阅': 4, '购物消费': 5, '医疗健康': 6, '住房物业': 7, '娱乐休闲': 8, '工资薪酬': 1, '奖金补贴': 4, '投资理财': 3, '退款报销': 7, '转账收入': 2, '其他收入': 5 };
function colorMap(names) {
  const used = new Set(), out = {};
  names.forEach(n => { const s = FIXED[n]; if (s && !used.has(s)) { out[n] = s; used.add(s); } });
  names.forEach(n => { if (out[n]) return; for (let i = 1; i <= 8; i++) if (!used.has(i)) { out[n] = i; used.add(i); break; } });
  const m = {}; names.forEach(n => m[n] = n === '其他' || !out[n] ? css('--s-other') : css('--s' + out[n])); return m;
}
function chart(id, option) {
  const el = document.getElementById(id); if (!el) return;
  const c = echarts.init(el, null, { renderer: 'svg' });
  c.setOption(I18N.deep(Object.assign({
    animationDuration: 500, textStyle: { fontFamily: 'system-ui, sans-serif', color: css('--ink-2') },
    grid: { left: 4, right: 8, top: 30, bottom: 2, containLabel: true },
    tooltip: { trigger: 'axis', confine: true, backgroundColor: css('--surface'), borderColor: css('--line-2'), textStyle: { color: css('--ink'), fontSize: 12.5 }, extraCssText: 'border-radius:12px;', valueFormatter: v => v == null ? '—' : money(v) },
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 9, itemHeight: 9, itemGap: 12, textStyle: { color: css('--ink-2'), fontSize: 11.5 } },
  }, option)));
  S.charts[id] = c; return c;
}
const axC = (data, extra = {}) => Object.assign({ type: 'category', data, axisLine: { lineStyle: { color: css('--axis') } }, axisTick: { show: false }, axisLabel: { color: css('--ink-3'), fontSize: 11 } }, extra);
const axV = () => ({ type: 'value', splitNumber: 4, splitLine: { lineStyle: { color: css('--grid') } }, axisLabel: { color: css('--ink-3'), fontSize: 11, formatter: v => I18N.big(v) } });
window.addEventListener('resize', () => Object.values(S.charts).forEach(c => c.resize()));
function donut(id, rows, label, kind) {
  const pos = rows.filter(r => r.amount > 0), top = pos.slice(0, 6), rest = pos.slice(6);
  const data = top.map(r => ({ name: r.name, value: r.amount, share: r.share }));
  if (rest.length) data.push({ name: '其他', value: +rest.reduce((s, r) => s + r.amount, 0).toFixed(2), share: +rest.reduce((s, r) => s + r.share, 0).toFixed(1) });
  if (!data.length) return { html: '<p class="muted" style="text-align:center;padding:20px 0">本月没有记录</p>', draw() {} };
  const col = colorMap(data.map(d => d.name)), total = data.reduce((s, d) => s + d.value, 0);
  return {
    html: `<div class="donut-wrap"><div class="donut"><div class="chart" id="${id}"></div><div class="donut-c"><span>${label}</span><b class="num">${money(total, 0)}</b></div></div>
      <ul class="legend">${data.map(d => `<li ${DA(d.name === '其他' && rest.length ? { kind, cats: rest.map(r => r.name), title: '其他' } : { kind, category: d.name })}><i style="background:${col[d.name]}"></i><span>${esc(d.name)}</span><em class="num">${d.share}%</em></li>`).join('')}</ul></div>`,
    draw() { chart(id, { legend: { show: false }, tooltip: { trigger: 'item', confine: true, formatter: p => `${p.name}<br><b>${money(p.value)}</b> · ${p.data.share}%` }, series: [{ type: 'pie', radius: ['60%', '90%'], padAngle: 1.5, itemStyle: { borderRadius: 4 }, label: { show: false }, data: data.map(d => ({ ...d, itemStyle: { color: col[d.name] } })) }] }); },
  };
}

/* ───────── 小组件 ───────── */
const pill = l => `<span class="pill ${l}">${icon(LEVEL[l][1])}${LEVEL[l][0]}</span>`;
const chg = (p, goodUp) => p == null ? '' : `<em class="${(p > 0) === goodUp ? '' : ''}">${p > 0 ? '▲' : '▼'}${Math.abs(p).toFixed(0)}%</em>`;
const pct = p => p == null ? '' : `<span class="${p > 0 ? 'up' : 'down'}">${p > 0 ? '+' : ''}${p.toFixed(0)}%</span>`;
function ring(score) {
  const r = 44, c = 2 * Math.PI * r, w = score == null ? '暂无' : score >= 85 ? '优秀' : score >= 70 ? '良好' : score >= 55 ? '一般' : '需改善';
  return `<div class="ring"><svg viewBox="0 0 104 104"><circle class="bg" cx="52" cy="52" r="${r}"/><circle class="fg" cx="52" cy="52" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}" data-to="${c * (1 - (score || 0) / 100)}"/></svg><div><b class="num">${score ?? '—'}</b><span>${w}</span></div></div>`;
}
const parts = ps => `<div class="parts">${ps.map(p => `<div class="part"><span>${p.name}</span><div class="track"><i style="width:${p.score / p.max * 100}%"></i></div><em class="num">${p.score}/${p.max}</em></div>`).join('')}</div>`;
function meter(m) {
  if (!m) return '';
  const max = Math.max(m.current, m.target, 1e-9) * 1.12, f = v => m.unit === 'pct' ? v + '%' : money(v, 0);
  return `<div class="meter"><div class="lab"><span>现状 <b class="num">${f(m.current)}</b></span><span>目标 <b class="num">${m.lower_better ? '≤ ' : '≥ '}${f(m.target)}</b></span></div><div class="track"><div class="fill" style="width:${Math.max(0, m.current) / max * 100}%"></div><div class="mark" style="left:${m.target / max * 100}%"></div></div></div>`;
}
const pendBanner = () => S.pending.length ? `<div class="card" style="padding:11px 14px;font-size:13.5px;display:flex;gap:9px;align-items:center">${pill('info')}<span>${S.pending.length} 笔手机记账待同步，连上电脑后计入分析</span></div>` : '';

/* ───────── 页面 ───────── */
function pOverview() {
  const a = A(), k = a.kpi, d = donut('c-exp', a.expense_cats, '总支出', 'expense'), t = a.trend.slice(-6);
  return { html: `${pendBanner()}
    <div class="card hero"><label>本月结余</label><div class="v num"><small>${k.net < 0 ? '−' : ''}${sym()}</small>${num(Math.abs(k.net))}</div>
      <div class="row"><div><span>收入</span><b class="num">${money(k.income, 0)}</b>${chg(k.income_change)}</div><div><span>支出</span><b class="num">${money(k.expense, 0)}</b>${chg(k.expense_change)}</div><div><span>储蓄率</span><b class="num">${k.savings_rate == null ? '—' : k.savings_rate + '%'}</b></div></div></div>
    <div class="card"><h3>支出构成 <span>点分类看每一笔</span></h3>${d.html}</div>
    <div class="card"><h3>财务健康 <span>满分 100</span></h3><div class="score">${ring(a.score.total)}${parts(a.score.parts)}</div></div>
    <div class="card"><h3>重点提醒 <span data-go="advice" style="color:var(--accent)">全部 ${a.advice.length} 条 ›</span></h3>${a.advice.slice(0, 3).map(x => `<div class="mini" data-go="advice">${pill(x.level)}<span>${esc(x.title)}</span></div>`).join('')}</div>
    <div class="card"><h3>近 ${t.length} 个月收支</h3><div class="chart" id="c-trend"></div></div>
    <div class="card"><h3>本月累计支出 <span>${k.prev_month ? '虚线为上月' : ''}</span></h3><div class="chart" id="c-cum"></div></div>`,
    draw() {
      d.draw();
      chart('c-trend', { xAxis: axC(t.map(r => +r.month.slice(5) + '月')), yAxis: axV(), series: [
        { name: '收入', type: 'bar', data: t.map(r => r.income), barMaxWidth: 14, itemStyle: { color: css('--s1'), borderRadius: [4, 4, 0, 0] } },
        { name: '支出', type: 'bar', data: t.map(r => r.expense), barMaxWidth: 14, itemStyle: { color: css('--s2'), borderRadius: [4, 4, 0, 0] } },
        { name: '结余', type: 'line', data: t.map(r => r.net), symbolSize: 6, lineStyle: { width: 2, color: css('--ink') }, itemStyle: { color: css('--ink') } }] });
      const dd = a.daily, ser = [{ name: '本月', type: 'line', data: dd.cum, showSymbol: false, smooth: .25, lineStyle: { width: 2.5, color: css('--s1') }, itemStyle: { color: css('--s1') }, areaStyle: { color: 'rgba(42,120,214,.14)' } }];
      if (dd.prev_cum) ser.push({ name: '上月', type: 'line', data: dd.prev_cum, showSymbol: false, smooth: .25, lineStyle: { width: 2, type: [5, 5], color: css('--ink-3') }, itemStyle: { color: css('--ink-3') } });
      chart('c-cum', { xAxis: axC(dd.days, { boundaryGap: false, axisLabel: { color: css('--ink-3'), fontSize: 11, interval: 4 } }), yAxis: axV(), series: ser });
    } };
}
function pAnalysis() {
  const a = A(), k = a.kpi, d = donut('c-inc', a.income_cats, '总收入', 'income'), max = Math.max(1, ...a.expense_cats.map(r => r.amount)), ct = a.cat_trend;
  return { html: `
    <div class="card"><h3>支出分类 <span>${k.hist_months ? '右侧为较近 ' + k.hist_months + ' 月均值' : ''}</span></h3><div class="rows">${a.expense_cats.filter(r => r.amount > 0).map(r => `<div class="row-i" ${DA({ kind: 'expense', category: r.name })}><div class="t">${esc(r.name)} <span class="s">${r.share}% · ${r.count} 笔</span></div><div class="a num">${money(r.amount)} <span style="font-size:12px;font-weight:500">${pct(r.vs_avg)}</span></div><div class="track"><i style="width:${r.amount / max * 100}%"></i></div></div>`).join('') || '<p class="muted">本月没有支出</p>'}</div></div>
    <div class="card"><h3>收入来源 <span>${k.income_count} 笔</span></h3>${d.html}</div>
    <div class="card"><h3>分类趋势 <span>近 ${ct.months.length} 个月</span></h3><div class="chart" id="c-ct" style="height:250px"></div></div>
    <div class="card"><h3>星期分布</h3><div class="chart" id="c-wd" style="height:180px"></div></div>
    <div class="card"><h3>花钱最多的商户</h3><div class="rows">${a.merchants.slice(0, 8).map(m => `<div class="row-i" ${DA({ kind: 'expense', merchant: m.name })}><div class="t">${esc(m.name)} <span class="tag">${esc(m.category)}</span></div><div class="a num">${money(m.amount)}</div></div>`).join('') || '<p class="muted">暂无</p>'}</div></div>
    <div class="card"><h3>账户分布</h3><div class="rows">${a.accounts.map(m => `<div class="row-i" ${DA({ account: m.name })}><div class="t">${esc(m.name)} <span class="s">${m.count} 笔</span></div><div class="a num">${m.income ? `<span class="in">+${money(m.income, 0)}</span> ` : ''}${m.expense ? '−' + money(m.expense, 0) : ''}</div></div>`).join('')}</div></div>
    <div class="card"><h3>月度汇总</h3><div class="rows">${[...a.trend].reverse().map(r => `<div class="row-i"><div class="t">${mlabel(r.month)} <span class="s">收 ${money(r.income, 0)} · 支 ${money(r.expense, 0)}</span></div><div class="a num ${r.net < 0 ? 'up' : ''}">${money(r.net, 0)}</div></div>`).join('')}</div></div>`,
    draw() {
      d.draw(); const cm = colorMap(ct.series.map(s => s.name));
      chart('c-ct', { grid: { left: 4, right: 8, top: 54, bottom: 2, containLabel: true }, legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 9, itemHeight: 9, itemGap: 10, textStyle: { color: css('--ink-2'), fontSize: 11.5 } }, xAxis: axC(ct.months.map(m => +m.slice(5) + '月')), yAxis: axV(), series: ct.series.map(s => ({ name: s.name, type: 'bar', stack: 'a', data: s.data, barMaxWidth: 26, itemStyle: { color: cm[s.name], borderColor: css('--surface'), borderWidth: 1 } })) });
      chart('c-wd', { legend: { show: false }, grid: { left: 4, right: 8, top: 10, bottom: 2, containLabel: true }, xAxis: axC(a.weekday.map((_, i) => I18N.weekday(i))), yAxis: axV(), series: [{ name: '支出', type: 'bar', barMaxWidth: 22, data: a.weekday.map((w, i) => ({ value: w, itemStyle: { color: i >= 5 ? css('--s2') : css('--s1'), borderRadius: [4, 4, 0, 0] } })) }] });
    } };
}
function pAdvice() {
  const a = A(), top = a.budget.filter(b => b.save > 0).sort((x, y) => y.save - x.save).slice(0, 3), bmax = Math.max(1, ...a.budget.map(b => Math.max(b.current, b.suggested)));
  return { html: `
    <div class="card hero"><label>按建议预算执行，下月可少花</label><div class="v num">${money(a.saving_potential, 0)}</div><p>${top.length ? '主要来自：' + top.map(b => `${b.name} ${money(b.save, 0)}`).join('、') : '各类开销都在合理范围内，保持即可。'}</p></div>
    ${a.advice.map(x => `<div class="card adv ${x.level}">${pill(x.level)}<h4>${esc(x.title)}</h4><p>${esc(x.detail)}</p>${meter(x.metric)}<div class="act">${icon('check')}<span>${esc(x.action)}</span></div></div>`).join('')}
    <div class="card"><h3>下月建议预算 <span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--s2)"></i> 本月　<i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--s3)"></i> 建议</span></h3>
      ${a.budget.map(b => `<div class="bud" ${DA({ kind: 'expense', category: b.name })}><div class="h"><span>${esc(b.name)}${b.flexible ? '' : ' <span class="tag">必需</span>'}</span><span class="num">${money(b.current, 0)} → <b>${money(b.suggested, 0)}</b></span></div><div class="bars"><div style="width:${Math.max(1, b.current / bmax * 100)}%;background:var(--s2)"></div><div style="width:${Math.max(1, b.suggested / bmax * 100)}%;background:var(--s3)"></div></div></div>`).join('')}</div>
    ${a.recurring.length ? `<div class="card"><h3>固定扣费 <span>逐项确认是否还需要</span></h3><div class="rows">${a.recurring.map(r => `<div class="row-i"><div class="t">${esc(r.name)} <span class="s">一年约 ${money(r.amount * 12, 0)}</span></div><div class="a num">${money(r.amount)}</div></div>`).join('')}</div></div>` : ''}`, draw() {} };
}
function pTxns() {
  const q = S.q.trim().toLowerCase(), c = C();
  const mine = S.pending.filter(t => t.currency === c.code && t.date.startsWith(S.month)).map(t => ({ ...t, pend: true }));
  const rows = [...mine, ...c.txns.filter(t => t.date.startsWith(S.month))].filter(t => !q || (t.desc + t.category + t.account + t.amount).toLowerCase().includes(q)).sort((x, y) => y.date.localeCompare(x.date));
  const days = {}; rows.forEach(t => (days[t.date] = days[t.date] || []).push(t));
  return { html: `<input class="input" id="q" placeholder="搜索描述、分类、金额…" value="${esc(S.q)}" style="margin-bottom:6px">
    ${Object.keys(days).map(d => `<div class="day"><span>${+d.slice(5, 7)}月${+d.slice(8)}日</span><span class="num">支出 ${money(days[d].filter(t => t.kind === 'expense').reduce((s, t) => s + t.amount, 0))}</span></div>
      <div class="card" style="padding:4px 14px;margin-bottom:0"><div class="rows">${days[d].map(t => `<div class="row-i"${t.pend ? ` data-cid="${t.cid}"` : ''}><div class="t">${esc(t.desc)}</div><div class="a num ${t.kind === 'income' ? 'in' : t.kind === 'transfer' ? 'muted' : ''}">${SIGN[t.kind] || ''}${sym()}${num(t.amount)}</div><div class="s" style="grid-column:1/3"><span class="tag">${esc(t.category)}</span> ${esc(t.account || '')}${t.card ? ' · ' + esc(t.card) : ''}${t.pend ? ' · <span style="color:var(--accent)">待同步（点按可撤销）</span>' : ''}</div></div>`).join('')}</div></div>`).join('') || '<p class="muted" style="text-align:center;padding:40px 0">这个月没有符合条件的交易</p>'}`,
    draw() {
      const i = $('#q'); i.oninput = () => { S.q = i.value; const pos = i.selectionStart; render(); const n = $('#q'); n.focus(); n.setSelectionRange(pos, pos); };
      $$('[data-cid]').forEach(e => e.onclick = () => { if (!confirm('撤销这笔还没同步的记账？')) return; S.pending = S.pending.filter(t => t.cid !== e.dataset.cid); LS.set('pending', S.pending); render(); });
    } };
}
function pSync() {
  const c = S.cfg || {}, web = !IN_APP;
  const deep = c.host ? `ledgerlens://pair?h=${encodeURIComponent(c.host)}&t=${encodeURIComponent(c.token)}` : '';
  return { html: `
    <div class="card"><h3>连接状态 <span>${S.online ? '<span class="pill good">' + icon('check') + '已连接</span>' : '<span class="pill warn">' + icon('alert') + '未连接</span>'}</span></h3>
      <div class="kv"><span>电脑</span><b>${esc(S.data ? S.data.device : '—')}</b></div>
      <div class="kv"><span>上次同步</span><b class="num">${esc(S.data ? S.data.synced_at : '从未')}</b></div>
      <div class="kv"><span>待同步的记账</span><b class="num">${S.pending.length} 笔</b></div>
      <button class="btn primary" id="syncNow" style="margin-top:12px">${icon('sync')}立即同步</button></div>
    <div class="card"><h3>电脑地址与配对码</h3><div class="form">
      <label>电脑地址<input class="input" id="host" inputmode="url" autocapitalize="off" placeholder="例如 192.168.1.8:8756" value="${esc((c.host || '').replace(/^https?:\/\//, ''))}"></label>
      <label>配对码<input class="input" id="tok" autocapitalize="characters" maxlength="8" placeholder="电脑端“手机同步”页上的 8 位码" value="${esc(c.token || '')}" style="letter-spacing:.14em"></label>
      <button class="btn" id="saveCfg">保存并连接</button></div></div>
    ${web && deep ? `<div class="card"><h3>安卓 App</h3><p class="muted" style="font-size:13.5px;margin-bottom:12px">装了 App 的话，点下面的按钮把这台电脑的配对信息带进 App。App 会保存数据，离开电脑也能查看。</p><a class="btn" href="${deep}" style="text-decoration:none;color:inherit">在 App 中打开</a></div>` : ''}
    <div class="card"><h3>语言</h3><select class="select" id="mLang">${I18N.LANGS.map(([c, n]) => `<option value="${c}"${c === I18N.lang ? ' selected' : ''}>${n}</option>`).join('')}</select></div>
    <div class="card help"><p><b>怎么连？</b>电脑上打开“流水分析助手 → 手机同步 → 开启”，手机和电脑连同一个 Wi-Fi，${IN_APP ? '填入页面上显示的地址和配对码。' : '用相机扫二维码即可。'}</p>
      <p><b>离开电脑还能用吗？</b>${IN_APP ? '能。App 显示上次同步的数据；在外面记的账会先存在手机里，回到同一 Wi-Fi 后自动传回电脑。' : '浏览器版需要连着电脑才能打开；想离线查看请安装安卓 App。'}</p>
      <p><b>数据安全</b>数据只在你的手机和电脑之间通过家里的局域网传输，不经过任何服务器。</p></div>`,
    draw() {
      $('#syncNow').onclick = () => sync(true);
      $('#mLang').onchange = e => { LS.set('lang', e.target.value); location.reload(); };
      $('#saveCfg').onclick = () => { const h = normHost($('#host').value), t = $('#tok').value.trim().toUpperCase(); if (!h || !t) return toast('请填写地址和配对码'); S.cfg = { host: h, token: t }; LS.set('cfg', S.cfg); sync(true); };
    } };
}
function pEmpty() {
  return { html: `<div class="empty"><svg class="logo"><use href="#logo"/></svg><h2>连接你的电脑</h2><p>在电脑端打开“手机同步”，把收支分析带到手机上。</p></div>`, draw() {} };
}

/* ───────── 分类明细：点分类看每一笔来自哪家银行哪张卡 ───────── */
function openDrill(f) {
  const c = C(), mer = (f.merchant || '').toLowerCase();
  const rows = c.txns.filter(t => t.date.startsWith(S.month) && (!f.kind || t.kind === f.kind) && (!f.category || t.category === f.category) && (!f.cats || f.cats.includes(t.category)) && (!f.account || (t.account || '未命名账户') === f.account) && (!mer || t.desc.toLowerCase().startsWith(mer))).sort((x, y) => y.date.localeCompare(x.date));
  const total = rows.reduce((s, t) => s + t.amount, 0), by = {};
  const src = t => (t.account || '未命名账户') + (t.card ? ' · ' + t.card : '');
  rows.forEach(t => { const k = src(t); by[k] = by[k] || { n: 0, amt: 0 }; by[k].n++; by[k].amt += t.amount; });
  $('#sheetCard').innerHTML = `<h2>${esc(f.title || f.category || f.merchant || f.account)}<button id="shClose">关闭</button></h2>
    <p class="muted" style="font-size:13px;margin:-8px 0 12px">${mlabel(S.month)} · ${rows.length} 笔 · 合计 <b class="num" style="color:var(--ink)">${money(total)}</b></p>
    <div class="card" style="padding:6px 14px"><div class="rows">${Object.entries(by).sort((a, b) => b[1].amt - a[1].amt).map(([k, v]) => `<div class="row-i"><div class="t">${esc(k)} <span class="s">${v.n} 笔</span></div><div class="a num">${money(v.amt)}</div><div class="track"><i style="width:${total ? v.amt / total * 100 : 0}%;background:linear-gradient(90deg,var(--brand-a),var(--brand-b))"></i></div></div>`).join('')}</div></div>
    <div class="card" style="padding:4px 14px"><div class="rows">${rows.map(t => `<div class="row-i"><div class="t" data-raw>${esc(t.desc)}</div><div class="a num ${t.kind === 'income' ? 'in' : ''}">${t.kind === 'income' ? '+' : t.kind === 'expense' ? '−' : ''}${sym()}${num(t.amount)}</div><div class="s" style="grid-column:1/3">${+t.date.slice(5, 7)}月${+t.date.slice(8)}日 · ${esc(src(t))}${t.pair ? ` ↔ <span data-raw>${esc((t.pair.account || '未命名账户') + (t.pair.card ? ' · ' + t.pair.card : ''))}</span>` : ''}</div></div>`).join('') || '<p class="muted" style="padding:14px 0">没有记录</p>'}</div></div>`;
  $('#sheet').hidden = false; $('#sheetCard').scrollTop = 0;
  $('#shClose').onclick = () => $('#sheet').hidden = true;
}
const DA = o => `data-drill='${esc(JSON.stringify(o))}'`;

/* ───────── 记一笔 ───────── */
function openAdd() {
  const d = S.data, kind = openAdd.kind || 'expense', cats = k => (k === 'income' ? (d ? d.income_categories : ['工资薪酬', '其他收入']) : k === 'transfer' ? ['内部转账'] : (d ? d.expense_categories : ['餐饮美食', '其他支出']));
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  $('#sheetCard').innerHTML = `<h2>记一笔<button id="shClose">取消</button></h2><div class="form">
    <input class="input amt num" id="aAmt" type="number" inputmode="decimal" step="0.01" placeholder="0.00">
    <div class="seg" id="aKind">${Object.entries(KIND).map(([k, v]) => `<button data-k="${k}" class="${k === kind ? 'on' : ''}">${v}</button>`).join('')}</div>
    <div class="two"><label>分类<select class="select" id="aCat">${cats(kind).map(c => `<option value="${c}">${c}</option>`).join('')}</select></label><label>日期<input class="input" id="aDate" type="date" value="${today}"></label></div>
    <label>描述<input class="input" id="aDesc" placeholder="例如：午饭、打车、工资"></label>
    <div class="two"><label>账户<input class="input" id="aAcc" value="${esc(LS.get('acc', '手机记账'))}"></label><label>币种<select class="select" id="aCur">${[...new Set([S.cur || 'CNY', 'CNY', 'USD', 'HKD', 'EUR', 'GBP'])].map(c => `<option>${c}</option>`).join('')}</select></label></div>
    <button class="btn primary" id="aSave">保存</button></div>`;
  $('#sheet').hidden = false; let k = kind;
  $('#shClose').onclick = () => $('#sheet').hidden = true;
  $$('#aKind button').forEach(b => b.onclick = () => { k = b.dataset.k; $$('#aKind button').forEach(x => x.classList.toggle('on', x === b)); $('#aCat').innerHTML = cats(k).map(c => `<option value="${c}">${c}</option>`).join(''); });
  $('#aSave').onclick = () => {
    const amount = parseFloat($('#aAmt').value);
    if (!(amount > 0)) return toast('请输入金额');
    const t = { cid: Date.now().toString(36) + Math.random().toString(36).slice(2, 8), date: $('#aDate').value || today, amount, kind: k, category: $('#aCat').value, desc: $('#aDesc').value.trim() || $('#aCat').value, account: $('#aAcc').value.trim() || '手机记账', currency: $('#aCur').value };
    LS.set('acc', t.account); S.pending.push(t); LS.set('pending', S.pending); $('#sheet').hidden = true; toast('已记录'); render(); sync(false);
  };
  setTimeout(() => $('#aAmt').focus(), 80);
}

/* ───────── 渲染 ───────── */
function render() {
  Object.values(S.charts).forEach(c => c.dispose()); S.charts = {};
  const c = C(), a = A(), ms = c ? Object.keys(c.analyses).sort() : [];
  $('#title').textContent = TITLES[S.tab];
  $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab));
  $('#monthNav').style.display = a && S.tab !== 'sync' ? '' : 'none';
  if (a) { $('#mSel').innerHTML = [...ms].reverse().map(m => `<option value="${m}"${m === S.month ? ' selected' : ''}>${mlabel(m)}</option>`).join(''); const i = ms.indexOf(S.month); $('#mPrev').disabled = i <= 0; $('#mNext').disabled = i >= ms.length - 1; }
  let p;
  if (S.tab === 'sync') p = pSync();
  else if (!a) { const e = pEmpty(), s = pSync(); p = S.data && !a ? { html: pendBanner() + '<p class="muted" style="text-align:center;padding:50px 0">电脑端还没有数据，先在电脑上导入账单，或点右下角 + 记一笔</p>', draw() {} } : { html: e.html + s.html, draw: s.draw }; }
  else p = { overview: pOverview, analysis: pAnalysis, advice: pAdvice, txns: pTxns }[S.tab]();
  const el = $('#content'), keep = S.tab === render.last ? el.scrollTop : 0; render.last = S.tab;
  el.innerHTML = p.html; el.scrollTop = keep; p.draw();
  $$('[data-go]', el).forEach(e => e.onclick = () => { S.tab = e.dataset.go; render(); });
  $$('[data-drill]', el).forEach(e => e.onclick = () => openDrill(JSON.parse(e.dataset.drill)));
  requestAnimationFrame(() => $$('.ring .fg').forEach(e => e.style.strokeDashoffset = e.dataset.to));
}
function readPairing() { // 来自二维码（?t=）或 App 深链（#pair=）
  const q = new URLSearchParams(location.search), h = new URLSearchParams(location.hash.slice(1));
  if (h.get('pair') && h.get('t')) { S.cfg = { host: normHost(h.get('pair')), token: h.get('t').toUpperCase() }; LS.set('cfg', S.cfg); history.replaceState(null, '', location.pathname); return true; }
  if (!IN_APP) { const t = q.get('t') || (S.cfg && S.cfg.host === location.origin ? S.cfg.token : ''); S.cfg = { host: location.origin, token: (t || '').toUpperCase() }; if (t) LS.set('cfg', S.cfg); }
  return false;
}
window.onPair = () => { if (readPairing()) { toast('已配对，正在同步'); sync(true); } };
window.addEventListener('hashchange', window.onPair);
document.addEventListener('visibilitychange', () => { if (!document.hidden) sync(false); });

(function init() {
  const q = new URLSearchParams(location.search);
  if (q.has('noanim')) document.head.insertAdjacentHTML('beforeend', '<style>*{animation:none!important;transition:none!important}</style>');
  if (q.get('tab')) S.tab = q.get('tab');
  if (q.get('drill')) setTimeout(() => A() && openDrill({ kind: 'expense', category: q.get('drill') }), 1500);
  I18N.set(q.get('lang') || LS.get('lang', (navigator.language || 'zh').slice(0, 2)));
  I18N.walk(document.body);
  readPairing(); pick();
  $$('#tabs button').forEach(b => b.onclick = () => { S.tab = b.dataset.tab; render(); });
  $('#fab').onclick = openAdd;
  $('#sheet').onclick = e => { if (e.target.id === 'sheet') $('#sheet').hidden = true; };
  $('#mSel').onchange = e => { S.month = e.target.value; render(); };
  $('#mPrev').onclick = () => { const ms = Object.keys(C().analyses).sort(); S.month = ms[ms.indexOf(S.month) - 1]; render(); };
  $('#mNext').onclick = () => { const ms = Object.keys(C().analyses).sort(); S.month = ms[ms.indexOf(S.month) + 1]; render(); };
  setStatus('off', S.data ? `显示 ${S.data.synced_at.slice(5)} 同步的数据` : '尚未连接电脑');
  render(); sync(false);
})();
