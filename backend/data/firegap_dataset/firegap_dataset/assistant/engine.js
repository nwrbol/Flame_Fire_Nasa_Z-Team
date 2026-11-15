// FireGap assessment engine. Pure function over the dataset: no model, no invented numbers.
const CLOSE = { dO2: 2, pRatio: 1.10 };   // "same conditions": +-2 pp O2, +-10 % pressure
const NEAR  = { dO2: 5, pRatio: 1.25 };   // "nearby": +-5 pp O2, +-25 % pressure
const FAMILY_LABEL = {
  solid: "Твёрдые материалы (BASS, BASS-II)",
  droplet: "Капли жидкого топлива (FLEX)",
  gas: "Газовые пламёна (ACME CFI-G, Flame Design)",
  burner: "Горелка, имитирующая твёрдое топливо (ACME BRE)",
};
const OUTCOME_TEXT = { ext: "погасло само", sust: "горело, пока не остановили подачу топлива или время", none: "не загорелось" };

function pr(p, t) { return Math.abs(Math.log(p / t)); }
function inBox(r, o2, p, box) { return Math.abs(r.o2 - o2) <= box.dO2 && pr(p, r.p) <= Math.log(box.pRatio); }
function dist(r, o2, p) { return Math.hypot((r.o2 - o2) / 2, Math.log(p / r.p) / Math.log(1.10)); }
const fmt = (x, d = 1) => (Math.round(x * 10 ** d) / 10 ** d).toString().replace(".", ",");

function describe(r) {
  const bits = [];
  bits.push(`${fmt(r.o2)}% O₂, ${fmt(r.p, 0)} кПа${r.pa ? " (давление принято ≈1 атм, в таблице его нет)" : ""}`);
  if (r.fam === "burner") {
    bits.push(`горелка ${r.burner} мм, ${r.fuel === "CH4" ? "метан" : "этилен"}, поток топлива ${fmt(r.flux, 2)} г/м²·с`);
  } else if (r.fam === "gas") {
    bits.push(`топливо: ${r.mat}`);
  } else {
    bits.push(r.mat);
  }
  if (r.oc) bits.push(OUTCOME_TEXT[r.oc]);
  else if (r.fam === "droplet" && r.burn != null) bits.push(`горела ${fmt(r.burn)} с${r.ext != null ? `, погасла при диаметре капли ${fmt(r.ext, 2)} мм` : ""}`);
  else if (r.obs) bits.push(`запись оператора: «${r.obs}»`);
  else bits.push("исход в таблице не указан");
  return bits.join("; ");
}

function assess(data, o2, p) {
  const out = { o2, p, families: [], verdict: null, notes: [] };
  for (const fam of Object.keys(FAMILY_LABEL)) {
    const rows = data.tests.filter(r => r.fam === fam);
    const close = rows.filter(r => inBox(r, o2, p, CLOSE));
    const near = rows.filter(r => inBox(r, o2, p, NEAR) && !inBox(r, o2, p, CLOSE));
    const level = close.length >= 3 ? "data" : close.length > 0 ? "few" : near.length > 0 ? "near" : "none";
    const pool = close.length ? close : near;
    const examples = [...pool].sort((a, b) => dist(a, o2, p) - dist(b, o2, p)).slice(0, 3);
    const nearest = rows.length ? [...rows].sort((a, b) => dist(a, o2, p) - dist(b, o2, p))[0] : null;
    const counts = { ext: 0, sust: 0, none: 0 };
    let classified = 0;
    for (const r of close) if (r.oc) { counts[r.oc]++; classified++; }
    out.families.push({ fam, label: FAMILY_LABEL[fam], total: rows.length, nClose: close.length, nNear: near.length,
      level, counts, classified, examples, nearest, nearestDist: nearest ? { dO2: nearest.o2 - o2, pRatio: nearest.p / p } : null,
      rangeO2: rows.length ? [Math.min(...rows.map(r => r.o2)), Math.max(...rows.map(r => r.o2))] : null,
      rangeP: rows.length ? [Math.min(...rows.map(r => r.p)), Math.max(...rows.map(r => r.p))] : null });
  }
  const anyClose = out.families.some(f => f.nClose > 0);
  const solid = out.families.find(f => f.fam === "solid");
  out.verdict = !anyClose ? "none" : solid.nClose > 0 ? "solid" : "indirect";
  return out;
}
if (typeof module !== "undefined") module.exports = { assess, describe, FAMILY_LABEL, OUTCOME_TEXT, CLOSE, NEAR, fmt };
