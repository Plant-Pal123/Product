// Lightweight SVG charts with a shared tooltip. Colours come from CSS custom
// properties (see css/styles.css) so light/dark themes swap in one place.

import { MONTHS } from './data/crops.js';

const NS = 'http://www.w3.org/2000/svg';

export const RAMPS = {
  ndvi: ['#eef4dc', '#d2e6ab', '#a8cf78', '#7ab64f', '#4f9936', '#2f7a27', '#185c1c'],
  slope: ['#fdeee3', '#f9cfb0', '#f3a877', '#eb7f45', '#d95926', '#b0431a', '#853112'],
  zones: ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'],
  pos: ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf'],
  neg: ['#fbd9d8', '#f4a9a8', '#ec7877', '#e34948', '#c23636'],
};

export const fmtMoney = (v, digits = 0) =>
  `${v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
export const fmtNum = (v, d = 1) => Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });

export function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'style') node.style.cssText = v;
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v);
  }
  if (parent) parent.appendChild(node);
  return node;
}

function svgRoot(host, height, label) {
  host.replaceChildren();
  const width = Math.max(260, host.clientWidth || 600);
  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': label, class: 'chart' }, host);
  return { svg, width, height };
}

function niceMax(v) {
  const p = 10 ** Math.floor(Math.log10(Math.max(1e-9, v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

function ticks(min, max, count = 4) {
  const step = niceMax((max - min) / count);
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Math.round(v * 1000) / 1000);
  return out;
}

// Shared tooltip ------------------------------------------------------------
const tip = document.createElement('div');
tip.className = 'tooltip';
tip.setAttribute('role', 'status');
document.body.appendChild(tip);

// rows: [{ value, label, color?, dash? }]
export function showTip(evt, title, rows) {
  tip.replaceChildren();
  if (title) {
    const h = document.createElement('div');
    h.className = 'tt-title';
    h.textContent = title;
    tip.appendChild(h);
  }
  for (const r of rows) {
    const row = document.createElement('div');
    row.className = 'tt-row';
    if (r.color) {
      const key = document.createElement('span');
      key.className = `tt-key${r.dash ? ' dash' : ''}`;
      key.style.setProperty('--k', r.color);
      row.appendChild(key);
    }
    const v = document.createElement('strong');
    v.textContent = r.value;
    const l = document.createElement('span');
    l.textContent = r.label;
    row.append(v, l);
    tip.appendChild(row);
  }
  tip.classList.add('on');
  const x = evt.clientX ?? evt.target.getBoundingClientRect().left;
  const y = evt.clientY ?? evt.target.getBoundingClientRect().top;
  const w = tip.offsetWidth;
  const h = tip.offsetHeight;
  tip.style.left = `${Math.min(window.innerWidth - w - 8, x + 14)}px`;
  tip.style.top = `${Math.max(8, y - h - 12)}px`;
}
export const hideTip = () => tip.classList.remove('on');

function bindHover(node, fn) {
  node.setAttribute('tabindex', '0');
  node.addEventListener('pointermove', fn);
  node.addEventListener('focus', fn);
  node.addEventListener('pointerleave', hideTip);
  node.addEventListener('blur', hideTip);
}

function yAxis(svg, { x0, x1, y, tickVals, fmt }) {
  for (const t of tickVals) {
    el('line', { x1: x0, x2: x1, y1: y(t), y2: y(t), class: t === 0 ? 'axis' : 'grid' }, svg);
    el('text', { x: x0 - 6, y: y(t) + 4, class: 'tick', 'text-anchor': 'end', text: fmt(t) }, svg);
  }
}

// Crosshair layer for month/week-indexed charts.
function crosshair(svg, { n, xAt, top, bottom, left, right, onIndex }) {
  const line = el('line', { y1: top, y2: bottom, class: 'crosshair', style: 'opacity:0' }, svg);
  const hit = el('rect', { x: left, y: top, width: right - left, height: bottom - top, fill: 'transparent', class: 'hit' }, svg);
  const handler = (evt) => {
    const box = svg.getBoundingClientRect();
    const scale = svg.viewBox.baseVal.width / box.width;
    const px = evt.clientX != null ? (evt.clientX - box.left) * scale : xAt(n - 1);
    let best = 0;
    for (let i = 1; i < n; i++) if (Math.abs(xAt(i) - px) < Math.abs(xAt(best) - px)) best = i;
    line.setAttribute('x1', xAt(best));
    line.setAttribute('x2', xAt(best));
    line.style.opacity = 1;
    onIndex(evt, best);
  };
  bindHover(hit, handler);
  hit.addEventListener('pointerleave', () => { line.style.opacity = 0; });
}

// Rainfall: observed + forecast bars against the 10-year normal ----------------
export function rainfallChart(host, field, outlook) {
  const { svg, width, height } = svgRoot(host, 220, 'Monthly rainfall, observed and forecast, versus 10-year normal');
  const m = { l: 40, r: 10, t: 12, b: 26 };
  const cl = field.climate;
  const values = MONTHS.map((_, i) => (i < 9 ? cl.observedRain[i] : cl.forecastRain[i - 9]));
  const hi = values.map((v, i) => (i < 9 ? v : v * outlook.forecastRainRange[1]));
  const max = niceMax(Math.max(...hi, ...cl.rain) * 1.05);
  const band = (width - m.l - m.r) / 12;
  const y = (v) => m.t + (height - m.t - m.b) * (1 - v / max);
  yAxis(svg, { x0: m.l, x1: width - m.r, y, tickVals: ticks(0, max), fmt: (t) => `${t}` });
  el('text', { x: 4, y: m.t + 2, class: 'tick', text: 'mm' }, svg);
  const bw = Math.min(22, band - 6);
  values.forEach((v, i) => {
    const cx = m.l + band * (i + 0.5);
    const forecast = i >= 9;
    const h = Math.max(1, y(0) - y(v));
    el('path', { d: roundedTop(cx - bw / 2, y(v), bw, h, 3), class: forecast ? 'bar forecast' : 'bar s1' }, svg);
    if (forecast) {
      const lo = v * outlook.forecastRainRange[0];
      const up = v * outlook.forecastRainRange[1];
      el('line', { x1: cx, x2: cx, y1: y(lo), y2: y(up), class: 'whisker' }, svg);
      el('line', { x1: cx - 4, x2: cx + 4, y1: y(up), y2: y(up), class: 'whisker' }, svg);
      el('line', { x1: cx - 4, x2: cx + 4, y1: y(lo), y2: y(lo), class: 'whisker' }, svg);
    }
    el('text', { x: cx, y: height - 8, class: 'tick', 'text-anchor': 'middle', text: MONTHS[i][0] + (band > 34 ? MONTHS[i].slice(1) : '') }, svg);
  });
  const pts = cl.rain.map((v, i) => `${m.l + band * (i + 0.5)},${y(v)}`).join(' ');
  el('polyline', { points: pts, class: 'line ref' }, svg);
  crosshair(svg, {
    n: 12, xAt: (i) => m.l + band * (i + 0.5), top: m.t, bottom: y(0), left: m.l, right: width - m.r,
    onIndex: (evt, i) => {
      const rows = [
        { value: `${values[i]} mm`, label: i < 9 ? 'Observed 2026' : `Forecast (${Math.round(values[i] * outlook.forecastRainRange[0])}–${Math.round(values[i] * outlook.forecastRainRange[1])} mm)`, color: 'var(--series-1)' },
        { value: `${cl.rain[i]} mm`, label: '10-year normal', color: 'var(--ink-muted)', dash: true },
        { value: `${values[i] - cl.rain[i] >= 0 ? '+' : '−'}${Math.abs(values[i] - cl.rain[i])} mm`, label: 'vs normal' },
      ];
      showTip(evt, `${MONTHS[i]} 2026`, rows);
    },
  });
}

function roundedTop(x, y, w, h, r) {
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

function roundedRight(x, y, w, h, r) {
  const rr = Math.min(r, w, h / 2);
  if (w <= 0) return '';
  return `M${x},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h - rr}Q${x + w},${y + h} ${x + w - rr},${y + h}H${x}Z`;
}

// Temperature: normal min–max band, normal mean, 2026 observed + forecast ----
export function temperatureChart(host, field) {
  const { svg, width, height } = svgRoot(host, 220, 'Monthly temperature, 2026 versus normal');
  const m = { l: 40, r: 10, t: 12, b: 26 };
  const cl = field.climate;
  const obs = MONTHS.map((_, i) => (i < 9 ? cl.observedTemp[i] : cl.forecastTemp[i - 9]));
  const lo = Math.floor(Math.min(...cl.tmin) / 5) * 5;
  const hi = Math.ceil(Math.max(...cl.tmax) / 5) * 5;
  const band = (width - m.l - m.r) / 12;
  const x = (i) => m.l + band * (i + 0.5);
  const y = (v) => m.t + (height - m.t - m.b) * (1 - (v - lo) / (hi - lo));
  yAxis(svg, { x0: m.l, x1: width - m.r, y, tickVals: ticks(lo, hi, 4), fmt: (t) => `${t}°` });
  const top = cl.tmax.map((v, i) => `${x(i)},${y(v)}`);
  const bot = cl.tmin.map((v, i) => `${x(i)},${y(v)}`).reverse();
  el('polygon', { points: [...top, ...bot].join(' '), class: 'band' }, svg);
  el('polyline', { points: cl.tavg.map((v, i) => `${x(i)},${y(v)}`).join(' '), class: 'line ref' }, svg);
  el('polyline', { points: obs.slice(0, 9).map((v, i) => `${x(i)},${y(v)}`).join(' '), class: 'line s1' }, svg);
  el('polyline', { points: obs.slice(8).map((v, i) => `${x(i + 8)},${y(v)}`).join(' '), class: 'line s1 dashed' }, svg);
  el('circle', { cx: x(8), cy: y(obs[8]), r: 4, class: 'dot s1' }, svg);
  MONTHS.forEach((mo, i) => el('text', { x: x(i), y: height - 8, class: 'tick', 'text-anchor': 'middle', text: band > 34 ? mo : mo[0] }, svg));
  crosshair(svg, {
    n: 12, xAt: x, top: m.t, bottom: height - m.b, left: m.l, right: width - m.r,
    onIndex: (evt, i) => showTip(evt, `${MONTHS[i]} 2026`, [
      { value: `${obs[i]} °C`, label: i < 9 ? 'Observed mean' : 'Forecast mean', color: 'var(--series-1)', dash: i >= 9 },
      { value: `${cl.tavg[i]} °C`, label: 'Normal mean', color: 'var(--ink-muted)', dash: true },
      { value: `${cl.tmin[i]} to ${cl.tmax[i]} °C`, label: 'Normal min–max' },
    ]),
  });
}

// Soil moisture: weekly volumetric moisture vs field capacity / wilting point
export function moistureChart(host, field) {
  const { svg, width, height } = svgRoot(host, 220, 'Weekly soil moisture with field capacity and wilting point');
  const m = { l: 40, r: 10, t: 12, b: 26 };
  const mo = field.moisture;
  const n = mo.weeks.length;
  const hi = Math.ceil((mo.fieldCapacity + 4) / 5) * 5;
  const lo = Math.max(0, Math.floor((mo.wiltingPoint - 4) / 5) * 5);
  const x = (i) => m.l + ((width - m.l - m.r) * i) / (n - 1);
  const y = (v) => m.t + (height - m.t - m.b) * (1 - (v - lo) / (hi - lo));
  yAxis(svg, { x0: m.l, x1: width - m.r, y, tickVals: ticks(lo, hi, 4), fmt: (t) => `${t}%` });
  const stress = mo.wiltingPoint + (mo.fieldCapacity - mo.wiltingPoint) * 0.5;
  el('rect', { x: m.l, y: y(stress), width: width - m.l - m.r, height: y(mo.wiltingPoint) - y(stress), class: 'zone-warn' }, svg);
  for (const [v, label] of [[mo.fieldCapacity, 'Field capacity'], [stress, '50% available water'], [mo.wiltingPoint, 'Wilting point']]) {
    el('line', { x1: m.l, x2: width - m.r, y1: y(v), y2: y(v), class: 'threshold' }, svg);
    el('text', { x: width - m.r - 4, y: y(v) - 4, class: 'tick', 'text-anchor': 'end', text: label }, svg);
  }
  const f = mo.forecastFrom;
  el('polyline', { points: mo.weeks.slice(0, f).map((v, i) => `${x(i)},${y(v)}`).join(' '), class: 'line s1' }, svg);
  el('polyline', { points: mo.weeks.slice(f - 1).map((v, i) => `${x(i + f - 1)},${y(v)}`).join(' '), class: 'line s1 dashed' }, svg);
  el('circle', { cx: x(f - 1), cy: y(mo.weeks[f - 1]), r: 4, class: 'dot s1' }, svg);
  ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'].forEach((lab, k) => {
    const i = Math.round(k * 4.35);
    if (i < n) el('text', { x: x(i), y: height - 8, class: 'tick', 'text-anchor': 'middle', text: lab }, svg);
  });
  crosshair(svg, {
    n, xAt: x, top: m.t, bottom: height - m.b, left: m.l, right: width - m.r,
    onIndex: (evt, i) => {
      const v = mo.weeks[i];
      const state = v < mo.wiltingPoint ? 'below wilting point' : v < stress ? 'crop water stress' : 'adequate';
      showTip(evt, `Week ${i + 14}${i >= f ? ' (forecast)' : ''}`, [
        { value: `${v}%`, label: 'Volumetric moisture', color: 'var(--series-1)', dash: i >= f },
        { value: state, label: '' },
      ]);
    },
  });
}

// Margin range across crops: P10–P90 whisker with P50 dot -------------------
export function marginRangeChart(host, results, selectedId, onSelect) {
  const rowH = 30;
  const m = { l: 124, r: 16, t: 8, b: 26 };
  const { svg, width, height } = svgRoot(host, m.t + m.b + rowH * results.length, 'Expected margin per hectare by crop, P10 to P90 range');
  const lows = results.map((r) => r.yield.p10 * r.fin.price * (1 - r.risk.priceVol) - r.cost.totalPerHa);
  const highs = results.map((r) => r.yield.p90 * r.fin.price * (1 + r.risk.priceVol) - r.cost.totalPerHa);
  const lo = Math.min(0, ...lows);
  const hi = Math.max(...highs);
  const tv = ticks(lo, hi, 5);
  const min = Math.min(lo, tv[0]);
  const max = Math.max(hi, tv[tv.length - 1]);
  const x = (v) => m.l + ((width - m.l - m.r) * (v - min)) / (max - min);
  for (const t of tv) {
    el('line', { x1: x(t), x2: x(t), y1: m.t, y2: height - m.b, class: t === 0 ? 'axis' : 'grid' }, svg);
    el('text', { x: x(t), y: height - 8, class: 'tick', 'text-anchor': 'middle', text: fmtMoney(t) }, svg);
  }
  results.forEach((r, i) => {
    const cy = m.t + rowH * (i + 0.5);
    const sel = r.crop.id === selectedId;
    const g = el('g', { class: `mr-row${sel ? ' sel' : ''}`, 'aria-label': `${r.crop.name} margin` }, svg);
    el('rect', { x: 0, y: cy - rowH / 2, width, height: rowH, class: 'row-hit' }, g);
    el('text', { x: m.l - 10, y: cy + 4, class: `row-label${sel ? ' strong' : ''}`, 'text-anchor': 'end', text: `${r.rank}. ${r.crop.name}` }, g);
    el('line', { x1: x(lows[i]), x2: x(highs[i]), y1: cy, y2: cy, class: `range${sel ? ' sel' : ''}` }, g);
    el('circle', { cx: x(r.fin.margin), cy, r: sel ? 6 : 5, class: `dot ${sel ? 's1' : 'muted'}` }, g);
    bindHover(g, (evt) => showTip(evt, `${r.crop.name} · ${r.strategy.label}`, [
      { value: fmtMoney(r.fin.margin), label: 'Expected margin /ha' },
      { value: `${fmtMoney(lows[i])} to ${fmtMoney(highs[i])}`, label: 'Bad year to good year (P10–P90 yield × price)' },
      { value: `${Math.round(r.fin.pLoss * 100)}%`, label: 'Chance of loss' },
    ]));
    g.addEventListener('click', () => onSelect(r.crop.id));
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(r.crop.id); } });
  });
}

// Waterfall: revenue minus cost groups = margin ($/ha) ----------------------
export function waterfallChart(host, r) {
  const e = r.cost.establishment;
  const o = r.cost.operating;
  const steps = [
    { label: 'Revenue', value: r.fin.revenue, kind: 'total' },
    { label: 'Establishment', value: -(e.seed + e.prep + e.planting + e.lime + e.contract) },
    { label: 'Fertiliser', value: -o.fertiliser },
    { label: 'Crop protection', value: -o.protection },
    { label: 'Machinery & contract', value: -(o.machinery + o.contract) },
    { label: 'Harvest & haulage', value: -(o.harvest + o.other) },
    { label: 'Labour', value: -o.labour },
    ...(o.irrigation ? [{ label: 'Irrigation', value: -o.irrigation }] : []),
    { label: 'Margin', value: r.fin.margin, kind: 'total' },
  ];
  const rowH = 26;
  const m = { l: 130, r: 70, t: 4, b: 22 };
  const { svg, width, height } = svgRoot(host, m.t + m.b + rowH * steps.length, `Revenue to margin waterfall for ${r.crop.name}`);
  const min = Math.min(0, r.fin.margin);
  const max = niceMax(r.fin.revenue);
  const x = (v) => m.l + ((width - m.l - m.r) * (v - min)) / (max - min);
  for (const t of ticks(min, max, 4)) {
    el('line', { x1: x(t), x2: x(t), y1: m.t, y2: height - m.b, class: t === 0 ? 'axis' : 'grid' }, svg);
    el('text', { x: x(t), y: height - 6, class: 'tick', 'text-anchor': 'middle', text: fmtMoney(t) }, svg);
  }
  let run = 0;
  steps.forEach((s, i) => {
    const cy = m.t + rowH * i;
    let a;
    let b;
    if (s.kind === 'total') { a = Math.min(0, s.value); b = Math.max(0, s.value); run = s.value; } else { a = run + s.value; b = run; run = a; }
    const cls = s.kind === 'total' ? (s.value >= 0 ? 'bar s1' : 'bar neg') : 'bar cost';
    const g = el('g', {}, svg);
    el('rect', { x: x(Math.min(a, b)), y: cy + 5, width: Math.max(1.5, Math.abs(x(b) - x(a))), height: rowH - 10, rx: 3, class: cls }, g);
    el('text', { x: m.l - 10, y: cy + rowH / 2 + 4, class: `row-label${s.kind ? ' strong' : ''}`, 'text-anchor': 'end', text: s.label }, g);
    el('text', { x: x(Math.max(a, b)) + 6, y: cy + rowH / 2 + 4, class: 'value-label', text: fmtMoney(s.value) }, g);
    el('rect', { x: 0, y: cy, width, height: rowH, fill: 'transparent' }, g);
    bindHover(g, (evt) => showTip(evt, s.label, [
      { value: `${fmtMoney(s.value)}/ha`, label: '' },
      { value: fmtMoney(s.value * (r.cost.total / r.cost.totalPerHa)), label: 'whole field' },
    ]));
  });
}

// Sensitivity heat grid: margin across price × yield scenarios --------------
export function sensitivityGrid(host, r) {
  host.replaceChildren();
  const prices = [-0.2, -0.1, 0, 0.1, 0.2];
  const yields = [['P10', r.yield.p10], ['P25', r.yield.p50 * (1 - 0.67 * r.yield.cv)], ['P50', r.yield.p50], ['P75', r.yield.p50 * (1 + 0.6 * r.yield.cv)], ['P90', r.yield.p90]];
  const table = document.createElement('table');
  table.className = 'heat';
  const cap = document.createElement('caption');
  cap.textContent = 'Margin $/ha by crop price (columns) and yield outcome (rows)';
  table.appendChild(cap);
  const head = table.insertRow();
  head.appendChild(document.createElement('th'));
  for (const p of prices) {
    const th = document.createElement('th');
    th.textContent = `${fmtMoney(r.fin.price * (1 + p))}${p === 0 ? '' : ` (${p > 0 ? '+' : '−'}${Math.abs(p * 100)}%)`}`;
    head.appendChild(th);
  }
  const scale = Math.max(200, r.fin.revenue * 0.5);
  for (const [label, y] of yields.slice().reverse()) {
    const tr = table.insertRow();
    const th = document.createElement('th');
    th.textContent = `${label} · ${fmtNum(y, y > 20 ? 0 : 1)} ${r.yield.unit}`;
    tr.appendChild(th);
    for (const p of prices) {
      const v = y * r.fin.price * (1 + p) - r.cost.totalPerHa;
      const td = tr.insertCell();
      const k = Math.min(4, Math.floor((Math.abs(v) / scale) * 5));
      td.style.background = Math.abs(v) < scale * 0.04 ? 'var(--diverge-mid)' : (v > 0 ? RAMPS.pos : RAMPS.neg)[k];
      td.style.color = k >= 3 ? '#fff' : '#0b0b0b';
      td.textContent = fmtMoney(v);
      if (label === 'P50' && p === 0) td.classList.add('base');
      td.tabIndex = 0;
      const show = (evt) => showTip(evt, `${label} yield, ${p === 0 ? 'current' : `${p > 0 ? '+' : '−'}${Math.abs(p * 100)}%`} price`, [
        { value: `${fmtMoney(v)}/ha`, label: 'Margin' },
        { value: fmtMoney(v * (r.cost.total / r.cost.totalPerHa)), label: 'Whole field' },
      ]);
      td.addEventListener('pointermove', show);
      td.addEventListener('focus', show);
      td.addEventListener('pointerleave', hideTip);
      td.addEventListener('blur', hideTip);
    }
  }
  host.appendChild(table);
}

// Nutrient bullets: value marker over an optimal band ------------------------
export function nutrientBullets(host, soil, targets) {
  host.replaceChildren();
  for (const [key, t] of Object.entries(targets)) {
    const v = soil[key];
    const status = v < t.lo ? 'Low' : v > t.hi ? 'High' : 'Optimal';
    const row = document.createElement('div');
    row.className = 'bullet';
    row.tabIndex = 0;
    const pct = (x) => `${Math.max(0, Math.min(100, ((x - t.min) / (t.max - t.min)) * 100))}%`;
    row.innerHTML = `
      <div class="bullet-head"><span class="b-label"></span><span class="b-val"></span></div>
      <div class="bullet-track"><div class="bullet-band"></div><div class="bullet-mark"></div></div>`;
    row.querySelector('.b-label').textContent = t.label;
    const val = row.querySelector('.b-val');
    val.innerHTML = `<strong></strong> <span class="status ${status.toLowerCase()}"></span>`;
    val.querySelector('strong').textContent = `${v}${t.unit ? ` ${t.unit}` : ''}`;
    val.querySelector('.status').textContent = `${status === 'Optimal' ? '✓' : status === 'Low' ? '↓' : '↑'} ${status}`;
    const bandEl = row.querySelector('.bullet-band');
    bandEl.style.left = pct(t.lo);
    bandEl.style.width = `calc(${pct(t.hi)} - ${pct(t.lo)})`;
    row.querySelector('.bullet-mark').style.left = pct(v);
    const show = (evt) => showTip(evt, t.label, [
      { value: `${v}${t.unit ? ` ${t.unit}` : ''}`, label: 'Measured' },
      { value: `${t.lo}–${t.hi}`, label: 'Target range' },
    ]);
    row.addEventListener('pointermove', show);
    row.addEventListener('focus', show);
    row.addEventListener('pointerleave', hideTip);
    row.addEventListener('blur', hideTip);
    host.appendChild(row);
  }
}

// Soil texture: sand / silt / clay stacked bar -------------------------------
export function textureBar(host, texture) {
  host.replaceChildren();
  const bar = document.createElement('div');
  bar.className = 'texture-bar';
  const parts = [['Sand', texture.sand, 'var(--series-2)'], ['Silt', texture.silt, 'var(--series-3)'], ['Clay', texture.clay, 'var(--series-1)']];
  for (const [label, v, color] of parts) {
    const seg = document.createElement('div');
    seg.className = 'seg';
    seg.style.flex = v;
    seg.style.background = color;
    seg.tabIndex = 0;
    const show = (evt) => showTip(evt, label, [{ value: `${v}%`, label: 'of mineral fraction' }]);
    seg.addEventListener('pointermove', show);
    seg.addEventListener('focus', show);
    seg.addEventListener('pointerleave', hideTip);
    bar.appendChild(seg);
  }
  const legend = document.createElement('div');
  legend.className = 'legend';
  for (const [label, v, color] of parts) {
    const item = document.createElement('span');
    item.innerHTML = '<i class="sw"></i><span></span>';
    item.querySelector('i').style.background = color;
    item.querySelector('span').textContent = `${label} ${v}%`;
    legend.appendChild(item);
  }
  host.append(bar, legend);
}

// Soil impact profile: diverging bars, positive = improves soil --------------
export function impactProfile(host, r) {
  const s = r.sustain;
  const rows = [
    { label: 'Nitrogen balance', v: Math.max(-1, Math.min(1, s.nBalance / 60)), text: `${s.nBalance >= 0 ? '+' : '−'}${Math.abs(Math.round(s.nBalance))} kg N/ha` },
    { label: 'Organic matter', v: s.om / 0.06, text: `${s.om >= 0 ? '+' : '−'}${Math.abs(s.om)} %/yr` },
    { label: 'Soil structure', v: s.structure, text: s.structure > 0.25 ? 'improves' : s.structure < -0.25 ? 'degrades' : 'neutral' },
    { label: 'Erosion protection', v: 1 - 2 * s.erosion, text: `${s.erosion < 0.3 ? 'low' : s.erosion < 0.6 ? 'moderate' : 'high'} risk` },
    { label: 'Water use', v: Math.max(-1, Math.min(1, (450 - r.crop.water) / 200)) - (r.irrMm ? 0.3 : 0), text: `${r.crop.water} mm${r.irrMm ? ` (+${Math.round(r.irrMm)} irrigated)` : ''}` },
  ];
  const rowH = 30;
  const m = { l: 130, r: 110, t: 18, b: 6 };
  const { svg, width, height } = svgRoot(host, m.t + m.b + rowH * rows.length, `Soil impact profile of ${r.crop.name}`);
  const mid = m.l + (width - m.l - m.r) / 2;
  const half = (width - m.l - m.r) / 2;
  el('text', { x: m.l, y: 11, class: 'tick', text: '◀ depletes' }, svg);
  el('text', { x: width - m.r, y: 11, class: 'tick', 'text-anchor': 'end', text: 'improves ▶' }, svg);
  el('line', { x1: mid, x2: mid, y1: m.t, y2: height - m.b, class: 'axis' }, svg);
  rows.forEach((row, i) => {
    const cy = m.t + rowH * (i + 0.5);
    const v = Math.max(-1, Math.min(1, row.v));
    const w = Math.abs(v) * half;
    const g = el('g', {}, svg);
    el('text', { x: m.l - 10, y: cy + 4, class: 'row-label', 'text-anchor': 'end', text: row.label }, g);
    el('rect', { x: v >= 0 ? mid : mid - w, y: cy - 8, width: Math.max(1.5, w), height: 16, rx: 3, class: v >= 0 ? 'bar s1' : 'bar neg' }, g);
    el('text', { x: width - m.r + 8, y: cy + 4, class: 'value-label', text: row.text }, g);
    el('rect', { x: 0, y: cy - rowH / 2, width, height: rowH, fill: 'transparent' }, g);
    bindHover(g, (evt) => showTip(evt, row.label, [{ value: row.text, label: v >= 0 ? 'improves soil' : 'depletes soil' }]));
  });
}

// Field map: zone grid clipped to the field boundary -------------------------
function zoneValue(field, x, y) {
  const s = field.zoneSeed;
  return 0.5 + 0.22 * Math.sin(x * 0.09 + s) * Math.cos(y * 0.11 - s) + 0.16 * Math.sin((x + y) * 0.05 + s * 2) + 0.07 * Math.sin(x * 0.4 + y * 0.3);
}

export function fieldMap(host, field, layer) {
  host.replaceChildren();
  const svg = el('svg', { viewBox: '0 0 100 70', class: 'map', role: 'img', 'aria-label': `${field.name} ${layer} map` }, host);
  const id = `clip-${field.id}`;
  const defs = el('defs', {}, svg);
  const clip = el('clipPath', { id }, defs);
  const pts = field.polygon.map((p) => p.join(',')).join(' ');
  el('polygon', { points: pts }, clip);
  // Satellite-like background texture.
  el('rect', { x: 0, y: 0, width: 100, height: 70, class: 'map-bg' }, svg);
  for (let i = 0; i < 9; i++) el('path', { d: `M${-10 + i * 14},70 L${10 + i * 14},0`, class: 'map-track' }, svg);
  const g = el('g', { 'clip-path': `url(#${id})` }, svg);
  const ramp = RAMPS[layer];
  const cell = 2.5;
  const values = [];
  for (let x = 0; x < 100; x += cell) {
    for (let y = 0; y < 70; y += cell) {
      let v = zoneValue(field, x, y);
      let display;
      if (layer === 'ndvi') { v = Math.max(0.2, Math.min(0.92, field.ndvi + (v - 0.5) * 0.45)); display = `NDVI ${v.toFixed(2)}`; }
      else if (layer === 'slope') { v = Math.max(0, field.terrain.slopeMean * (0.35 + 1.4 * (1 - Math.abs(y - 35) / 35) * v)); v = Math.min(v, field.terrain.slopeMax); display = `${v.toFixed(1)}% slope`; }
      else { v = Math.max(0.6, Math.min(1.35, field.productivity + (v - 0.5) * 0.6)); display = `${Math.round(v * 100)}% of field-average yield`; }
      values.push({ x, y, v, display });
    }
  }
  const vs = values.map((d) => d.v);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  for (const d of values) {
    const k = Math.min(ramp.length - 1, Math.floor(((d.v - lo) / (hi - lo + 1e-9)) * ramp.length));
    const rect = el('rect', { x: d.x, y: d.y, width: cell + 0.05, height: cell + 0.05, fill: ramp[k] }, g);
    rect.addEventListener('pointermove', (evt) => showTip(evt, field.name, [{ value: d.display, label: '' }]));
    rect.addEventListener('pointerleave', hideTip);
  }
  el('polygon', { points: pts, class: 'field-outline' }, svg);
  return { lo, hi, ramp };
}

// Yield outlook: P10–P90 band, P50, break-even and this field's past yields --
export function yieldRangeChart(host, r, history) {
  const { svg, width, height } = svgRoot(host, 120, `Yield range for ${r.crop.name}`);
  const m = { l: 16, r: 16, t: 34, b: 30 };
  const past = history.filter((h) => h.crop === r.crop.id);
  const max = niceMax(Math.max(r.yield.p90, r.yield.potential, r.fin.breakEvenYield, ...past.map((h) => h.yield)) * 1.08);
  const x = (v) => m.l + ((width - m.l - m.r) * v) / max;
  const cy = m.t + 18;
  for (const t of ticks(0, max, 5)) {
    el('line', { x1: x(t), x2: x(t), y1: m.t - 6, y2: height - m.b, class: t === 0 ? 'axis' : 'grid' }, svg);
    el('text', { x: x(t), y: height - 10, class: 'tick', 'text-anchor': 'middle', text: `${t}` }, svg);
  }
  el('text', { x: width - m.r, y: height - 10 + 0, class: 'tick', 'text-anchor': 'end', dy: '-12', text: `${r.yield.unit}/ha` }, svg);
  const band = el('rect', { x: x(r.yield.p10), y: cy - 10, width: x(r.yield.p90) - x(r.yield.p10), height: 20, rx: 4, class: 'band-strong' }, svg);
  bindHover(band, (evt) => showTip(evt, 'Yield range', [
    { value: `${fmtNum(r.yield.p10)}–${fmtNum(r.yield.p90)} ${r.yield.unit}/ha`, label: '80% of seasons fall here (P10–P90)' },
  ]));
  el('line', { x1: x(r.yield.p50), x2: x(r.yield.p50), y1: cy - 14, y2: cy + 14, class: 'marker s1' }, svg);
  el('text', { x: x(r.yield.p50), y: m.t - 12, class: 'value-label', 'text-anchor': 'middle', text: `P50 ${fmtNum(r.yield.p50)}` }, svg);
  const be = r.fin.breakEvenYield;
  el('line', { x1: x(be), x2: x(be), y1: m.t - 6, y2: height - m.b, class: 'threshold crit' }, svg);
  el('text', { x: x(be) + 4, y: height - m.b - 4, class: 'tick crit-text', text: `Break-even ${fmtNum(be)}` }, svg);
  el('path', { d: `M${x(r.yield.potential)},${cy - 16} l-5,-7 h10 z`, class: 'tri' }, svg);
  el('text', { x: x(r.yield.potential), y: m.t - 12 + 0, dy: past.length ? 0 : 0, class: 'tick', 'text-anchor': 'middle', text: x(r.yield.potential) - x(r.yield.p50) > 70 ? 'Potential' : '' }, svg);
  for (const h of past) {
    const d = el('circle', { cx: x(h.yield), cy: cy + 22, r: 5, class: 'dot hist' }, svg);
    bindHover(d, (evt) => showTip(evt, `${h.year} harvest`, [{ value: `${h.yield} ${r.yield.unit}/ha`, label: 'recorded on this field' }]));
  }
}
