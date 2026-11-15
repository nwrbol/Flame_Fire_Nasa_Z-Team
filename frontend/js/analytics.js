// MicroFlame Analytics: describes the FireGap dataset (what was tested, where the gaps are).
// No risk score, no prediction. Every number is computed here from /assets/analytics.json,
// which scripts/build_analytics.py derives from tests.csv. Loaded only on #/analytics.
const SVGNS = 'http://www.w3.org/2000/svg';
const C = { blue: '#2a78d6', orange: '#eb6834', aqua: '#1baf7a', yellow: '#eda100', grey: '#8a8984', light: '#b9b8b2' };
const FAM = {   // colour + marker shape: colour is never the only cue
  solid: { c: C.orange, shape: 'square', short: 'Solid' },
  droplet: { c: C.blue, shape: 'circle', short: 'Droplet' },
  gas: { c: C.aqua, shape: 'triangle', short: 'Gas' },
  bre: { c: C.yellow, shape: 'diamond', short: 'BRE' },
  saffire: { c: C.grey, shape: 'cross', short: 'Saffire' },
};
const KIND_FAM = { solid: 'solid', droplet: 'droplet', gas: 'gas', rig: 'bre', unknown: null };
const OUT_C = { out: C.blue, burning: C.orange, none: C.light };
const fmt = (n) => n.toLocaleString('en');
const pct = (a, b) => (b ? Math.round(a / b * 1000) / 10 : 0);

function h(tag, attrs = {}, ...kids) {
  const svg = ['svg', 'g', 'rect', 'circle', 'path', 'line', 'text', 'polygon', 'title'].includes(tag);
  const e = svg ? document.createElementNS(SVGNS, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k);
  return e;
}
function marker(shape, x, y, r, color, hollow) {
  const st = { fill: hollow ? 'none' : color, stroke: color, 'stroke-width': hollow ? 1.6 : 1 };
  if (shape === 'square') return h('rect', { x: x - r * .88, y: y - r * .88, width: r * 1.76, height: r * 1.76, ...st });
  if (shape === 'triangle') return h('polygon', { points: `${x},${y - r * 1.1} ${x + r},${y + r * .75} ${x - r},${y + r * .75}`, ...st });
  if (shape === 'diamond') return h('polygon', { points: `${x},${y - r * 1.2} ${x + r},${y} ${x},${y + r * 1.2} ${x - r},${y}`, ...st });
  if (shape === 'cross') return h('path', { d: `M${x - r},${y - r}L${x + r},${y + r}M${x + r},${y - r}L${x - r},${y + r}`, stroke: color, 'stroke-width': 2.2, fill: 'none' });
  return h('circle', { cx: x, cy: y, r, ...st });
}

export async function mountAnalytics(root, { gapsOnly = false } = {}) {
  if (!document.getElementById('anCss')) document.head.append(h('link', { rel: 'stylesheet', href: '/css/analytics.css', id: 'anCss' }));
  root.replaceChildren(h('p', { class: 'an-status', text: 'Loading the dataset…' }));
  const D = await (await fetch('/assets/analytics.json')).json();
  const F = Object.fromEntries(D.fields.map((f, i) => [f, i]));
  const famLabel = Object.fromEntries(D.families.map(f => [f.id, f.label]));
  const qLabel = D.quality.map(q => q.label);
  const R = D.records.map(r => ({
    id: r[F.id], test: r[F.test], study: D.studies[r[F.study]], family: r[F.family], material: D.materials[r[F.material]],
    o2: r[F.o2], kpa: r[F.kpa], assumed: !!r[F.kpa_assumed], flow: r[F.flow], thick: r[F.thick], outcome: r[F.outcome],
    flags: r[F.flags], gravity: D.gravities[r[F.gravity]] || '',
  }));
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const S = { study: '', family: '', material: '', o2: null, kpa: null, o2_open: false, kpa_open: false, cell: null };
  const filterObj = () => ({ study: S.study ? [S.study] : [], family: S.family ? [S.family] : [], material: S.material ? [S.material] : [],
    ...(S.o2 ? { o2: S.o2, o2_open: S.o2_open } : {}), ...(S.kpa ? { kpa: S.kpa, kpa_open: S.kpa_open } : {}) });
  const match = (r, f = filterObj()) => {   // same semantics as backend/app/analytics.py matches()
    for (const k of ['study', 'family', 'material']) if (f[k].length && !f[k].includes(r[k])) return false;
    for (const k of ['o2', 'kpa']) if (f[k]) { const v = r[k]; if (v == null) return false; const [lo, hi] = f[k]; if (v < lo || (f[k + '_open'] ? v >= hi : v > hi)) return false; }
    return true;
  };

  // ---------- layout ----------
  const tip = h('div', { class: 'an-tip', role: 'tooltip', hidden: true });
  const kpis = h('div', { class: 'an-kpis' });
  const sel = (label, key, opts) => h('label', { class: 'an-f' }, h('span', { text: label }),
    h('select', { 'data-f': key, onchange: (e) => { S[key] = e.target.value; S.cell = null; render(); } },
      h('option', { value: '', text: 'All' }), opts.map(([v, t]) => h('option', { value: v, text: t }))));
  const rng = (label, key, unit) => h('fieldset', { class: 'an-f an-rng' }, h('legend', { text: `${label}, ${unit}` }),
    h('input', { type: 'number', 'data-r': key + '0', 'aria-label': `${label} from`, placeholder: 'from', step: 'any', onchange: readRanges }),
    h('span', { 'aria-hidden': 'true', text: '–' }),
    h('input', { type: 'number', 'data-r': key + '1', 'aria-label': `${label} to`, placeholder: 'to', step: 'any', onchange: readRanges }));
  function readRanges() {
    for (const k of ['o2', 'kpa']) {
      const a = filters.querySelector(`[data-r=${k}0]`).value, b = filters.querySelector(`[data-r=${k}1]`).value;
      S[k] = a === '' && b === '' ? null : [a === '' ? -1e9 : +a, b === '' ? 1e9 : +b]; S[k + '_open'] = false;
    }
    S.cell = null; render();
  }
  const filters = h('div', { class: 'an-filters', role: 'group', 'aria-label': 'Filters' },
    sel('Investigation', 'study', D.studies.map(s => [s, s])),
    sel('Family', 'family', D.families.map(f => [f.id, f.label])),
    sel('Material', 'material', D.materials.map(m => [m, m])),
    rng('O₂', 'o2', '%'), rng('Pressure', 'kpa', 'kPa'),
    h('button', { type: 'button', class: 'chip an-reset', text: 'Reset filters', onclick: () => { Object.assign(S, { study: '', family: '', material: '', o2: null, kpa: null, cell: null }); render(); } }),
    h('a', { class: 'chip', id: 'anCsv', download: true, text: '↓ Download filtered CSV' }));
  const active = h('p', { class: 'an-active', 'aria-live': 'polite' });
  const grid = h('div', { class: 'an-grid' });
  if (gapsOnly) root.replaceChildren(grid, tip);
  else root.replaceChildren(
    h('div', { class: 'wrap' },
      h('p', { class: 'kicker', text: 'Analytics' }),
      h('h1', { class: 'an-h1', text: 'What the dataset covers — and where it stops.' }),
      h('p', { class: 'lead', text: `Every number below is counted from ${fmt(D.source.rows)} NASA PSI test records (FireGap tests.csv). This page describes the data; it does not rate fire risk or predict anything.` }),
      kpis, filters, active, grid),
    tip);

  // ---------- tooltips (hover and keyboard focus) ----------
  function showTip(e) {
    const t = e.currentTarget.getAttribute('data-tip'); if (!t) return;
    tip.textContent = t; tip.hidden = false;
    const b = e.currentTarget.getBoundingClientRect(), w = tip.offsetWidth;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, b.left + b.width / 2 - w / 2)) + 'px';
    tip.style.top = (b.top + scrollY - tip.offsetHeight - 8 < scrollY ? b.bottom + scrollY + 8 : b.top + scrollY - tip.offsetHeight - 8) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };
  addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); });
  function mark(node, tipText, onClick) {
    node.setAttribute('data-tip', tipText); node.setAttribute('tabindex', '0'); node.setAttribute('aria-label', tipText);
    node.setAttribute('role', onClick ? 'button' : 'img'); node.classList.add('an-mark');
    node.addEventListener('mouseenter', showTip); node.addEventListener('mouseleave', hideTip);
    node.addEventListener('focus', showTip); node.addEventListener('blur', hideTip);
    if (onClick) { node.addEventListener('click', onClick); node.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }); }
    return node;
  }

  // ---------- card scaffold: title = finding, chart, notes, "View as table" ----------
  function card(id, title, svg, notes, table, total, wide) {
    const tbl = h('div', { class: 'an-table', hidden: true }, table);
    const btn = h('button', { type: 'button', class: 'chip an-tt', 'aria-pressed': 'false', 'aria-controls': id + 'T', text: 'View as table',
      onclick: () => { const on = tbl.hidden; tbl.hidden = !on; svg.style.display = on ? 'none' : ''; btn.setAttribute('aria-pressed', on); btn.textContent = on ? 'View as chart' : 'View as table'; } });
    tbl.id = id + 'T';
    return h('figure', { class: 'an-card' + (wide ? ' wide' : ''), id, 'data-total': total },
      h('figcaption', {}, h('h2', { text: title })), svg, notes && h('p', { class: 'an-note', text: notes }), h('div', { class: 'an-tools' }, btn), tbl);
  }
  const table = (head, rows) => h('table', {}, h('thead', {}, h('tr', {}, head.map(t => h('th', { scope: 'col', text: t })))),
    h('tbody', {}, rows.map(r => h('tr', {}, r.map((c, i) => h(i ? 'td' : 'th', i ? { text: c } : { scope: 'row', text: c }))))));
  const svgBox = (w, hgt, label) => h('svg', { viewBox: `0 0 ${w} ${hgt}`, role: 'group', 'aria-label': label, class: 'an-svg' });

  // horizontal bars: items [{key,label,n,color,tip,tag}], click toggles a filter
  function hbars(items, { label, total, onClick, isOn, maxLabel = 210, unit = '' }) {
    const rowH = 26, W = 640, x0 = maxLabel, x1 = W - 70, hgt = items.length * rowH + 10;
    const max = Math.max(1, ...items.map(i => i.n)), svg = svgBox(W, hgt, label);
    items.forEach((it, k) => {
      const y = 6 + k * rowH, w = (x1 - x0) * it.n / max;
      svg.append(h('text', { x: x0 - 8, y: y + 15, 'text-anchor': 'end', class: 'an-lbl' + (isOn && isOn(it) ? ' on' : ''), text: it.label.length > 34 ? it.label.slice(0, 33) + '…' : it.label }));
      const g = h('g', {}, h('rect', { x: x0, y: y + 3, width: Math.max(it.n ? 2 : 0, w), height: rowH - 9, rx: 2, fill: it.color || C.blue, class: 'an-bar' }),
        h('text', { x: x0 + Math.max(2, w) + 6, y: y + 15, class: 'an-val', text: (unit === '%' ? `${it.n}%` : fmt(it.n)) + (it.tag ? ` · ${it.tag}` : '') }));
      svg.append(mark(g, it.tip, onClick ? () => onClick(it) : null));
    });
    return svg;
  }

  // ---------- charts ----------
  function coverageMap(rows) {
    const W = 640, H = 380, m = { l: 52, r: 24, t: 16, b: 44 }, X0 = 10, X1 = 45, Y0 = 0, Y1 = 350;
    const sx = v => m.l + (v - X0) / (X1 - X0) * (W - m.l - m.r), sy = v => H - m.b - (v - Y0) / (Y1 - Y0) * (H - m.t - m.b);
    const svg = svgBox(W, H, 'Coverage map: oxygen versus pressure, markers by family');
    for (let v = 10; v <= 45; v += 5) svg.append(h('line', { x1: sx(v), x2: sx(v), y1: m.t, y2: H - m.b, class: 'an-gridline' }), h('text', { x: sx(v), y: H - m.b + 16, 'text-anchor': 'middle', class: 'an-ax', text: v }));
    for (let v = 0; v <= 350; v += 50) svg.append(h('line', { x1: m.l, x2: W - m.r, y1: sy(v), y2: sy(v), class: 'an-gridline' }), h('text', { x: m.l - 8, y: sy(v) + 4, 'text-anchor': 'end', class: 'an-ax', text: v }));
    svg.append(h('text', { x: (m.l + W - m.r) / 2, y: H - 6, 'text-anchor': 'middle', class: 'an-axt', text: 'Oxygen, % (initial)' }),
      h('text', { transform: `translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)`, 'text-anchor': 'middle', class: 'an-axt', text: 'Pressure, kPa' }));
    const groups = new Map(); let unplotted = 0;
    for (const r of rows) {
      if (r.o2 == null || r.kpa == null) { unplotted++; continue; }
      const k = `${r.family}|${Math.round(r.o2 * 2) / 2}|${Math.round(r.kpa / 5) * 5}|${r.assumed}`;
      const g = groups.get(k) || { fam: r.family, o2: Math.round(r.o2 * 2) / 2, kpa: Math.round(r.kpa / 5) * 5, assumed: r.assumed, n: 0 }; g.n++; groups.set(k, g);
    }
    const plotted = rows.length - unplotted;
    [...groups.values()].sort((a, b) => b.n - a.n).forEach(g => {
      const f = FAM[g.fam] || FAM.saffire, r = 3 + Math.sqrt(g.n) * 1.3;
      svg.append(mark(h('g', { class: 'an-pt' }, marker(f.shape, sx(g.o2), sy(g.kpa), r, f.c, g.assumed)),
        `${famLabel[g.fam]}: ${g.n} test${g.n > 1 ? 's' : ''} at ${g.o2}% O₂, ${g.kpa} kPa${g.assumed ? ' (pressure assumed)' : ''}`));
    });
    for (const ref of D.references) {
      if (ref.o2 > X1) {   // Apollo: 100% O2 is off the scale -> arrow at the right edge
        const y = sy(ref.kpa); svg.append(mark(h('g', {}, h('path', { d: `M${W - m.r - 92},${y}H${W - m.r - 4}M${W - m.r - 10},${y - 5}L${W - m.r - 3},${y}L${W - m.r - 10},${y + 5}`, class: 'an-ref' }),
          h('text', { x: W - m.r - 4, y: y - 8, 'text-anchor': 'end', class: 'an-reft', text: `${ref.label} ${ref.o2}% O₂ off the scale` })),
          `${ref.label}: ${ref.o2}% O₂ at ${ref.kpa} kPa (${ref.note}); fact ${ref.fact}`));
        continue;
      }
      const x = sx(ref.o2), y = sy(ref.kpa);
      svg.append(mark(h('g', {}, h('path', { d: `M${x - 7},${y}H${x + 7}M${x},${y - 7}V${y + 7}`, class: 'an-ref' }),
        h('text', { x: x + 9, y: y - 7, class: 'an-reft', text: `${ref.label} ${ref.o2}% / ${ref.kpa} kPa` })), `${ref.label}: ${ref.o2}% O₂, ${ref.kpa} kPa (fact ${ref.fact})`));
    }
    const fams = D.families.map(f => [f.id, rows.filter(r => r.family === f.id && r.o2 != null && r.kpa != null).length]);
    const legend = h('div', { class: 'an-legend' }, fams.map(([id, n]) => h('span', {},
      h('svg', { viewBox: '0 0 16 16', width: 14, height: 14, 'aria-hidden': 'true' }, marker(FAM[id].shape, 8, 8, 5, FAM[id].c, false)), ` ${FAM[id].short} · ${fmt(n)}`)),
      h('span', {}, h('svg', { viewBox: '0 0 16 16', width: 14, height: 14, 'aria-hidden': 'true' }, marker('circle', 8, 8, 5, C.grey, true)), ' hollow = pressure assumed'));
    const NAME = { solid: 'solid samples', droplet: 'droplets', gas: 'gas flames', bre: 'the burner emulator', saffire: 'Saffire' };
    const placed = rows.filter(r => r.kpa != null && r.o2 != null);
    const below = [...new Set(placed.filter(r => r.kpa < 70).map(r => NAME[r.family]))];
    const sol = placed.filter(r => r.family === 'solid').map(r => r.kpa);
    const solTxt = sol.length ? `; solid samples only at ${Math.min(...sol)}–${Math.max(...sol)} kPa` : '';
    const title = plotted ? `Below 70 kPa: ${below.length ? 'only ' + below.join(' and ') : 'no tests'}${solTxt}` : 'No record in this selection states both O₂ and pressure';
    const fig = card('anMap', title, svg, `${fmt(plotted)} records plotted; ${fmt(unplotted)} not plotted because O₂ or pressure is not recorded. Marker size = number of tests.`,
      table(['Family', 'O₂, %', 'Pressure, kPa', 'Pressure assumed', 'Tests'], [...groups.values()].map(g => [famLabel[g.fam], g.o2, g.kpa, g.assumed ? 'yes' : 'no', g.n])), rows.length, true);
    fig.insertBefore(legend, svg);
    return fig;
  }

  function coverageGrid(rows) {
    const O = [10, 45, 5], P = [40, 340, 20], cols = (O[1] - O[0]) / O[2], rws = (P[1] - P[0]) / P[2];
    const W = 640, m = { l: 64, t: 10, b: 40, r: 10 }, cw = (W - m.l - m.r) / cols, ch = 22, H = m.t + rws * ch + m.b;
    const svg = svgBox(W, H, 'Coverage grid: number of tests per oxygen and pressure cell; empty cells have no tests');
    const cnt = Array.from({ length: rws }, () => Array(cols).fill(0)); let outside = 0;
    for (const r of rows) {
      if (r.o2 == null || r.kpa == null) { outside++; continue; }
      const i = Math.floor((r.o2 - O[0]) / O[2]), j = Math.floor((r.kpa - P[0]) / P[2]);
      if (i < 0 || i >= cols || j < 0 || j >= rws) { outside++; continue; }
      cnt[j][i]++;
    }
    const max = Math.max(1, ...cnt.flat()); let empty = 0;
    for (let j = 0; j < rws; j++) for (let i = 0; i < cols; i++) {
      const n = cnt[j][i], x = m.l + i * cw, y = m.t + (rws - 1 - j) * ch, o = [O[0] + i * O[2], O[0] + (i + 1) * O[2]], p = [P[0] + j * P[2], P[0] + (j + 1) * P[2]];
      if (!n) empty++;
      const on = S.cell && S.cell.i === i && S.cell.j === j;
      const g = h('g', { class: 'an-cell' + (n ? '' : ' empty') + (on ? ' on' : ''), 'data-n': n },
        h('rect', { x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 2, fill: n ? C.blue : 'none', 'fill-opacity': n ? .18 + .72 * Math.sqrt(n / max) : 0 }),
        h('text', { x: x + cw / 2, y: y + ch / 2 + 4, 'text-anchor': 'middle', class: n ? 'an-cv' : 'an-ce', text: n ? fmt(n) : 'no tests' }));
      svg.append(mark(g, `${o[0]}–${o[1]}% O₂, ${p[0]}–${p[1]} kPa: ${n ? fmt(n) + ' tests' : 'no tests (gap)'}`, () => { S.cell = on ? null : { i, j, o, p }; render(); }));
    }
    for (let i = 0; i <= cols; i++) svg.append(h('text', { x: m.l + i * cw, y: H - m.b + 16, 'text-anchor': 'middle', class: 'an-ax', text: O[0] + i * O[2] }));
    for (let j = 0; j <= rws; j += 2) svg.append(h('text', { x: m.l - 8, y: m.t + (rws - j) * ch + 4, 'text-anchor': 'end', class: 'an-ax', text: P[0] + j * P[2] }));
    svg.append(h('text', { x: (m.l + W - m.r) / 2, y: H - 6, 'text-anchor': 'middle', class: 'an-axt', text: 'Oxygen, % (5-point cells)' }),
      h('text', { transform: `translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)`, 'text-anchor': 'middle', class: 'an-axt', text: 'Pressure, kPa (20 kPa cells)' }));
    const placed = rows.length - outside;
    const fig = card('anGrid', `${empty} of ${cols * rws} O₂ × pressure cells have no tests at all`, svg,
      `Click a cell to list its records. ${fmt(placed)} records placed; ${fmt(outside)} not placed (O₂ or pressure not recorded, or outside the grid).`,
      table(['Pressure, kPa', ...Array.from({ length: cols }, (_, i) => `${O[0] + i * O[2]}–${O[0] + (i + 1) * O[2]}% O₂`)],
        cnt.map((row, j) => [`${P[0] + j * P[2]}–${P[0] + (j + 1) * P[2]}`, ...row.map(n => n ? String(n) : 'no tests')]).reverse()), rows.length, true);
    if (S.cell) fig.append(cellPanel(S.cell));
    return fig;
  }
  function cellPanel(c) {
    const f = { ...filterObj(), o2: c.o, o2_open: true, kpa: c.p, kpa_open: true }, list = R.filter(r => match(r, f));
    const sim = h('button', { type: 'button', class: 'chip', text: `Open in simulator (${(c.o[0] + c.o[1]) / 2}% O₂, ${(c.p[0] + c.p[1]) / 2} kPa)`, onclick: () => openSim((c.o[0] + c.o[1]) / 2, (c.p[0] + c.p[1]) / 2) });
    const dl = h('a', { class: 'chip', download: true, href: '/api/export?format=csv&analytics=' + encodeURIComponent(JSON.stringify(f)), text: '↓ CSV of this cell' });
    return h('div', { class: 'an-cellpanel', 'aria-live': 'polite' },
      h('h3', { text: `${c.o[0]}–${c.o[1]}% O₂ · ${c.p[0]}–${c.p[1]} kPa: ${list.length ? fmt(list.length) + ' records' : 'no tests'}` }),
      h('div', { class: 'an-tools' }, sim, dl),
      list.length ? h('div', { class: 'an-table' }, table(['Test', 'Investigation', 'Material', 'O₂, %', 'kPa', 'Outcome'],
        list.slice(0, 60).map(r => [r.test || '—', r.study, r.material, r.o2 ?? 'not recorded', r.kpa == null ? 'not recorded' : r.kpa + (r.assumed ? ' (assumed)' : ''), D.outcomes.find(o => o.id === r.outcome).label]))) :
        h('p', { class: 'an-note', text: 'This is a gap: NASA has no test in this cell for the current filters.' }),
      list.length > 60 ? h('p', { class: 'an-note', text: `Showing 60 of ${fmt(list.length)}; download the CSV for all.` }) : null);
  }
  function openSim(o2, kpa) {
    location.hash = '#sim';
    requestAnimationFrame(() => setTimeout(() => {
      for (const [id, v] of [['o2', o2], ['kpa', kpa]]) { const el = document.getElementById(id); if (el) { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); } }
    }, 50));
  }

  function byStudy(rows) {
    const items = D.studies.map(s => ({ key: s, label: s, n: rows.filter(r => r.study === s).length })).sort((a, b) => b.n - a.n);
    items.forEach(i => { const f = R.find(r => r.study === i.key).family; i.color = FAM[f].c; i.tag = FAM[f].short.toLowerCase(); i.tip = `${i.label}: ${fmt(i.n)} records (${famLabel[f]}). Click to filter.`; });
    const top = items[0];
    return card('anStudy', rows.length ? `${top.label} holds ${pct(top.n, rows.length)}% of the selected records` : 'No records in this selection',
      hbars(items, { label: 'Records by investigation', onClick: (i) => { S.study = S.study === i.key ? '' : i.key; render(); }, isOn: (i) => S.study === i.key, maxLabel: 150 }), null,
      table(['Investigation', 'Records'], items.map(i => [i.label, fmt(i.n)])), items.reduce((a, i) => a + i.n, 0));
  }
  function materials(rows) {
    const items = D.materials.map(mn => ({ key: mn, label: mn, n: rows.filter(r => r.material === mn).length })).sort((a, b) => b.n - a.n);
    items.forEach(i => { const k = D.material_kind[i.key], f = KIND_FAM[k]; i.color = f ? FAM[f].c : C.light; i.tag = f ? FAM[f].short.toLowerCase() : 'unknown';
      i.tip = `${i.label}: ${fmt(i.n)} records (${i.tag}). Click to filter.`; });
    const ns = rows.filter(r => r.material === 'Material not stated').length;
    return card('anMat', `${items.filter(i => i.n).length} material families; ${fmt(ns)} records do not state the material`,
      hbars(items, { label: 'Records by material family', onClick: (i) => { S.material = S.material === i.key ? '' : i.key; render(); }, isOn: (i) => S.material === i.key, maxLabel: 250 }), null,
      table(['Material', 'Kind', 'Records'], items.map(i => [i.label, i.tag, fmt(i.n)])), items.reduce((a, i) => a + i.n, 0));
  }
  function airflow(rows) {
    const W = 640, H = 250, m = { l: 48, r: 16, t: 14, b: 44 }, bins = []; for (let a = 0; a < 40; a += 5) bins.push([a, a + 5]);
    const nr = rows.filter(r => r.flow == null).length, counts = bins.map(([a, b]) => rows.filter(r => r.flow != null && r.flow >= a && r.flow < b).length);
    const over = rows.filter(r => r.flow != null && r.flow >= 40).length;
    const all = [...counts, over, nr], labels = [...bins.map(([a, b]) => `${a}–${b}`), '≥40', 'not recorded'];
    const max = Math.max(1, ...all), bw = (W - m.l - m.r) / (all.length + .6), svg = svgBox(W, H, 'Airflow distribution, with a separate not-recorded bar');
    const sx = (k) => m.l + (k + (k >= all.length - 1 ? .6 : 0)) * bw, sy = (v) => H - m.b - v / max * (H - m.t - m.b);
    const v = D.ventilation, vx0 = m.l + v.lo / 5 * bw, vx1 = m.l + v.hi / 5 * bw;
    svg.append(h('rect', { x: vx0, y: m.t, width: vx1 - vx0, height: H - m.t - m.b, class: 'an-band' }),
      h('text', { x: (vx0 + vx1) / 2, y: m.t + 12, 'text-anchor': 'middle', class: 'an-reft', text: `${v.label} ${v.lo}–${v.hi} cm/s` }));
    all.forEach((n, k) => {
      const x = sx(k), y = sy(n), isNr = k === all.length - 1;
      svg.append(mark(h('g', {}, h('rect', { x: x + 3, y, width: bw - 6, height: H - m.b - y, fill: isNr ? C.light : C.blue, class: 'an-bar' + (isNr ? ' nr' : '') }),
        h('text', { x: x + bw / 2, y: y - 5, 'text-anchor': 'middle', class: 'an-val', text: fmt(n) })),
        `Airflow ${labels[k]}${isNr ? '' : ' cm/s'}: ${fmt(n)} records`));
      svg.append(h('text', { x: x + bw / 2, y: H - m.b + 16, 'text-anchor': 'middle', class: 'an-ax', text: labels[k] }));
    });
    svg.append(h('text', { x: (m.l + W - m.r) / 2, y: H - 6, 'text-anchor': 'middle', class: 'an-axt', text: 'Airflow, cm/s' }),
      h('text', { transform: `translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)`, 'text-anchor': 'middle', class: 'an-axt', text: 'Records' }));
    const rec = rows.length - nr;
    return card('anFlow', `Airflow is recorded for only ${fmt(rec)} of ${fmt(rows.length)} records`, svg,
      `Shaded band: spacecraft ventilation range from fact ${v.fact}. Most tables give fan dial settings, not cm/s.`,
      table(['Airflow, cm/s', 'Records'], labels.map((l, k) => [l, fmt(all[k])])), all.reduce((a, b) => a + b, 0));
  }
  function outcomes(rows) {
    const W = 640, rowH = 34, x0 = 120, x1 = W - 20, fams = D.families.filter(f => rows.some(r => r.family === f.id));
    const H = fams.length * rowH + 50, svg = svgBox(W, H, 'Outcomes by family, stacked: went out, kept burning, not recorded'); let total = 0;
    fams.forEach((f, k) => {
      const fr = rows.filter(r => r.family === f.id), y = 8 + k * rowH; let x = x0;
      svg.append(h('text', { x: x0 - 8, y: y + 17, 'text-anchor': 'end', class: 'an-lbl', text: FAM[f.id].short }));
      for (const o of D.outcomes) {
        const n = fr.filter(r => r.outcome === o.id).length, w = (x1 - x0) * n / fr.length; total += n;
        if (!n) continue;
        svg.append(mark(h('g', {}, h('rect', { x, y: y + 4, width: w, height: rowH - 12, fill: OUT_C[o.id], class: 'an-bar' + (o.id === 'none' ? ' nr' : '') }),
          w > 34 ? h('text', { x: x + w / 2, y: y + 19, 'text-anchor': 'middle', class: 'an-in', text: fmt(n) }) : null),
          `${f.label} — ${o.label}: ${fmt(n)} of ${fmt(fr.length)} (${pct(n, fr.length)}%)`));
        x += w;
      }
    });
    const ly = H - 22; let lx = x0;
    for (const o of D.outcomes) { svg.append(h('rect', { x: lx, y: ly, width: 12, height: 12, fill: OUT_C[o.id], class: o.id === 'none' ? 'nr' : '' }), h('text', { x: lx + 17, y: ly + 11, class: 'an-ax', text: o.label })); lx += 150; }
    const withOut = D.families.filter(f => rows.some(r => r.family === f.id && r.outcome !== 'none')).map(f => FAM[f.id].short.toLowerCase());
    const n = rows.filter(r => r.outcome !== 'none').length;
    return card('anOut', `An outcome is recorded for ${pct(n, rows.length)}% of records`, svg,
      `Structured outcomes exist only for ${withOut.join(', ') || 'none of the selected families'} (gas flames and the burner emulator from ACME tables; Saffire from report text). Solid and droplet tables have no outcome column.`,
      table(['Family', ...D.outcomes.map(o => o.label)], fams.map(f => [f.label, ...D.outcomes.map(o => fmt(rows.filter(r => r.family === f.id && r.outcome === o.id).length))])), total);
  }
  function quality(rows) {
    const anyN = rows.filter(r => r.flags).length;
    const items = [{ key: 'any', label: 'Any data-quality note', n: pct(anyN, rows.length), cnt: anyN, color: C.yellow },
      { key: 'none', label: 'No note', n: pct(rows.length - anyN, rows.length), cnt: rows.length - anyN, color: C.light },
      ...qLabel.map((l, i) => ({ key: i, label: l, cnt: rows.filter(r => r.flags & (1 << i)).length })).map(it => ({ ...it, n: pct(it.cnt, rows.length), color: C.grey })).sort((a, b) => b.cnt - a.cnt)];
    items.forEach(i => { i.tip = `${i.label}: ${fmt(i.cnt)} of ${fmt(rows.length)} records (${i.n}%)`; });
    return card('anQ', `${pct(anyN, rows.length)}% of records carry at least one data-quality note`,
      hbars(items, { label: 'Share of records by data-quality category', unit: '%', maxLabel: 290 }),
      'Categories are read from the wording of data_quality_note; a record can be in several, so categories do not add up to 100%.',
      table(['Category', 'Records', 'Share'], items.map(i => [i.label, fmt(i.cnt), i.n + '%'])), anyN + (rows.length - anyN));
  }
  function gravity(rows) {
    const micro = rows.filter(r => r.gravity === 'microgravity').length, unk = rows.filter(r => !r.gravity).length;
    const lunar = rows.filter(r => r.gravity === 'lunar').length, mars = rows.filter(r => r.gravity === 'martian').length;
    const other = rows.length - micro - unk - lunar - mars;
    const items = [{ label: 'Microgravity', n: micro, color: C.blue }, { label: 'Lunar gravity', n: lunar, tag: lunar ? '' : 'no direct measurements', color: C.orange },
      { label: 'Martian gravity', n: mars, tag: mars ? '' : 'no direct measurements', color: C.orange }, { label: 'Not stated', n: unk, color: C.light }];
    if (other) items.push({ label: 'Other', n: other, color: C.grey });
    items.forEach(i => { i.tip = `${i.label}: ${fmt(i.n)} records${i.tag ? ' — ' + i.tag : ''}`; });
    return card('anG', lunar + mars ? `${fmt(lunar + mars)} records at partial gravity` : `All ${fmt(micro)} records are microgravity; none at lunar or Martian gravity`,
      hbars(items, { label: 'Records by gravity regime', maxLabel: 150 }), 'From the gravity_regime column (else the study platform: ISS or free-flying Cygnus = microgravity).',
      table(['Gravity regime', 'Records'], items.map(i => [i.label, fmt(i.n) + (i.tag ? ` (${i.tag})` : '')])), items.reduce((a, i) => a + i.n, 0));
  }

  function kpiTiles(rows) {
    const n = rows.length, both = rows.filter(r => r.o2 != null && r.kpa != null).length, out = rows.filter(r => r.outcome !== 'none').length;
    const fl = rows.filter(r => r.flags).length, part = rows.filter(r => ['lunar', 'martian', 'partial'].includes(r.gravity)).length;
    const studies = new Set(rows.map(r => r.study)).size;
    const tile = (id, v, l, sub) => h('div', { class: 'an-kpi', id }, h('b', { class: 'mono', text: v }), h('span', { text: l }), sub ? h('small', { text: sub }) : null);
    kpis.replaceChildren(
      tile('kRec', fmt(n), 'test records', n === R.length ? 'all records' : `of ${fmt(R.length)}`),
      tile('kStu', fmt(studies), 'investigations', `${D.totals.studies_in_catalogue} in studies.json`),
      tile('kBoth', fmt(both), 'with O₂ and pressure known', `${pct(both, n)}%`),
      tile('kOut', pct(out, n) + '%', 'with a recorded outcome', `${fmt(out)} records`),
      tile('kFlag', pct(fl, n) + '%', 'with data-quality flags', `${fmt(fl)} records`),
      tile('kPart', fmt(part), 'at lunar or Martian gravity', 'no direct measurements'));
  }

  function render() {
    const f = filterObj(), rows = R.filter(r => match(r, f));
    if (gapsOnly) { root.dataset.filtered = rows.length; grid.replaceChildren(coverageMap(rows), coverageGrid(rows)); hideTip(); return; }
    for (const k of ['study', 'family', 'material']) filters.querySelector(`[data-f=${k}]`).value = S[k];
    for (const k of ['o2', 'kpa']) { const [a, b] = filters.querySelectorAll(`[data-r^=${k}]`); if (!S[k]) { a.value = ''; b.value = ''; } }
    filters.querySelector('#anCsv').href = '/api/export?format=csv&analytics=' + encodeURIComponent(JSON.stringify(f));
    const parts = [S.study, S.family && famLabel[S.family], S.material, S.o2 && `O₂ ${S.o2[0] < -1e8 ? '…' : S.o2[0]}–${S.o2[1] > 1e8 ? '…' : S.o2[1]}%`, S.kpa && `${S.kpa[0] < -1e8 ? '…' : S.kpa[0]}–${S.kpa[1] > 1e8 ? '…' : S.kpa[1]} kPa`].filter(Boolean);
    active.textContent = parts.length ? `Filtered: ${parts.join(' · ')} — ${fmt(rows.length)} of ${fmt(R.length)} records. An O₂ or pressure range excludes records without that value.` : `All ${fmt(R.length)} records.`;
    root.dataset.filtered = rows.length;
    kpiTiles(rows);
    grid.replaceChildren(coverageMap(rows), coverageGrid(rows), byStudy(rows), materials(rows), airflow(rows), outcomes(rows), quality(rows), gravity(rows));
    hideTip();
  }
  if (reduce) root.classList.add('an-reduce');
  render();
  return { data: D, records: R, state: S, render, match };
}
