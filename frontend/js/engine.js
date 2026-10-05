// Recommendation engine: scores every crop × management strategy against the
// field's soil, terrain and climate, applies the consultant's constraints, and
// explains the result. Pure functions only — the UI owns state.

import { CROPS, CROP_BY_ID, MACHINES, INPUT_PRICES } from './data/crops.js';
import { OUTLOOK } from './data/fields.js';

export const PLANNING_DATE = new Date('2026-09-26');
const LATEST_AUTUMN_SOWING = {
  wheat: { date: new Date('2026-11-10'), label: '10 Nov' },
  canola: { date: new Date('2026-09-10'), label: '10 Sep' },
};
const SOIL_P_TARGET = 20;
const SOIL_K_TARGET = 150;
const SCLEROTINIA_HOSTS = ['canola', 'sunflower', 'soybean', 'peas'];

export const STRATEGIES = {
  standard: { id: 'standard', label: 'Standard inputs', seed: 1, fert: 1, prot: 1, yield: 1, cv: 1, sust: 0,
    desc: 'Full seed rate, fertiliser to replace crop demand, calendar-based crop protection.' },
  lowinput: { id: 'lowinput', label: 'Low-input', seed: 0.85, fert: 0.6, prot: 0.7, yield: 0.84, cv: 1.12, sust: 8,
    desc: '15% lower seed rate, N at 60% of demand guided by soil tests, threshold-based spraying only.' },
  irrigated: { id: 'irrigated', label: 'Irrigated', seed: 1, fert: 1.05, prot: 1, yield: 1, cv: 1, sust: 0, irrigate: true,
    desc: 'Standard inputs plus irrigation scheduled to cover the seasonal water deficit.' },
};

export const RISK_LEVELS = ['low', 'medium', 'high'];
const MAX_LOSS_PROB = { low: 0.25, medium: 0.45, high: 1 };

export function defaultConstraints(field) {
  return {
    budgetPerHa: 1600,
    fertBudgetPerHa: 320,
    labourHours: Math.round(field.area * 9),
    labourRate: 25,
    machines: ['tractor', 'drill', 'planter', 'sprayer', 'combine'],
    allowContracting: true,
    irrigation: 'none',
    targetMargin: 250,
    risk: 'medium',
    window: 'any',
    sustainability: 'balanced',
    horizon: 3,
    excluded: [],
    preferred: [],
  };
}

const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const round = (v, d = 0) => Math.round(v * 10 ** d) / 10 ** d;
const sum = (obj) => Object.values(obj).reduce((a, b) => a + b, 0);

// Standard normal CDF (Abramowitz–Stegun 7.1.26).
function normCdf(z) {
  const t = 1 / (1 + 0.3275911 * Math.abs(z) / Math.SQRT2);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-(z * z) / 2);
  return z >= 0 ? (1 + y) / 2 : (1 - y) / 2;
}

function phScore(ph, [min, lo, hi, max]) {
  if (ph >= lo && ph <= hi) return 1;
  if (ph < lo) return ph <= min ? 0.25 : 0.5 + (0.5 * (ph - min)) / (lo - min);
  return ph >= max ? 0.25 : 0.5 + (0.5 * (max - ph)) / (max - hi);
}

function seasonClimate(field, crop) {
  const { rain, tavg, tmin } = field.climate;
  let seasonRain = 0;
  let gdd = 0;
  let minT = Infinity;
  for (const m of crop.months) {
    seasonRain += rain[m] * (1 + OUTLOOK.rainPct / 100);
    gdd += Math.max(0, tavg[m] + OUTLOOK.tempDelta - crop.base) * 30.4;
    minT = Math.min(minT, tmin[m]);
  }
  return { seasonRain, gdd, minT };
}

function rotationEffect(prevId, crop) {
  const prev = CROP_BY_ID[prevId];
  const notes = [];
  let mult = 1;
  let credit = 0;
  if (!prev) return { mult, credit, notes: ['No previous crop recorded'], score: 0.8 };
  if (prev.id === crop.id) {
    mult *= 0.8;
    notes.push(`Second ${crop.name.toLowerCase()} in a row: disease and pest carry-over`);
  } else if (prev.family === crop.family) {
    mult *= 0.93;
    notes.push(`Same plant family as the previous ${prev.name.toLowerCase()}: shared diseases`);
  }
  if (prev.family === 'legume' && crop.family !== 'legume') {
    credit = prev.id === 'lucerne' ? 80 : 35;
    mult *= 1.04;
    notes.push(`${prev.name} leaves ~${credit} kg N/ha for this crop`);
  }
  if (prev.id !== crop.id && SCLEROTINIA_HOSTS.includes(prev.id) && SCLEROTINIA_HOSTS.includes(crop.id)) {
    mult *= 0.95;
    notes.push(`Follows ${prev.name.toLowerCase()}: both are Sclerotinia hosts`);
  }
  if (prev.family === 'c4grass' && crop.family === 'cereal') {
    mult *= 0.95;
    notes.push(`${prev.name} residue raises Fusarium risk in cereals`);
  }
  if (prev.family === 'cereal' && !['cereal', 'c4grass'].includes(crop.family)) {
    mult *= 1.03;
    notes.push('Break crop after a cereal: reduces grass weeds and take-all');
  }
  if (!notes.length) notes.push(`Neutral sequence after ${prev.name.toLowerCase()}`);
  return { mult, credit, notes, score: clamp((mult - 0.8) / 0.24) };
}

function textureScore(field, crop) {
  const fit = crop.texture[field.soil.group];
  const tol = crop.waterlogTol;
  const drain = { good: 1, moderate: 1 - (1 - tol) * 0.25, poor: 1 - (1 - tol) * 0.55 }[field.terrain.drainage];
  return { score: fit * drain, fit, drain };
}

// Evaluate one crop under one management strategy. Returns the full result,
// including hard `issues` (constraint violations) and soft `flags`.
export function evaluate(field, crop, strategy, c, opts = {}) {
  const soil = field.soil;
  const prevId = field.history[0]?.crop;
  const perennialFactor = crop.perennial ? 0.875 : 1; // establishment year yields ~60%
  const flags = [];
  const issues = [];

  // --- pH and liming ---
  let effPh = soil.ph;
  let limeT = 0;
  if (soil.ph < crop.ph[1]) {
    limeT = round((crop.ph[1] - soil.ph) * 2.5, 1);
    effPh = round(soil.ph + (crop.ph[1] - soil.ph) * 0.6, 2);
    flags.push({ type: 'info', text: `Lime ${limeT} t/ha to lift pH from ${soil.ph} toward ${crop.ph[1]}` });
  }
  const ph = phScore(effPh, crop.ph);

  // --- texture & drainage ---
  const tex = textureScore(field, crop);

  // --- water ---
  const clim = seasonClimate(field, crop);
  const supply = clim.seasonRain * 0.75 + soil.awc * (crop.sowing === 'spring' ? 1 : 0.8);
  const deficit = Math.max(0, crop.water - supply);
  let irrMm = 0;
  if (strategy.irrigate) irrMm = c.irrigation === 'full' ? deficit : Math.min(deficit, 150);
  const waterRatio = (supply + irrMm) / crop.water;
  const water = clamp(waterRatio);

  // --- temperature ---
  const gddRatio = clim.gdd / crop.gddReq;
  const frostHit = clim.minT < crop.frostTol;
  const temp = clamp(Math.min(1, gddRatio) ** 1.5 * (frostHit ? 0.7 : 1));

  // --- slope ---
  const half = crop.slopeMax / 2;
  const s = field.terrain.slopeMean;
  const slope = s <= half ? 1 : s >= crop.slopeMax ? 0.35 : 1 - (0.65 * (s - half)) / half;

  // --- rotation ---
  const rot = rotationEffect(prevId, crop);

  // --- nutrients ---
  const pStatus = soil.p / SOIL_P_TARGET;
  const kStatus = soil.k / SOIL_K_TARGET;
  const { n: nDem, p: pDem, k: kDem } = crop.nutrients;
  const nutr = clamp((Math.min(1, pStatus) * pDem + Math.min(1, kStatus) * kDem) / (pDem + kDem));

  const factors = [
    { key: 'water', label: 'Water supply', weight: 0.22, score: water,
      value: `${Math.round(waterRatio * 100)}% of demand`,
      detail: `${Math.round(supply)} mm available (seasonal rain ${Math.round(clim.seasonRain)} mm incl. ${OUTLOOK.rainPct}% outlook + ${soil.awc} mm soil store)${irrMm ? ` + ${Math.round(irrMm)} mm irrigation` : ''} vs ${crop.water} mm crop demand.` },
    { key: 'temp', label: 'Heat units & frost', weight: 0.18, score: temp,
      value: `${Math.round(gddRatio * 100)}% of GDD`,
      detail: `${Math.round(clim.gdd)} growing degree-days (base ${crop.base} °C) vs ${crop.gddReq} required.${frostHit ? ` Season minimum ${clim.minT} °C is below its ${crop.frostTol} °C tolerance.` : ''}` },
    { key: 'ph', label: 'Soil pH', weight: 0.16, score: ph,
      value: `pH ${soil.ph}${limeT ? ` → ${effPh}` : ''}`,
      detail: `Optimal range ${crop.ph[1]}–${crop.ph[2]}.${limeT ? ` Liming at ${limeT} t/ha partially corrects acidity in year one.` : ''}` },
    { key: 'texture', label: 'Texture & drainage', weight: 0.14, score: tex.score,
      value: `${soil.textureClass}, ${field.terrain.drainage} drainage`,
      detail: `Texture fit ${Math.round(tex.fit * 100)}%; drainage fit ${Math.round(tex.drain * 100)}% (waterlogging tolerance ${Math.round(crop.waterlogTol * 100)}%).` },
    { key: 'rotation', label: 'Rotation fit', weight: 0.12, score: rot.score,
      value: prevId ? `after ${CROP_BY_ID[prevId]?.name.toLowerCase()}` : 'unknown',
      detail: rot.notes.join('. ') + '.' },
    { key: 'slope', label: 'Slope & terrain', weight: 0.1, score: slope,
      value: `${s}% mean slope`,
      detail: `Suited to slopes up to ~${half}% without extra erosion control; ${crop.slopeMax}% practical limit.` },
    { key: 'nutrients', label: 'P & K status', weight: 0.08, score: nutr,
      value: `P ${soil.p} / K ${soil.k} ppm`,
      detail: `Soil P at ${Math.round(pStatus * 100)}% and K at ${Math.round(kStatus * 100)}% of target; deficits are corrected with fertiliser (see costs).` },
  ];
  const minFactor = Math.min(...factors.map((f) => f.score));
  const suitability = factors.reduce((a, f) => a + f.weight * f.score, 0) * (0.55 + 0.45 * minFactor);

  // --- fertiliser ---
  const nSupply = soil.nMin + soil.om * 12 + rot.credit;
  const nRate = nDem > 0 ? Math.max(0, nDem - nSupply) : 0;
  const pRate = pDem * (pStatus < 0.8 ? 1.3 : pStatus > 1.4 ? 0.3 : 0.8);
  const kRate = kDem * (kStatus < 0.8 ? 1.3 : kStatus > 1.4 ? 0.3 : 0.8);
  let fertCost = (nRate * INPUT_PRICES.n + pRate * INPUT_PRICES.p + kRate * INPUT_PRICES.k) * strategy.fert;
  let fertYield = 1;
  if (fertCost > c.fertBudgetPerHa) {
    const shortfall = 1 - c.fertBudgetPerHa / fertCost;
    fertYield = 1 - 0.4 * shortfall * (nDem > 0 ? 1 : 0.5);
    flags.push({ type: 'warn', text: `Fertiliser capped at $${c.fertBudgetPerHa}/ha (${Math.round(shortfall * 100)}% below plan): about −${Math.round((1 - fertYield) * 100)}% yield` });
    fertCost = c.fertBudgetPerHa;
  }

  // --- yield ---
  const tempYield = Math.min(1, gddRatio) ** 1.2 * (frostHit ? 0.75 : 1);
  const slopeYield = 0.85 + 0.15 * slope;
  let p50 = crop.yield.potential * perennialFactor * Math.min(1, waterRatio) ** 0.7 * tempYield * (0.6 + 0.4 * ph)
    * (0.5 + 0.5 * tex.score) * slopeYield * rot.mult * field.productivity * strategy.yield * fertYield;
  const yieldDrivers = [
    { label: 'Water supply', mult: Math.min(1, waterRatio) ** 0.7 },
    { label: 'Heat units & frost', mult: tempYield },
    { label: 'Soil pH', mult: 0.6 + 0.4 * ph },
    { label: 'Texture & drainage', mult: 0.5 + 0.5 * tex.score },
    { label: 'Slope', mult: slopeYield },
    { label: 'Rotation', mult: rot.mult },
    { label: 'Field productivity (NDVI zones)', mult: field.productivity },
    { label: `Strategy: ${strategy.label.toLowerCase()}`, mult: strategy.yield },
    { label: 'Fertiliser budget', mult: fertYield },
  ];
  if (crop.perennial) yieldDrivers.unshift({ label: 'Establishment-year average', mult: perennialFactor });
  const hist = field.history.filter((h) => h.crop === crop.id);
  let calibration = null;
  if (hist.length) {
    const histAvg = hist.reduce((a, h) => a + h.yield, 0) / hist.length;
    const histAdj = histAvg * strategy.yield * fertYield * (irrMm > 0 ? 1.08 : 1);
    calibration = { years: hist.map((h) => h.year), histAvg, model: p50 };
    p50 = 0.65 * p50 + 0.35 * histAdj;
  }
  const irrCover = deficit > 0 ? Math.min(1, irrMm / deficit) : 0;
  const cv = crop.yield.cv * field.weatherCv * strategy.cv * (1 - 0.35 * irrCover) * (waterRatio < 0.8 ? 1.15 : 1);
  const p10 = p50 * (1 - 1.28 * cv);
  const p90 = p50 * (1 + 1.1 * cv);

  // --- machinery & labour ---
  const missing = crop.machines.filter((m) => !c.machines.includes(m));
  if (missing.length && !c.allowContracting) {
    issues.push({ key: 'machinery', text: `Needs ${missing.map((m) => MACHINES[m].label.toLowerCase()).join(', ')}; not owned and contracting is disabled` });
  } else if (missing.length) {
    flags.push({ type: 'info', text: `Contractor for ${missing.map((m) => MACHINES[m].label.toLowerCase()).join(', ')}` });
  }
  const contractEst = missing.filter((m) => MACHINES[m].stage === 'est').reduce((a, m) => a + MACHINES[m].contract, 0);
  const contractOp = missing.filter((m) => MACHINES[m].stage === 'op').reduce((a, m) => a + MACHINES[m].contract, 0);
  const labourHrs = crop.labour * Math.max(0.3, 1 - 0.2 * missing.length) + irrMm / 25;

  // --- costs ($/ha) ---
  const yieldScale = 0.6 + 0.4 * (p50 / crop.yield.potential);
  const amort = crop.perennial ? crop.standYears : 1;
  const establishment = {
    seed: (crop.costs.seed * strategy.seed) / amort,
    prep: crop.costs.prep / amort,
    planting: crop.costs.planting / amort,
    lime: (limeT * INPUT_PRICES.lime) / 4,
    contract: contractEst / amort,
  };
  const operating = {
    fertiliser: fertCost,
    protection: crop.costs.protection * strategy.prot,
    machinery: crop.costs.machinery * Math.max(0.4, 1 - 0.15 * missing.length),
    harvest: crop.costs.harvest * yieldScale,
    other: crop.costs.other * yieldScale,
    labour: labourHrs * c.labourRate,
    irrigation: irrMm > 0 ? irrMm * INPUT_PRICES.irrigationPerMm + INPUT_PRICES.irrigationFixed : 0,
    contract: contractOp,
  };
  const estPerHa = sum(establishment);
  const opPerHa = sum(operating);
  const totalPerHa = estPerHa + opPerHa;

  // --- financials ---
  const price = crop.price;
  const revenue = p50 * price;
  const margin = revenue - totalPerHa;
  const roi = margin / totalPerHa;
  const sigma = revenue * Math.sqrt(cv ** 2 + crop.priceVol ** 2);
  const pLoss = normCdf(-margin / sigma);
  const downside = p10 * price * (1 - crop.priceVol) - totalPerHa;

  const riskScore = clamp(pLoss * 1.4 + cv * 0.9 + crop.priceVol * 0.5);
  const riskLabel = riskScore < 0.3 ? 'Low' : riskScore < 0.5 ? 'Moderate' : 'High';

  // --- soil impact & sustainability ---
  const im = crop.impact;
  const erosionEff = clamp(im.erosion * (0.5 + s / 8));
  const nBalance = im.n - nRate * strategy.fert * 0.1 + (strategy.id === 'lowinput' ? 10 : 0);
  const sustParts = {
    n: clamp((nBalance + 40) / 100),
    om: clamp((im.om + 0.06) / 0.12),
    structure: (im.structure + 1) / 2,
    erosion: 1 - erosionEff,
    water: irrMm > 0 ? clamp(1 - irrMm / 300) : 1,
    inputs: clamp(1 - (nRate * strategy.fert) / 250),
  };
  const sustainability = clamp(
    100 * (0.2 * sustParts.n + 0.2 * sustParts.om + 0.2 * sustParts.structure + 0.25 * sustParts.erosion
      + 0.075 * sustParts.water + 0.075 * sustParts.inputs) + strategy.sust, 0, 100);

  // --- hard constraints ---
  if (c.excluded.includes(crop.id)) issues.push({ key: 'excluded', text: 'Farmer does not want to grow this crop' });
  if (!opts.ignoreWindow) {
    if (c.window === 'autumn' && crop.sowing !== 'autumn') issues.push({ key: 'window', text: 'Spring-sown: outside the autumn 2026 planting window' });
    if (c.window === 'spring' && crop.sowing !== 'spring') issues.push({ key: 'window', text: 'Autumn-sown: outside the spring 2027 planting window' });
    const latest = LATEST_AUTUMN_SOWING[crop.id];
    if (latest && PLANNING_DATE > latest.date) issues.push({ key: 'window', text: `Sowing window closed (latest ~${latest.label} for this region)` });
  }
  if (crop.perennial && c.horizon < 3) issues.push({ key: 'horizon', text: `Perennial ${crop.standYears}-year stand needs a planning horizon of at least 3 years` });
  if (totalPerHa > c.budgetPerHa) issues.push({ key: 'budget', text: `Costs $${Math.round(totalPerHa).toLocaleString()}/ha, over the $${c.budgetPerHa.toLocaleString()}/ha budget` });
  if (labourHrs * field.area > c.labourHours) issues.push({ key: 'labour', text: `Needs ${Math.round(labourHrs * field.area)} labour hours; ${c.labourHours} available` });
  if (pLoss > MAX_LOSS_PROB[c.risk]) issues.push({ key: 'risk', text: `${Math.round(pLoss * 100)}% chance of a loss is above ${c.risk} risk tolerance (max ${Math.round(MAX_LOSS_PROB[c.risk] * 100)}%)` });
  if (c.sustainability === 'strict' && sustainability < 50) issues.push({ key: 'sustainability', text: `Sustainability score ${Math.round(sustainability)} is below the strict threshold (50)` });
  if (waterRatio < 0.55) issues.push({ key: 'water', text: `Water supply covers only ${Math.round(waterRatio * 100)}% of demand without irrigation` });

  // --- soft flags ---
  if (margin < c.targetMargin) flags.push({ type: 'warn', text: `Margin $${Math.round(margin)}/ha is below the $${c.targetMargin}/ha target` });
  if (waterRatio < 0.85 && !issues.some((i) => i.key === 'water')) flags.push({ type: 'warn', text: `Water-limited: supply covers ${Math.round(waterRatio * 100)}% of demand` });
  if (slope < 0.8) flags.push({ type: 'warn', text: `${s}% slope: use contour or strip tillage and keep residue cover` });
  if (crop.perennial) flags.push({ type: 'info', text: `Establishment spread over a ${crop.standYears}-year stand; yields averaged incl. establishment year` });
  if (calibration) flags.push({ type: 'info', text: `Calibrated with this field's ${calibration.years.join(', ')} yield (${round(calibration.histAvg, 1)} ${crop.unit ?? 't'}/ha)` });

  // --- ranking score ---
  const profitScore = 0.65 * clamp(0.5 + (margin - c.targetMargin) / 1000) + 0.35 * clamp((roi + 0.2) / 1.0);
  const w = {
    suit: 0.35,
    profit: 0.3,
    risk: { low: 0.28, medium: 0.17, high: 0.08 }[c.risk],
    sust: { none: 0.05, balanced: 0.12, strict: 0.25 }[c.sustainability] + (c.horizon - 1) * 0.025,
  };
  const wSum = w.suit + w.profit + w.risk + w.sust;
  const parts = {
    suitability: (w.suit / wSum) * suitability,
    profit: (w.profit / wSum) * profitScore,
    risk: (w.risk / wSum) * (1 - riskScore),
    sustainability: (w.sust / wSum) * (sustainability / 100),
  };
  let score = sum(parts) + (c.preferred.includes(crop.id) ? 0.06 : 0);
  if (margin < c.targetMargin) score *= 0.92;

  return {
    crop, strategy, factors, suitability, score: score * 100, scoreParts: parts,
    preferred: c.preferred.includes(crop.id),
    climate: clim, waterRatio, irrMm, limeT, nRate, pRate, kRate, rotation: rot, missing, labourHrs,
    yield: { p10, p50, p90, cv, unit: crop.unit ?? 't', potential: crop.yield.potential, calibration, drivers: yieldDrivers },
    cost: { establishment, operating, estPerHa, opPerHa, totalPerHa, total: totalPerHa * field.area },
    fin: { price, revenue, margin, roi, breakEvenYield: totalPerHa / price, breakEvenPrice: totalPerHa / p50,
      pLoss, downside, totalRevenue: revenue * field.area, totalMargin: margin * field.area },
    risk: { score: riskScore, label: riskLabel, pLoss, cv, priceVol: crop.priceVol },
    sustain: { score: sustainability, parts: sustParts, nBalance, om: im.om, structure: im.structure, erosion: erosionEff, text: im.text },
    flags, issues, feasible: issues.length === 0,
  };
}

function strategiesFor(c) {
  const list = [STRATEGIES.standard, STRATEGIES.lowinput];
  if (c.irrigation !== 'none') list.push(STRATEGIES.irrigated);
  return list;
}

// Rank all crops. Each crop is represented by its best feasible strategy; the
// other feasible strategies are returned as alternatives.
export function rank(field, c, opts = {}) {
  const ranked = [];
  const rejected = [];
  for (const crop of CROPS) {
    const results = strategiesFor(c)
      .map((st) => evaluate(field, crop, st, c, opts))
      .filter((r) => !(r.strategy.irrigate && r.irrMm === 0));
    const feasible = results.filter((r) => r.feasible).sort((a, b) => b.score - a.score);
    if (feasible.length) {
      ranked.push({ ...feasible[0], alternatives: feasible.slice(1) });
    } else {
      const closest = results.sort((a, b) => a.issues.length - b.issues.length || b.score - a.score)[0];
      rejected.push(closest);
    }
  }
  ranked.sort((a, b) => b.score - a.score);
  ranked.forEach((r, i) => { r.rank = i + 1; });
  return { ranked, rejected };
}

// "Why" narrative for a result, written for a consultant.
export function explain(r, field) {
  const byScore = [...r.factors].sort((a, b) => b.score * b.weight - a.score * a.weight);
  const strengths = byScore.filter((f) => f.score >= 0.85).slice(0, 2);
  const weakest = [...r.factors].sort((a, b) => a.score - b.score)[0];
  const out = [];
  const name = r.crop.name;
  if (strengths.length) {
    out.push(`${name} fits this field well on ${strengths.map((f) => `${f.label.toLowerCase()} (${f.value})`).join(' and ')}.`);
  }
  if (weakest.score < 0.85) {
    out.push(`The main limitation is ${weakest.label.toLowerCase()} (${weakest.value}). ${weakest.detail}`);
  }
  out.push(`Under ${r.strategy.label.toLowerCase()} management the expected margin is $${Math.round(r.fin.margin).toLocaleString()}/ha ($${Math.round(r.fin.totalMargin).toLocaleString()} across ${field.area} ha). The chance of losing money is ${Math.round(r.fin.pLoss * 100)}%, and break-even needs ${round(r.fin.breakEvenYield, 1)} ${r.yield.unit}/ha.`);
  const im = r.sustain;
  out.push(`Soil impact: ${im.nBalance >= 0 ? `leaves about +${Math.round(im.nBalance)}` : `draws down about ${Math.abs(Math.round(im.nBalance))}`} kg N/ha, organic matter ${im.om >= 0 ? '+' : ''}${im.om}%/yr, and erosion risk on this slope is ${im.erosion < 0.3 ? 'low' : im.erosion < 0.6 ? 'moderate' : 'high'}.`);
  return out;
}

// Trade-offs when moving from result `a` (rejected) to result `b` (alternative).
export function compare(a, b) {
  const rows = [
    { label: 'Expected margin', unit: '$/ha', a: a.fin.margin, b: b.fin.margin, higherIsBetter: true, money: true },
    { label: 'Total cost', unit: '$/ha', a: a.cost.totalPerHa, b: b.cost.totalPerHa, higherIsBetter: false, money: true },
    { label: 'Establishment cost', unit: '$/ha', a: a.cost.estPerHa, b: b.cost.estPerHa, higherIsBetter: false, money: true },
    { label: 'Revenue', unit: '$/ha', a: a.fin.revenue, b: b.fin.revenue, higherIsBetter: true, money: true },
    { label: 'Chance of loss', unit: '%', a: a.fin.pLoss * 100, b: b.fin.pLoss * 100, higherIsBetter: false },
    { label: 'Suitability', unit: '/100', a: a.suitability * 100, b: b.suitability * 100, higherIsBetter: true },
    { label: 'Soil N balance', unit: 'kg/ha', a: a.sustain.nBalance, b: b.sustain.nBalance, higherIsBetter: true },
    { label: 'Sustainability', unit: '/100', a: a.sustain.score, b: b.sustain.score, higherIsBetter: true },
  ];
  return rows.map((r) => ({ ...r, delta: r.b - r.a, better: r.higherIsBetter ? r.b >= r.a : r.b <= r.a }));
}

// Translate a consultant's objection into a constraint change.
export const FEEDBACK_REASONS = [
  { id: 'cost', label: 'Too expensive for the farmer' },
  { id: 'risk', label: 'Too risky' },
  { id: 'machinery', label: 'Equipment not available' },
  { id: 'labour', label: 'Not enough labour' },
  { id: 'water', label: 'Irrigation not possible' },
  { id: 'dislike', label: 'Farmer does not want this crop' },
];

export function applyFeedback(reasonId, r, c, field) {
  const next = structuredClone(c);
  const name = `${r.crop.name}${r.strategy.id !== 'standard' ? ` (${r.strategy.label.toLowerCase()})` : ''}`;
  let text;
  switch (reasonId) {
    case 'cost': {
      next.budgetPerHa = Math.max(200, Math.floor((r.cost.totalPerHa - 1) / 10) * 10);
      text = `Budget capped at $${next.budgetPerHa.toLocaleString()}/ha, below the $${Math.round(r.cost.totalPerHa).toLocaleString()}/ha cost of ${name}.`;
      break;
    }
    case 'risk': {
      const i = RISK_LEVELS.indexOf(c.risk);
      if (i > 0) {
        next.risk = RISK_LEVELS[i - 1];
        text = `Risk tolerance lowered from ${c.risk} to ${next.risk} (${name} has a ${Math.round(r.fin.pLoss * 100)}% chance of loss).`;
      } else {
        next.excluded = [...new Set([...c.excluded, r.crop.id])];
        text = `Risk tolerance is already low, so ${r.crop.name} was excluded.`;
      }
      break;
    }
    case 'machinery': {
      if (r.missing.length) {
        next.allowContracting = false;
        text = `No contractor available for ${r.missing.map((m) => MACHINES[m].label.toLowerCase()).join(', ')}, so contracting is now disabled.`;
      } else {
        const special = r.crop.machines.filter((m) => !['tractor', 'sprayer'].includes(m));
        next.machines = c.machines.filter((m) => !special.includes(m));
        text = `Marked ${special.map((m) => MACHINES[m].label.toLowerCase()).join(', ')} as unavailable. Crops needing them will use a contractor if contracting is allowed.`;
      }
      break;
    }
    case 'labour': {
      next.labourHours = Math.max(0, Math.floor(r.labourHrs * field.area * 0.95));
      text = `Labour capped at ${next.labourHours} hours, below the ${Math.round(r.labourHrs * field.area)} h that ${name} needs.`;
      break;
    }
    case 'water': {
      next.irrigation = 'none';
      text = 'Irrigation set to unavailable.';
      break;
    }
    default: {
      next.excluded = [...new Set([...c.excluded, r.crop.id])];
      next.preferred = c.preferred.filter((id) => id !== r.crop.id);
      text = `${r.crop.name} excluded at the farmer's request.`;
    }
  }
  return { constraints: next, text };
}

// Multi-year rotation outlook: greedily choose the best feasible crop each year
// given the previous crop, tracking soil organic matter and cumulative margin.
export function rotationOutlook(field, c, first) {
  const years = [];
  let om = field.soil.om;
  let history = field.history;
  let current = first;
  let cumulative = 0;
  for (let y = 0; y < c.horizon; y++) {
    if (!current) break;
    om = round(om + current.sustain.om, 2);
    cumulative += current.fin.margin;
    years.push({ year: 2027 + y, result: current, om, cumulative });
    history = [{ year: 2027 + y, crop: current.crop.id, yield: current.yield.p50 }, ...history];
    const nextField = { ...field, history, soil: { ...field.soil, om } };
    if (current.crop.perennial && years.filter((x) => x.result.crop.id === current.crop.id).length < current.crop.standYears) {
      continue; // perennial stand stays in place
    }
    current = rank(nextField, c, { ignoreWindow: true }).ranked[0];
  }
  return years;
}
