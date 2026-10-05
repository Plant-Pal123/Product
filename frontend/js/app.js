import { liveBackendView, setActivePlotId } from './live.js';
import { fetchLiveForecast } from './weather.js';
import { createPlan, getPlan, getSoilProperties, recommend } from './api.js?v=20260927-2';

const paddocks = [
  {
    id: 'riverflat-a', name: 'Riverflat A', area: 24.6, soil: 'silt loam', drainage: 'well drained', top: true,
    location: { lat: -41.35, lon: 173.05 }, region: 'Kōwhai Downs, Nelson', plotId: 2,
    ph: 6.4, organic: 3.8, nitrogen: 78, phosphorus: 31, potassium: 164, moisture: 27,
    rainfall: [44, 52, 68, 61, 74, 83, 78, 66, 57, 48, 43, 39],
    crops: [
      { id: 'maize', name: 'Maize grain', category: 'Grain', score: 92, margin: 1180, yield: '13.2 t', cost: 1640, gmo: true },
      { id: 'wheat', name: 'Feed wheat', category: 'Grain', score: 87, margin: 860, yield: '9.8 t', cost: 1120, gmo: true },
      { id: 'barley', name: 'Feed barley', category: 'Grain', score: 81, margin: 740, yield: '8.4 t', cost: 980, gmo: true },
      { id: 'peas', name: 'Process peas', category: 'Vegetable', score: 76, margin: 690, yield: '6.1 t', cost: 1340 },
      { id: 'squash', name: 'Buttercup squash', category: 'Vegetable', score: 68, margin: 610, yield: '32 t', cost: 2180 },
    ],
  },
  {
    id: 'riverflat-b', name: 'Riverflat B', area: 19.1, soil: 'sandy loam', drainage: 'moderately drained',
    location: { lat: -37.9319, lon: 175.2536 }, region: 'Ohaupo, Waikato', plotId: 3,
    ph: 6.1, organic: 3.1, nitrogen: 66, phosphorus: 27, potassium: 148, moisture: 23,
    rainfall: [42, 49, 64, 58, 70, 77, 75, 62, 52, 46, 41, 37],
    crops: [
      { id: 'wheat', name: 'Feed wheat', category: 'Grain', score: 89, margin: 910, yield: '10.1 t', cost: 1140, gmo: true },
      { id: 'maize', name: 'Maize grain', category: 'Grain', score: 85, margin: 1040, yield: '12.6 t', cost: 1610, gmo: true },
      { id: 'barley', name: 'Feed barley', category: 'Grain', score: 80, margin: 715, yield: '8.2 t', cost: 960, gmo: true },
      { id: 'peas', name: 'Process peas', category: 'Vegetable', score: 74, margin: 650, yield: '5.9 t', cost: 1310 },
      { id: 'squash', name: 'Buttercup squash', category: 'Vegetable', score: 65, margin: 560, yield: '30 t', cost: 2110 },
    ],
  },
  {
    id: 'terrace-north', name: 'Terrace North', area: 31.0, soil: 'loam', drainage: 'well drained',
    location: { lat: -43.6333, lon: 172.4833 }, region: 'Lincoln, Canterbury', plotId: 4,
    ph: 6.7, organic: 4.2, nitrogen: 71, phosphorus: 35, potassium: 176, moisture: 25,
    rainfall: [39, 46, 61, 55, 67, 74, 70, 59, 50, 43, 39, 35],
    crops: [
      { id: 'barley', name: 'Feed barley', category: 'Grain', score: 90, margin: 805, yield: '8.9 t', cost: 1010, gmo: true },
      { id: 'wheat', name: 'Feed wheat', category: 'Grain', score: 86, margin: 850, yield: '9.6 t', cost: 1130, gmo: true },
      { id: 'peas', name: 'Process peas', category: 'Vegetable', score: 82, margin: 780, yield: '6.6 t', cost: 1380 },
      { id: 'maize', name: 'Maize grain', category: 'Grain', score: 77, margin: 920, yield: '11.7 t', cost: 1580, gmo: true },
      { id: 'squash', name: 'Buttercup squash', category: 'Vegetable', score: 71, margin: 640, yield: '33 t', cost: 2200 },
    ],
  },
  {
    id: 'clay-flat', name: 'Clay Flat', area: 14.8, soil: 'clay loam', drainage: 'imperfectly drained',
    location: { lat: -45.8795, lon: 170.3419 }, region: 'Mosgiel, Otago', plotId: 5,
    ph: 6.0, organic: 4.7, nitrogen: 83, phosphorus: 24, potassium: 202, moisture: 34,
    rainfall: [47, 55, 71, 65, 78, 88, 84, 71, 61, 52, 47, 43],
    crops: [
      { id: 'peas', name: 'Process peas', category: 'Vegetable', score: 84, margin: 745, yield: '6.4 t', cost: 1360 },
      { id: 'wheat', name: 'Feed wheat', category: 'Grain', score: 80, margin: 790, yield: '9.1 t', cost: 1110, gmo: true },
      { id: 'barley', name: 'Feed barley', category: 'Grain', score: 73, margin: 650, yield: '7.8 t', cost: 950, gmo: true },
      { id: 'squash', name: 'Buttercup squash', category: 'Vegetable', score: 69, margin: 590, yield: '31 t', cost: 2150 },
      { id: 'maize', name: 'Maize grain', category: 'Grain', score: 63, margin: 760, yield: '10.8 t', cost: 1570, gmo: true },
    ],
  },
];

// "Live backend" talks to the real FastAPI service and exposes internals
// (model versions, raw classifier/regressor output) that aren't meant for
// customers - only show it when explicitly opted into dev mode, via
// ?dev=1 (persisted in localStorage so it survives reloads/nav) or
// localStorage.setItem('devMode', '1') directly.
const DEV_MODE = (() => {
  try {
    if (new URLSearchParams(location.search).get('dev') === '1') localStorage.setItem('devMode', '1');
    if (new URLSearchParams(location.search).get('dev') === '0') localStorage.removeItem('devMode');
    return localStorage.getItem('devMode') === '1';
  } catch {
    return false;
  }
})();

const tabs = ['Overview', 'Soil', 'Climate', 'Financials', 'Plan', 'Compare', ...(DEV_MODE ? ['Live backend'] : [])];
const state = {
  paddockId: 'riverflat-a', tab: 'Overview', cropVariants: {}, query: '',
  paddockTabs: {}, // remembers each paddock's own last-viewed tab, so switching paddocks doesn't reset to Overview
  compareIds: ['maize', 'wheat', 'barley'], financeCropId: 'maize', forecastRange: 'weekly',
  scenario: { budget: 1800, risk: 'balanced', irrigation: true },
  report: {
    title: 'Seasonal crop recommendation', preparedBy: 'Agricultural advisory team',
    summary: 'Plant maize grain as the lead option, subject to final contract pricing and a pre-plant soil check.',
    includeAlternatives: true, includeSoil: true, includeClimate: true, includeAiSummary: false, includePlan: false,
  },
  forecastDayIndex: 0,
  planDone: [],
};
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const money = (value) => `$${Number(value).toLocaleString('en-NZ')}`;
const field = () => paddocks.find((p) => p.id === state.paddockId);
// Remembers this paddock's own last-viewed tab so switching paddocks lands
// back on whatever tab you had open for it, instead of always Overview.
const setTab = (tabName) => { state.tab = tabName; state.paddockTabs[state.paddockId] = tabName; };
const phStatus = (value) => value < 5.8 ? 'Acidic' : value < 6.3 ? 'Slightly acidic' : value <= 7 ? 'Optimal' : 'Alkaline';
const weeklyForecast = [
  { day: 'Today', icon: '☀', high: 24, low: 12, rain: 5 },
  { day: 'Sun', icon: '🌤', high: 23, low: 13, rain: 10 },
  { day: 'Mon', icon: '☁', high: 21, low: 12, rain: 25 },
  { day: 'Tue', icon: '🌧', high: 19, low: 11, rain: 70 },
  { day: 'Wed', icon: '🌦', high: 20, low: 10, rain: 45 },
  { day: 'Thu', icon: '☀', high: 22, low: 11, rain: 10 },
  { day: 'Fri', icon: '☀', high: 24, low: 12, rain: 5 },
];
const extendedForecast = [
  ...weeklyForecast,
  { day: 'Sat 3', icon: '🌤', high: 23, low: 13, rain: 15 },
  { day: 'Sun 4', icon: '☁', high: 21, low: 14, rain: 30 },
  { day: 'Mon 5', icon: '🌧', high: 18, low: 12, rain: 75 },
  { day: 'Tue 6', icon: '🌦', high: 20, low: 11, rain: 45 },
  { day: 'Wed 7', icon: '🌤', high: 22, low: 12, rain: 20 },
  { day: 'Thu 8', icon: '☀', high: 24, low: 13, rain: 10 },
  { day: 'Fri 9', icon: '☀', high: 25, low: 14, rain: 5 },
];
const seasonalForecast = [
  ['Oct', 18, 9, 44], ['Nov', 20, 11, 52], ['Dec', 23, 13, 68], ['Jan', 25, 15, 61],
  ['Feb', 25, 15, 74], ['Mar', 23, 13, 83], ['Apr', 20, 10, 78], ['May', 17, 8, 66],
  ['Jun', 14, 6, 57], ['Jul', 13, 5, 48], ['Aug', 14, 6, 43], ['Sep', 16, 7, 39],
].map(([day, high, low, rain]) => ({ day, icon: rain > 70 ? '🌧' : rain > 55 ? '🌦' : '🌤', high, low, rain }));

// Each GMO-capable grain (maize, wheat, barley) gets its own independent
// GMO/non-GMO selection, keyed by crop id in state.cropVariants - picking
// non-GMO wheat has no effect on maize or barley's selection.
function cropVariant(cropId) {
  return state.cropVariants[cropId] ?? 'gmo';
}

function displayCrop(crop) {
  if (!crop.gmo || cropVariant(crop.id) === 'gmo') return crop;
  return {
    ...crop,
    name: `${crop.name} — non-GMO`,
    margin: Math.round(crop.margin * 0.85),
    yield: `${(parseFloat(crop.yield) * 0.92).toFixed(1)} t`,
    cost: Math.round(crop.cost * 0.94),
  };
}

function renderPaddocks() {
  const matches = paddocks.filter((p) => p.name.toLowerCase().includes(state.query.toLowerCase()));
  $('#paddockCount').textContent = matches.length;
  $('#paddockList').innerHTML = matches.length ? matches.map((p) => `
    <button class="paddock-button ${p.id === state.paddockId ? 'active' : ''}" data-paddock="${p.id}" aria-current="${p.id === state.paddockId ? 'true' : 'false'}">
      <span><span class="paddock-name">${p.name}</span><span class="paddock-meta">${p.area.toFixed(1)} ha · ${p.soil}</span></span>
    </button>`).join('') : '<div class="empty-state">No paddocks found</div>';
}

function renderTabs() {
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab-button ${tab === state.tab ? 'active' : ''}" data-tab="${tab}" aria-selected="${tab === state.tab}">${tab}</button>`).join('');
  document.querySelectorAll('[data-rail-tab]').forEach((button) => {
    button.classList.toggle('active', button.dataset.railTab === state.tab);
  });
}

function cropCard(crop, index) {
  const shown = displayCrop(crop);
  const variant = crop.gmo ? cropVariant(crop.id) : null;
  return `<article class="crop-card ${index === 0 ? 'top' : ''}">
    <div class="card-top"><span class="rank mono">${String(index + 1).padStart(2, '0')}</span></div>
    <div><div class="crop-name-row"><span class="crop-name">${shown.name}</span>${crop.gmo ? `<span class="gmo-badge ${variant === 'non-gmo' ? 'non-gmo-badge' : ''}">${variant === 'non-gmo' ? 'Non-GMO' : 'GMO'}</span>` : ''}</div><div class="category">${crop.category}</div></div>
    ${crop.gmo ? `<div class="variant-toggle" role="group" aria-label="${esc(crop.name)} variant"><button class="${variant === 'gmo' ? 'active' : ''}" data-variant="gmo" data-variant-crop="${crop.id}">GMO</button><button class="${variant === 'non-gmo' ? 'active' : ''}" data-variant="non-gmo" data-variant-crop="${crop.id}">Non-GMO</button></div>` : ''}
    <div class="score-row"><span class="score-value mono">${crop.score}</span><div class="score-track" aria-label="Fit score ${crop.score} out of 100"><div class="score-fill" style="width:${crop.score}%"></div></div></div>
    <div class="metrics-row"><div class="metric"><label>Margin/ha</label><strong class="mono">${money(shown.margin)}</strong></div><div class="metric"><label>Yield/ha</label><strong class="mono">${shown.yield}</strong></div><div class="metric"><label>Cost/ha</label><strong class="mono">${money(shown.cost)}</strong></div></div>
  </article>`;
}

function recommendationsView(p) {
  return `<article class="reference-map-card recommendations-map"><div class="reference-map-top"><span>Illustrative regional map</span><span>Example only</span></div><div class="reference-marker"><i></i><strong>Example field</strong><small>Not the user’s current location</small></div><div class="reference-disclaimer">Generic visual reference only. It does not show this paddock, your position, or a live field boundary.</div></article>
    <div class="section-title recommendation-heading"><h3>Recommended crops</h3><p>Grain and vegetable options ranked for ${p.name}</p></div>
    <section class="crop-grid">${p.crops.map(cropCard).join('')}</section>`;
}

// LRIS FSL only publishes pH/organic carbon/CEC/available water/rooting
// depth/phosphate retention (see backend/app/services/soil_enrichment/specs.py)
// - it has no N/P/K nutrient layers, so those bars stay demo-only even once
// live data loads. Everything else on this tab switches to the real reading
// the moment `p.liveSoil` (fetched by loadLiveSoilForPaddock) has it.
function liveSoilValue(p, propertyCode) {
  return p.liveSoil?.soil_properties.find((prop) => prop.property === propertyCode) ?? null;
}

function soilView(p) {
  const livePh = liveSoilValue(p, 'ph');
  const liveOrganic = liveSoilValue(p, 'organic_carbon');
  const liveCec = liveSoilValue(p, 'cec');
  const livePaw = liveSoilValue(p, 'available_water_capacity');
  const liveRooting = liveSoilValue(p, 'potential_rooting_depth');
  const livePret = liveSoilValue(p, 'phosphate_retention');

  const ph = livePh?.value ?? p.ph;
  const organic = liveOrganic?.value ?? p.organic;
  const cec = liveCec?.value ?? (10 + p.organic * 2.2);

  const nutrients = [['Nitrogen', p.nitrogen, 100], ['Phosphorus', p.phosphorus, 50], ['Potassium', p.potassium, 250]];
  const textures = {
    'silt loam': [20, 65, 15], 'sandy loam': [58, 30, 12], loam: [42, 40, 18], 'clay loam': [30, 34, 36],
  };
  const [sand, silt, clay] = textures[p.soil] || [40, 40, 20];
  const phPosition = Math.max(0, Math.min(100, (ph - 4.5) / 3.5 * 100));

  const sourceBanner = p.liveSoil
    ? (p.liveSoil.soil_properties.length
      ? `<div class="live-banner"><strong>Live LRIS data</strong> · ${esc(p.liveSoil.attribution[0] ?? '')}</div>`
      : `<p class="live-note">No LRIS soil data stored yet for this paddock - showing demo values. Run the backend's soil refresh (Live backend tab) or <code>scripts/ingest_soil_data.py</code>.</p>`)
    : (p.liveSoilFailed ? `<p class="live-note">Couldn't reach the backend - showing demo values. See backend/README.md.</p>` : '');

  const extraKpis = [
    livePaw ? `<div><span>Profile available water</span><strong class="mono">${livePaw.value}${livePaw.unit ? ` ${esc(livePaw.unit)}` : ''}</strong><small>${esc(livePaw.source)}</small></div>` : '',
    liveRooting ? `<div><span>Potential rooting depth</span><strong class="mono">${liveRooting.value}${liveRooting.unit ? ` ${esc(liveRooting.unit)}` : ''}</strong><small>${esc(liveRooting.source)}</small></div>` : '',
    livePret ? `<div><span>Phosphate retention</span><strong class="mono">${livePret.value}${livePret.unit ? ` ${esc(livePret.unit)}` : ''}</strong><small>${esc(livePret.source)}</small></div>` : '',
  ].filter(Boolean).join('');

  return `<div class="section-title"><h3>Soil health</h3><p>${p.liveSoil?.soil_properties.length ? 'LRIS Portal (Landcare Research) soil data' : 'Composite field sample · collected 18 Sep 2026'}</p></div>
    ${sourceBanner}
    <div class="soil-dashboard">
      <article class="soil-main info-card">
        <div class="soil-title"><div><span class="eyebrow">${livePh ? 'Source-attributed reading' : 'Latest laboratory results'}</span><h3>${p.name} soil profile</h3></div><span class="outlook-badge">Balanced</span></div>
        <div class="soil-kpis">
          <div><span>pH level</span><strong class="mono">${ph.toFixed(1)}</strong><small>${phStatus(ph)} · target 6.0–7.0</small></div>
          <div><span>Organic matter</span><strong class="mono">${organic.toFixed(1)}%</strong><small>${liveOrganic ? esc(liveOrganic.source) : 'Good carbon level'}</small></div>
          <div><span>CEC</span><strong class="mono">${cec.toFixed(1)}</strong><small>cmol(+)/kg${liveCec ? '' : ' · estimated'}</small></div>
          <div><span>Sample depth</span><strong class="mono">0–15 cm</strong><small>Composite cores</small></div>
        </div>
        ${extraKpis ? `<div class="soil-kpis" style="margin-top:8px">${extraKpis}</div>` : ''}
        <div class="nutrient-panel">
          <div class="chart-head"><div><h3>Nutrient availability</h3><span>${p.liveSoil ? 'Demo estimate - LRIS FSL does not publish N/P/K levels' : 'Current level against agronomic range'}</span></div><strong>mg/kg <small>unless noted</small></strong></div>
          <div class="soil-bars">${nutrients.map(([label, value, max]) => { const pct = Math.min(100, value / max * 100); return `<div class="soil-bar-row"><div class="soil-bar-head"><span>${label}</span><strong class="mono">${value}</strong></div><div class="soil-bar-track"><span class="target-band"></span><i style="width:${pct}%"></i><b style="left:${pct}%"></b></div><small>${pct < 45 ? 'Below target' : pct > 88 ? 'Above target' : 'Within working range'}</small></div>`; }).join('')}</div>
        </div>
      </article>
      <aside class="soil-side info-card">
        <div class="cost-head"><span class="eyebrow">Soil composition</span><h3>${p.soil}</h3><p>Estimated texture from the latest composite sample.</p></div>
        <div class="texture-donut-wrap"><div class="texture-donut" style="--sand:${sand}%; --silt:${sand + silt}%"><span><strong class="mono">${organic.toFixed(1)}%</strong><small>Organic matter</small></span></div></div>
        <div class="texture-legend"><div><span><i class="sand"></i>Sand</span><strong class="mono">${sand}%</strong></div><div><span><i class="silt"></i>Silt</span><strong class="mono">${silt}%</strong></div><div><span><i class="clay"></i>Clay</span><strong class="mono">${clay}%</strong></div></div>
        <div class="ph-scale"><div><span>Acidic</span><strong>pH balance</strong><span>Alkaline</span></div><div class="ph-track"><i style="left:${phPosition}%"></i></div></div>
        <div class="soil-note"><span>✓</span><p><strong>Good planting condition</strong>${ph < 6.1 ? 'A light lime application may improve nutrient availability.' : 'No major pH correction is indicated before planting.'}</p></div>
      </aside>
    </div>`;
}

function climateView(p) {
  const live = p.liveWeather;
  const ranges = { weekly: live?.weekly ?? weeklyForecast, extended: live?.extended ?? extendedForecast, seasonal: seasonalForecast };
  const forecast = ranges[state.forecastRange];
  const selectedIndex = Math.min(state.forecastDayIndex, forecast.length - 1);
  const selectedDay = forecast[selectedIndex];
  const chartValues = state.forecastRange === 'seasonal' ? forecast.map((d) => d.rain) : forecast.map((d) => d.high);
  const chartMax = Math.max(...chartValues) + 5;
  const pointCoords = chartValues.map((value, i) => ({ x: i * (100 / Math.max(1, chartValues.length - 1)), y: 92 - value / chartMax * 72 }));
  const points = pointCoords.map(({ x, y }) => `${x},${y}`).join(' ');
  const chartTitle = state.forecastRange === 'seasonal' ? 'Rainfall outlook' : 'Temperature outlook';
  const chartUnit = state.forecastRange === 'seasonal' ? 'Monthly forecast · mm' : `Daily high · ${state.forecastRange === 'weekly' ? 'next 7 days' : 'next 14 days'}`;
  const chartTotal = state.forecastRange === 'seasonal' ? '642 mm' : `${Math.round(chartValues.reduce((a, b) => a + b, 0) / chartValues.length)}°C`;
  const rangeLabel = state.forecastRange === 'weekly' ? '7-day forecast' : state.forecastRange === 'extended' ? '14-day forecast' : 'Seasonal outlook';
  const workable = state.forecastRange === 'seasonal' ? selectedDay.rain < 75 : selectedDay.rain < 35 && selectedDay.high >= 15 && selectedDay.high <= 27;
  const advisoryTitle = state.forecastRange === 'seasonal' ? (workable ? 'Manageable rainfall month' : 'Higher rainfall month') : (workable ? 'Good fieldwork window' : selectedDay.rain >= 60 ? 'Delay spraying and cultivation' : 'Use caution for fieldwork');
  const advisoryText = state.forecastRange === 'seasonal' ? `${selectedDay.day} is forecast near ${selectedDay.rain} mm. Use this as a planning signal, not a daily schedule.` : `${selectedDay.day} is forecast at ${selectedDay.high}°/${selectedDay.low}° with ${selectedDay.rain}% rain probability. ${workable ? 'Conditions should suit planting and machinery access.' : 'Recheck the short-range forecast before scheduling machinery or sprays.'}`;
  const updatedLabel = live ? `live · ${live.retrievedAt.toLocaleTimeString('en-NZ', { hour: '2-digit', minute: '2-digit' })}` : 'updated 26 Sep 2026';
  const weeklyDays = live?.weekly ?? [];
  const avgHumidity = weeklyDays.length ? Math.round(weeklyDays.reduce((sum, d) => sum + d.humidity, 0) / weeklyDays.length) : 72;
  const avgTemp = weeklyDays.length ? Math.round(weeklyDays.reduce((sum, d) => sum + d.high, 0) / weeklyDays.length) : 21;
  return `<div class="climate-heading"><div class="section-title"><h3>Climate outlook</h3><p>Forecast conditions for ${p.name} · ${updatedLabel}</p></div><div class="forecast-range" role="group" aria-label="Forecast period"><button class="${state.forecastRange === 'weekly' ? 'active' : ''}" data-forecast-range="weekly">7 days</button><button class="${state.forecastRange === 'extended' ? 'active' : ''}" data-forecast-range="extended">14 days</button><button class="${state.forecastRange === 'seasonal' ? 'active' : ''}" data-forecast-range="seasonal">Seasonal</button></div></div>
  <div class="climate-dashboard">
    <article class="climate-main info-card">
      <div class="climate-title"><div><span class="eyebrow">${esc(p.region)}</span><h3>Growing conditions</h3></div><span class="outlook-badge">Favourable</span></div>
      <div class="climate-kpis"><div><span>Avg humidity</span><strong class="mono">${avgHumidity}%</strong><small>60–80% range</small></div><div><span>Avg temperature</span><strong class="mono">${avgTemp}°C</strong><small>12° / 24°</small></div><div><span>Growing degree days</span><strong class="mono">1,240</strong><small>Base 10°C</small></div><div><span>Season rainfall</span><strong class="mono">642 mm</strong><small>−6% vs normal</small></div></div>
      <div class="condition-chart"><div class="chart-head"><div><h3>${chartTitle}</h3><span>${chartUnit}</span></div><strong class="mono">${chartTotal} <small>${state.forecastRange === 'seasonal' ? 'season total' : 'average high'}</small></strong></div><div class="chart-key"><span><i></i>${state.forecastRange === 'seasonal' ? 'Forecast rainfall (mm)' : 'Forecast daily high (°C)'}</span><em>Choose a point for details</em></div><div class="interactive-chart"><div class="chart-scale"><span>${chartMax}${state.forecastRange === 'seasonal' ? ' mm' : '°'}</span><span>${Math.round(chartMax / 2)}${state.forecastRange === 'seasonal' ? ' mm' : '°'}</span><span>0</span></div><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="${chartTitle}"><defs><linearGradient id="rainFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f9e5c" stop-opacity=".28"/><stop offset="1" stop-color="#2f9e5c" stop-opacity="0"/></linearGradient></defs><path d="M0,100 L${points.replaceAll(' ', ' L')} L100,100 Z" fill="url(#rainFill)"/><line x1="0" y1="25" x2="100" y2="25" class="forecast-gridline"/><line x1="0" y1="55" x2="100" y2="55" class="forecast-gridline"/><line x1="0" y1="85" x2="100" y2="85" class="forecast-gridline"/><polyline points="${points}" fill="none" stroke="#2f9e5c" stroke-width="2" vector-effect="non-scaling-stroke"/>${pointCoords.map(({ x, y }, i) => `<circle cx="${x}" cy="${y}" r="${i === selectedIndex ? 2.4 : 1.7}" class="forecast-point ${i === selectedIndex ? 'selected' : ''}" vector-effect="non-scaling-stroke" data-forecast-day="${i}"><title>${forecast[i].day}: ${chartValues[i]}${state.forecastRange === 'seasonal' ? ' mm' : '°C'}</title></circle>`).join('')}</svg></div><div class="month-axis" style="grid-template-columns:repeat(${forecast.length},1fr)">${forecast.map((d, i) => `<button class="${i === selectedIndex ? 'selected' : ''}" data-forecast-day="${i}">${d.day.replace('Today', 'Now')}</button>`).join('')}</div><div class="weather-explainer ${workable ? 'positive' : 'caution'}"><div><span class="eyebrow">What this means</span><h4>${advisoryTitle}</h4><p>${advisoryText}</p></div><dl><div><dt>${state.forecastRange === 'seasonal' ? 'Rainfall' : 'High / low'}</dt><dd class="mono">${state.forecastRange === 'seasonal' ? `${selectedDay.rain} mm` : `${selectedDay.high}° / ${selectedDay.low}°`}</dd></div><div><dt>${state.forecastRange === 'seasonal' ? 'Avg high' : 'Rain chance'}</dt><dd class="mono">${state.forecastRange === 'seasonal' ? `${selectedDay.high}°` : `${selectedDay.rain}%`}</dd></div><div><dt>${state.forecastRange === 'seasonal' ? 'Signal' : 'Wind'}</dt><dd class="mono">${state.forecastRange === 'seasonal' ? 'Planning' : `${12 + selectedIndex % 4 * 3} km/h`}</dd></div></dl></div></div>
    </article>
    <aside class="climate-forecast info-card"><div class="forecast-head"><div><span class="eyebrow">${rangeLabel}</span><h3>${state.forecastRange === 'seasonal' ? 'Growing season' : 'Planting window'}</h3></div><span class="forecast-now"><b>${selectedDay.high}°</b>${selectedDay.day}</span></div><div class="forecast-list forecast-${state.forecastRange}">${forecast.map((d, i) => `<button class="forecast-day ${i === selectedIndex ? 'today' : ''}" data-forecast-day="${i}"><span>${d.day}</span><b class="weather-icon">${d.icon}</b><strong class="mono">${d.high}°</strong><small>${d.low}°</small><em>${d.rain}${state.forecastRange === 'seasonal' ? ' mm' : '%'}</em></button>`).join('')}</div><div class="forecast-note"><span>↗</span><p><strong>${advisoryTitle}</strong>${advisoryText}</p></div></aside>
  </div>`;
}

function financialsView(p) {
  const selectedBase = p.crops.find((crop) => crop.id === state.financeCropId) || p.crops[0];
  const selected = displayCrop(selectedBase);
  const revenue = selected.margin + selected.cost;
  const roi = Math.round(selected.margin / selected.cost * 100);
  const maxMargin = Math.max(...p.crops.map((crop) => displayCrop(crop).margin));
  const costParts = [
    ['Seed & planting', 28, '#2f9e5c'], ['Fertiliser', 26, '#8ec59e'],
    ['Crop protection', 18, '#d4b35f'], ['Machinery', 17, '#758078'], ['Other', 11, '#c9cbc5'],
  ];
  return `<div class="section-title"><h3>Financial outlook</h3><p>Expected performance per hectare · select a crop to inspect</p></div>
    <div class="finance-dashboard">
      <article class="finance-main info-card">
        <div class="finance-title"><div><span class="eyebrow">Selected scenario</span><h3>${selected.name}</h3></div><span class="outlook-badge">${roi >= 65 ? 'Strong return' : roi >= 45 ? 'Moderate return' : 'Lower return'}</span></div>
        <div class="finance-kpis">
          <div><span>Gross revenue</span><strong class="mono">${money(revenue)}</strong><small>Expected per ha</small></div>
          <div><span>Growing cost</span><strong class="mono">${money(selected.cost)}</strong><small>Expected per ha</small></div>
          <div class="featured"><span>Gross margin</span><strong class="mono">${money(selected.margin)}</strong><small>Before overheads</small></div>
          <div><span>Return on cost</span><strong class="mono">${roi}%</strong><small>Margin ÷ cost</small></div>
        </div>
        <div class="margin-chart">
          <div class="chart-head"><div><h3>Margin by crop</h3><span>Expected gross margin · $/ha</span></div><strong class="mono">${money(selected.margin)}<small>selected crop</small></strong></div>
          <div class="margin-bars">${p.crops.map((crop) => { const shown = displayCrop(crop); const active = crop.id === selectedBase.id; return `<button class="margin-row ${active ? 'active' : ''}" data-finance-crop="${crop.id}" aria-pressed="${active}"><span class="margin-name">${shown.name}</span><span class="margin-track"><i style="width:${shown.margin / maxMargin * 100}%"></i></span><strong class="mono">${money(shown.margin)}</strong></button>`; }).join('')}</div>
        </div>
      </article>
      <aside class="cost-panel info-card">
        <div class="cost-head"><span class="eyebrow">Cost structure</span><h3>${money(selected.cost)} / ha</h3><p>Estimated variable costs for ${selected.name.toLowerCase()}.</p></div>
        <div class="cost-donut-wrap"><div class="cost-donut" style="--seed:28%; --fert:54%; --protect:72%; --machine:89%"><span><strong class="mono">${money(selected.cost)}</strong><small>Total cost</small></span></div></div>
        <div class="cost-legend">${costParts.map(([label, share, color]) => `<div><span><i style="background:${color}"></i>${label}</span><strong class="mono">${money(Math.round(selected.cost * share / 100))}</strong></div>`).join('')}</div>
        <div class="finance-note"><span>↗</span><p><strong>${roi}% return on growing cost</strong>${selected.name} returns an estimated ${money(selected.margin)} before fixed farm overheads.</p></div>
      </aside>
    </div>`;
}

// Shared with reportPageMarkup's "Season plan" section, so "Add plan to
// report" reflects the exact same stages/progress shown on the Plan tab.
const PLAN_STAGES = [
  { id: 'contract', phase: 'Commercial', date: 'By 30 Sep', title: 'Confirm buyer and contract', text: 'Lock price basis, quality specification and delivery window.', owner: 'Advisor' },
  { id: 'presow', phase: 'Pre-sowing', date: '1–10 Oct', title: 'Prepare the seedbed', text: 'Confirm field conditions, complete cultivation and apply base P and K.', owner: 'Farm team' },
  { id: 'plant', phase: 'Planting', date: '10–25 Oct', title: 'Plant and verify establishment', text: 'Check soil temperature, sowing depth and plant population behind the drill.', owner: 'Contractor' },
  { id: 'emergence', phase: 'Emergence', date: 'Early Nov', title: 'Inspect emergence', text: 'Count plants, identify gaps and complete early weed control.', owner: 'Advisor' },
  { id: 'nutrition', phase: 'Crop care', date: 'Late Nov', title: 'Review crop nutrition', text: 'Use the latest soil test and crop condition to confirm the nitrogen plan.', owner: 'Advisor' },
  { id: 'harvest', phase: 'Harvest', date: 'Mar–Apr', title: 'Book harvest capacity', text: 'Confirm contractor timing, storage and delivery logistics.', owner: 'Farm team' },
];

function planView(p) {
  const crop = displayCrop(p.crops[0]);
  const stages = PLAN_STAGES;
  const complete = stages.filter((stage) => state.planDone.includes(stage.id)).length;
  const progress = Math.round(complete / stages.length * 100);
  return `<div class="section-title"><h3>Season plan</h3><p>A working execution plan for ${p.name}</p></div>
    <section class="plan-hero"><div><span class="eyebrow">Current crop plan</span><h2>${crop.name}</h2><p>Indicative schedule from commercial sign-off through harvest preparation.</p></div><div class="plan-hero-metrics"><div><span>Planting window</span><strong>10–25 Oct</strong></div><div><span>Working budget</span><strong class="mono">${money(crop.cost)}/ha</strong></div><div><span>Tasks complete</span><strong class="mono">${complete}/${stages.length}</strong></div></div></section>
    <div class="plan-progress"><div class="plan-progress-head"><span>Plan progress</span><strong class="mono">${progress}%</strong></div><div class="plan-progress-track"><i style="width:${progress}%"></i></div></div>
    <div class="plan-workspace"><section class="plan-stages">${stages.map((stage, index) => { const done = state.planDone.includes(stage.id); return `<article class="plan-stage ${done ? 'complete' : ''}"><button class="plan-check" data-plan-step="${stage.id}" aria-pressed="${done}" aria-label="Mark ${stage.title} ${done ? 'incomplete' : 'complete'}">${done ? '✓' : ''}</button><div class="plan-date"><span>${stage.phase}</span><strong>${stage.date}</strong></div><div class="plan-copy"><span class="mono">${String(index + 1).padStart(2, '0')}</span><h3>${stage.title}</h3><p>${stage.text}</p></div><div class="plan-owner"><span>Owner</span><strong>${stage.owner}</strong></div></article>`; }).join('')}</section>
      <aside class="plan-sidebar"><article class="info-card"><span class="eyebrow">Key dependencies</span><h3>Before planting</h3><ul><li><span class="dep-dot amber"></span><div><strong>Crop contract -</strong><small> Still needs confirmation</small></div></li><li><span class="dep-dot green"></span><div><strong>Seed supply - </strong><small>Availability confirmed</small></div></li><li><span class="dep-dot green"></span><div><strong>Machinery - </strong><small>Contractor provisionally held</small></div></li></ul></article><article class="plan-callout"><div><strong>Decision checkpoint</strong><p>Review the 7-day forecast and seedbed condition 48 hours before planting.</p></div></article><button class="secondary-button plan-report-link" data-add-plan-to-report>${state.report.includePlan ? 'Season plan added ✓' : 'Add plan to report →'}</button></aside>
    </div>`;
}

function compareView(p) {
  const selected = p.crops.filter((crop) => state.compareIds.includes(crop.id));
  const best = (key) => Math.max(...selected.map((crop) => Number(displayCrop(crop)[key]) || 0));
  return `<div class="section-title"><h3>Compare crop options</h3><p>Choose two or more crops to compare</p></div>
    <div class="compare-picker">${p.crops.map((crop) => `<button class="compare-chip ${state.compareIds.includes(crop.id) ? 'selected' : ''}" data-compare-crop="${crop.id}" aria-pressed="${state.compareIds.includes(crop.id)}"><span>${state.compareIds.includes(crop.id) ? '✓' : '+'}</span>${crop.name}</button>`).join('')}</div>
    ${selected.length < 2 ? '<div class="compare-empty">Select at least two crops to build a comparison.</div>' : `<article class="compare-card"><div class="table-scroll"><table class="comparison-table interactive"><thead><tr><th>Measure</th>${selected.map((crop) => `<th><span class="crop-dot dot-${crop.id}"></span>${displayCrop(crop).name}</th>`).join('')}</tr></thead><tbody>
      <tr><td>Overall fit</td>${selected.map((crop) => `<td class="mono ${crop.score === Math.max(...selected.map((c) => c.score)) ? 'best-cell' : ''}">${crop.score}<small>/100</small></td>`).join('')}</tr>
      <tr><td>Expected margin</td>${selected.map((crop) => { const x = displayCrop(crop); return `<td class="mono ${x.margin === best('margin') ? 'best-cell' : ''}">${money(x.margin)}<small>/ha</small></td>`; }).join('')}</tr>
      <tr><td>Expected yield</td>${selected.map((crop) => `<td class="mono">${displayCrop(crop).yield}<small>/ha</small></td>`).join('')}</tr>
      <tr><td>Growing cost</td>${selected.map((crop) => `<td class="mono">${money(displayCrop(crop).cost)}<small>/ha</small></td>`).join('')}</tr>
      <tr><td>Category</td>${selected.map((crop) => `<td>${crop.category}</td>`).join('')}</tr>
    </tbody></table></div><p class="comparison-hint"><span>●</span> Highlighted values lead the current selection.</p></article>`}
  `;
}

function scenarioView(p) {
  const { budget, risk, irrigation } = state.scenario;
  const sensitivity = { maize: 0.72, wheat: 0.42, barley: 0.35, peas: 0.58, squash: 0.78 };
  const volatility = { maize: 0.62, wheat: 0.35, barley: 0.31, peas: 0.48, squash: 0.70 };
  const ranked = p.crops.map((crop) => {
    const shown = displayCrop(crop);
    const costExposure = shown.cost / 2600 * 40;
    const weatherSensitivity = (sensitivity[crop.id] || 0.5) * 35;
    const marginVariability = (volatility[crop.id] || 0.5) * 25;
    const riskScore = Math.round(Math.min(100, costExposure + weatherSensitivity + marginVariability));
    const budgetPenalty = shown.cost > budget ? Math.min(22, Math.round((shown.cost - budget) / 45)) : 0;
    const riskAdjustment = risk === 'conservative' ? Math.round((45 - riskScore) / 3) : risk === 'growth' ? Math.round(shown.margin / 180) : Math.round((55 - riskScore) / 8);
    const irrigationAdjustment = irrigation && ['maize', 'squash'].includes(crop.id) ? 4 : 0;
    return { ...crop, shown, riskScore, scenarioScore: Math.max(0, Math.min(99, crop.score - budgetPenalty + riskAdjustment + irrigationAdjustment)), feasible: shown.cost <= budget };
  }).sort((a, b) => b.scenarioScore - a.scenarioScore);
  return `<div class="section-title"><h3>Scenario planner</h3><p>Test assumptions before making a recommendation</p></div><div class="scenario-layout">
    <aside class="scenario-controls info-card"><span class="eyebrow">Planning assumptions</span><h3>Shape the shortlist</h3><label class="scenario-field"><span>Maximum growing cost <output class="mono">${money(budget)}/ha</output></span><input type="range" min="800" max="2600" step="100" value="${budget}" data-scenario-budget></label><div class="scenario-field"><span>Risk approach</span><div class="risk-options">${['conservative','balanced','growth'].map((value) => `<button class="${risk === value ? 'active' : ''}" data-scenario-risk="${value}">${value[0].toUpperCase() + value.slice(1)}</button>`).join('')}</div><div class="risk-definition"><p><strong>Conservative</strong>Favours lower cost and risk scores.</p><p><strong>Balanced</strong>Balances fit, return and uncertainty.</p><p><strong>Growth</strong>Favours higher margins despite exposure.</p></div></div><label class="switch-row"><span><strong>Irrigation available</strong><small>Boost water-sensitive crops</small></span><input type="checkbox" data-scenario-irrigation ${irrigation ? 'checked' : ''}><i></i></label><div class="risk-method"><strong>How risk is measured</strong><p>Risk score runs from 0–100; lower is safer.</p><div><span>Cost exposure</span><b>40%</b></div><div><span>Weather sensitivity</span><b>35%</b></div><div><span>Margin variability</span><b>25%</b></div></div><div class="scenario-tip"><strong>Decision-support estimate</strong>Risk uses demonstration assumptions and should be replaced with validated local history and price distributions.</div></aside>
    <section class="scenario-results"><div class="scenario-summary"><div><span class="eyebrow">Best under this scenario</span><h3>${ranked[0].shown.name}</h3></div><span class="confidence-pill">${ranked[0].scenarioScore} score</span></div><div class="scenario-list">${ranked.map((crop, index) => `<article class="scenario-row ${index === 0 ? 'top' : ''}"><span class="mono scenario-rank">${String(index + 1).padStart(2, '0')}</span><div><strong>${crop.shown.name}</strong><small>${crop.feasible ? 'Within budget' : `${money(crop.shown.cost - budget)}/ha over budget`} · Risk ${crop.riskScore}/100</small></div><div class="scenario-score"><span><i style="width:${crop.scenarioScore}%"></i></span><b class="mono">${crop.scenarioScore}</b></div><div class="scenario-margin"><small>Margin</small><strong class="mono">${money(crop.shown.margin)}/ha</strong></div></article>`).join('')}</div></section>
  </div>`;
}

// Real AI-generated content for the report, sourced from the actual backend
// (recommend -> plan -> DeepSeek summary, see backend/README.md#ai-plan-summary)
// rather than the demo data used everywhere else on this tab. Opt-in
// (unchecked by default) and generated on demand, since it calls a paid API.
function renderAiSummaryBody(p) {
  if (!p.aiSummary) return `<p class="editor-note">Not generated yet - use "Generate AI summary" in the editor panel.</p>`;
  if (p.aiSummary.error) return `<p class="editor-note">Couldn't generate an AI summary right now - try again shortly.</p>`;
  const notes = p.aiSummary.agronomic_notes?.length
    ? `<ul class="bullets">${p.aiSummary.agronomic_notes.map((note) => `<li>${esc(note)}</li>`).join('')}</ul>`
    : '';
  return `<p>${esc(p.aiSummary.narrative)}</p>
    ${notes}
    <p>${esc(p.aiSummary.finance_commentary)}</p>
    <p class="editor-note"><em>AI-generated from this plan's figures - verify before acting on it.</em></p>`;
}

function renderPlanSectionBody(p) {
  const crop = displayCrop(p.crops[0]);
  const complete = PLAN_STAGES.filter((stage) => state.planDone.includes(stage.id)).length;
  const items = PLAN_STAGES.map((stage) => `<li><strong>${esc(stage.title)}</strong> - ${esc(stage.date)}${state.planDone.includes(stage.id) ? ' (done)' : ''}</li>`).join('');
  return `<p>${crop.name} · planting window 10–25 Oct · working budget ${money(crop.cost)}/ha · ${complete}/${PLAN_STAGES.length} tasks complete.</p>
    <ul class="bullets">${items}</ul>`;
}

function reportPageMarkup(p) {
  const top = displayCrop(p.crops[0]);
  return `<div class="report-page-head"><div><span class="report-logo">P</span><strong>PlantPal</strong></div><span>Advisor report · 26 Sep 2026</span></div><div class="report-meta">${p.name} · ${esc(p.region)} · ${p.area.toFixed(1)} ha</div><h1 data-report-preview="title">${esc(state.report.title)}</h1><p class="report-byline">Prepared by <span data-report-preview="preparedBy">${esc(state.report.preparedBy)}</span></p><section class="report-hero"><span>Lead recommendation</span><h2>${top.name}</h2><p data-report-preview="summary">${esc(state.report.summary)}</p><div><strong class="mono">${money(top.margin)}</strong><small>margin / ha</small><strong class="mono">${top.yield}</strong><small>yield / ha</small><strong class="mono">${p.crops[0].score}</strong><small>fit score</small></div></section><section class="report-section" data-report-section="alternatives" ${state.report.includeAlternatives ? '' : 'hidden'}><h3>Alternative options</h3><div class="report-alternatives">${p.crops.slice(1, 4).map((crop) => `<div><strong>${displayCrop(crop).name}</strong><span class="mono">${crop.score}/100 · ${money(displayCrop(crop).margin)}/ha</span></div>`).join('')}</div></section><section class="report-columns"><div data-report-section="soil" ${state.report.includeSoil ? '' : 'hidden'}><h3>Soil summary</h3><p>pH ${p.ph.toFixed(1)} (${phStatus(p.ph).toLowerCase()}), ${p.organic.toFixed(1)}% organic matter and ${p.soil} texture.</p></div><div data-report-section="climate" ${state.report.includeClimate ? '' : 'hidden'}><h3>Climate summary</h3><p>Near-normal rainfall and a warmer spring indicate a favourable establishment window.</p></div></section><section class="report-section" data-report-section="plan" ${state.report.includePlan ? '' : 'hidden'}><h3>Season plan</h3>${renderPlanSectionBody(p)}</section><section class="report-section" data-report-section="aisummary" ${state.report.includeAiSummary ? '' : 'hidden'}><h3>AI-generated summary</h3>${renderAiSummaryBody(p)}</section><footer>Decision-support estimate only. Confirm contracts, prices and field conditions before planting.</footer>`;
}

function reportView(p) {
  return `<div class="section-title"><h3>Report builder</h3><p>Edit the advisor narrative, review the page, then export it as PDF</p></div><div class="report-builder">
    <aside class="report-editor info-card"><span class="eyebrow">Report settings</span><h3>Edit content</h3><label>Report title<input type="text" value="${esc(state.report.title)}" data-report-field="title"></label><label>Prepared by<input type="text" value="${esc(state.report.preparedBy)}" data-report-field="preparedBy"></label><label>Executive recommendation<textarea rows="6" data-report-field="summary">${esc(state.report.summary)}</textarea></label><fieldset><legend>Include sections</legend><label class="report-check"><input type="checkbox" data-report-include="Alternatives" ${state.report.includeAlternatives ? 'checked' : ''}> Alternative crops</label><label class="report-check"><input type="checkbox" data-report-include="Soil" ${state.report.includeSoil ? 'checked' : ''}> Soil summary</label><label class="report-check"><input type="checkbox" data-report-include="Climate" ${state.report.includeClimate ? 'checked' : ''}> Climate summary</label><label class="report-check"><input type="checkbox" data-report-include="Plan" ${state.report.includePlan ? 'checked' : ''}> Season plan</label><label class="report-check"><input type="checkbox" data-report-include="AiSummary" ${state.report.includeAiSummary ? 'checked' : ''}> AI-generated summary</label></fieldset><div class="ai-summary-controls"><span class="editor-note">Calls the real backend + DeepSeek - takes a few seconds.</span><button type="button" class="secondary-button report-export" id="generateAiSummaryBtn">Generate AI summary</button></div><button class="primary-button report-export" data-export-report>Preview & export PDF</button><p class="editor-note">Your edits stay in this browser session until the page is refreshed.</p></aside>
    <div class="report-preview-shell"><div class="preview-label"><span>Live preview</span><span>Letter · 1 page</span></div><article class="report-page">${reportPageMarkup(p)}</article></div>
  </div>`;
}

async function generateAiSummary() {
  const p = field();
  const btn = $('#generateAiSummaryBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Generating...'; }
  try {
    const rec = await recommend(p.plotId);
    const plan = await createPlan(rec.recommendation_id);
    const full = await getPlan(plan.id);
    p.aiSummary = full.content.ai_summary ?? { error: true };
  } catch (err) {
    console.error('AI summary generation failed:', err);
    p.aiSummary = { error: true };
  }
  if (state.paddockId === p.id && state.tab === 'Report') renderContent();
}

function renderContent() {
  const views = { Overview: recommendationsView, Soil: soilView, Climate: climateView, Financials: financialsView, Plan: planView, Compare: compareView, 'Scenario planner': scenarioView, Report: reportView, 'Live backend': liveBackendView };
  $('#content').innerHTML = views[state.tab](field());
}

function render() {
  const p = field();
  $('#fieldName').textContent = p.name;
  $('#fieldMeta').textContent = `${p.area.toFixed(1)} ha · ${p.soil} · sampled 18 Sep 2026`;
  $('#farmName').textContent = p.region;
  const latitude = `${Math.abs(p.location.lat).toFixed(2)}°${p.location.lat < 0 ? 'S' : 'N'}`;
  const longitude = `${Math.abs(p.location.lon).toFixed(2)}°${p.location.lon < 0 ? 'W' : 'E'}`;
  $('#locationLabel').textContent = `${latitude}, ${longitude}`;
  setActivePlotId(p.plotId);
  renderPaddocks(); renderTabs(); renderContent();
  loadLiveWeatherForPaddock(p);
  loadLiveSoilForPaddock(p);
}

function closeSummary() {
  $('#summaryModal').hidden = true;
  document.body.style.overflow = '';
  $('#exportButton').focus();
}

document.addEventListener('click', (event) => {
  const paddock = event.target.closest('[data-paddock]');
  const tab = event.target.closest('[data-tab]');
  const variant = event.target.closest('[data-variant]');
  const railTab = event.target.closest('[data-rail-tab]');
  const compareCrop = event.target.closest('[data-compare-crop]');
  const financeCrop = event.target.closest('[data-finance-crop]');
  const forecastRange = event.target.closest('[data-forecast-range]');
  const forecastDay = event.target.closest('[data-forecast-day]');
  const planStep = event.target.closest('[data-plan-step]');
  if (paddock) { state.paddockId = paddock.dataset.paddock; state.tab = state.paddockTabs[state.paddockId] || 'Overview'; render(); }
  if (tab) { setTab(tab.dataset.tab); renderTabs(); renderContent(); }
  if (railTab) { setTab(railTab.dataset.railTab); renderTabs(); renderContent(); }
  if (compareCrop) {
    const id = compareCrop.dataset.compareCrop;
    state.compareIds = state.compareIds.includes(id) ? state.compareIds.filter((cropId) => cropId !== id) : [...state.compareIds, id];
    renderContent();
  }
  if (financeCrop) { state.financeCropId = financeCrop.dataset.financeCrop; renderContent(); }
  if (forecastRange) { state.forecastRange = forecastRange.dataset.forecastRange; state.forecastDayIndex = 0; renderContent(); }
  if (forecastDay) { state.forecastDayIndex = Number(forecastDay.dataset.forecastDay); renderContent(); }
  if (planStep) {
    const id = planStep.dataset.planStep;
    state.planDone = state.planDone.includes(id) ? state.planDone.filter((stepId) => stepId !== id) : [...state.planDone, id];
    renderContent();
  }
  const scenarioRisk = event.target.closest('[data-scenario-risk]');
  if (scenarioRisk) { state.scenario.risk = scenarioRisk.dataset.scenarioRisk; renderContent(); }
  if (event.target.closest('#generateAiSummaryBtn')) generateAiSummary();
  if (event.target.closest('[data-add-plan-to-report]')) {
    state.report.includePlan = true;
    setTab('Report');
    renderTabs();
    renderContent();
  }
  if (event.target.closest('[data-export-report]')) {
    $('#printArea').classList.add('report-print-area');
    $('#printArea').innerHTML = `<article class="report-page">${reportPageMarkup(field())}</article>`;
    $('#summaryModal').hidden = false;
    document.body.style.overflow = 'hidden';
    $('.close-button').focus();
  }
  if (variant) {
    state.cropVariants[variant.dataset.variantCrop] = variant.dataset.variant;
    renderContent();
  }
  if (event.target.closest('[data-close-modal]')) closeSummary();
});

$('#paddockSearch').addEventListener('input', (event) => { state.query = event.target.value; renderPaddocks(); });
document.addEventListener('input', (event) => {
  if (event.target.matches('[data-scenario-budget]')) {
    state.scenario.budget = Number(event.target.value);
    const output = event.target.closest('.scenario-field')?.querySelector('output');
    if (output) output.textContent = `${money(state.scenario.budget)}/ha`;
  }
  if (event.target.matches('[data-report-field]')) {
    const key = event.target.dataset.reportField;
    state.report[key] = event.target.value;
    const preview = document.querySelector(`[data-report-preview="${key}"]`);
    if (preview) preview.textContent = event.target.value;
  }
});
document.addEventListener('change', (event) => {
  if (event.target.matches('[data-scenario-budget]')) renderContent();
  if (event.target.matches('[data-scenario-irrigation]')) {
    state.scenario.irrigation = event.target.checked;
    renderContent();
  }
  if (event.target.matches('[data-report-include]')) {
    const name = event.target.dataset.reportInclude;
    state.report[`include${name}`] = event.target.checked;
    document.querySelectorAll(`[data-report-section="${name.toLowerCase()}"]`).forEach((section) => { section.hidden = !event.target.checked; });
  }
});
$('#themeToggle').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme === 'dark';
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  localStorage.setItem('plantpal-theme', dark ? 'light' : 'dark');
});
$('#exportButton').addEventListener('click', () => { setTab('Report'); renderTabs(); renderContent(); });
$('#printSummary').addEventListener('click', () => window.print());
$('#copySummary').addEventListener('click', async (event) => {
  // Capture the button before the `await` - `event.currentTarget` is only
  // valid during synchronous event dispatch and becomes null once execution
  // resumes after an await, which silently threw here before this fix.
  const btn = event.currentTarget;
  // Copy exactly what's shown/exported in the preview (respects which
  // sections are toggled on, including the AI summary), not a separate,
  // unrelated hardcoded blurb.
  await navigator.clipboard.writeText($('#printArea').innerText);
  btn.textContent = 'Copied';
  setTimeout(() => { btn.textContent = 'Copy text'; }, 1400);
});
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('#summaryModal').hidden) closeSummary(); });

// Each paddock is its own real place (see the `location`/`region` fields in
// the `paddocks` array above) - weather follows whichever paddock is
// selected, fetched once per paddock and cached on the paddock object itself
// rather than a single global "current location".
async function loadLiveWeatherForPaddock(p) {
  if (p.liveWeather || p.liveWeatherFailed) return;
  try {
    p.liveWeather = await fetchLiveForecast(p.location);
  } catch (err) {
    p.liveWeatherFailed = true;
    console.warn(`Live weather unavailable for ${p.region}, keeping demo forecast:`, err.message); // eslint-disable-line no-console
    return;
  }
  if (state.paddockId === p.id && state.tab === 'Climate') renderContent();
}

// Reads whatever soil_observations the real backend already has stored for
// this paddock's plot (see backend/README.md#soil-property-enrichment) -
// never triggers a live LRIS call itself, since that's the slow/rate-limited
// path handled by the "Refresh from source" button on the Live backend tab.
async function loadLiveSoilForPaddock(p) {
  if (p.liveSoil || p.liveSoilFailed) return;
  try {
    p.liveSoil = await getSoilProperties(p.plotId);
  } catch (err) {
    p.liveSoilFailed = true;
    console.warn(`Live soil data unavailable for ${p.name}, keeping demo values:`, err.message); // eslint-disable-line no-console
    return;
  }
  if (state.paddockId === p.id && state.tab === 'Soil') renderContent();
}

document.documentElement.dataset.theme = localStorage.getItem('plantpal-theme') || 'light';
render();
loadLiveWeatherForPaddock(field());
loadLiveSoilForPaddock(field());
