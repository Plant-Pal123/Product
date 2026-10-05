// Wires a "Live backend" dashboard tab to the real FastAPI backend.
// Deliberately standalone (no imports from app.js/engine.js and vice versa):
// the backend's crop catalog doesn't overlap with the simulator's, so nothing
// here should ever feed into rank()/evaluate() - it's rendered in its own tab
// instead. app.js only imports `liveBackendView` to get this tab's markup;
// all the interactivity below is wired via document-level event delegation
// (matching app.js's own pattern) so it keeps working after app.js's
// `renderContent()` replaces #content's innerHTML on every tab switch.

import { createPlan, getPlotData, getSatelliteHistory, getSoilProperties, getWeatherHistory, planPdfUrl, recommend, refreshSatellite, refreshSoilProperties, refreshWeather } from './api.js';

// Follows whichever paddock is selected in the main dashboard - each paddock
// has its own real backend Plot row (see backend/scripts/ensure_paddock_plots.py
// and the `plotId` field on each entry in app.js's `paddocks` array).
// app.js calls setActivePlotId() on every paddock switch and on initial load.
let activePlotId = 306; // Kōwhai Downs, Nelson - matches app.js's initial paddockId

export function setActivePlotId(id) {
  activePlotId = id;
}

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const $ = (sel) => document.querySelector(sel);

const PROVENANCE_LABEL = { measured: 'Measured', modelled: 'Modelled', mapped: 'Mapped', derived: 'Derived' };
const QUALITY_LABEL = { valid: 'Valid', estimated: 'Estimated', stale: 'Stale', missing: 'Missing', review: 'Needs review' };

function errorBanner(err) {
  return `<div class="live-banner live-banner-error">
    <strong>Couldn't reach the backend:</strong> ${esc(err.message)}.
    Is it running at <code>127.0.0.1:8000</code>? See backend/README.md.
  </div>`;
}

export function liveBackendView() {
  return `
    <div class="section-title"><h3>Live backend</h3><p>Talks to the real FastAPI service in <code>backend/</code>, not the simulated data above</p></div>
    <div class="live-grid">
      <article class="info-card">
        <div class="live-card-head"><div><span class="eyebrow">Soil properties</span><h3>Source-attributed soil data</h3></div></div>
        <p class="live-intro">Reads <code>soil_observations</code> for the selected paddock (plot id ${activePlotId}) - see
          <code>backend/README.md#soil-property-enrichment</code> for what feeds it and its licensing.</p>
        <div class="live-actions">
          <button type="button" class="secondary-button" id="soilLoadBtn">Load stored properties</button>
          <button type="button" class="secondary-button" id="soilRefreshBtn">Refresh from source</button>
          <label style="display:inline-flex;align-items:center;gap:5px;font-size:12.5px;color:var(--muted)">
            <input type="checkbox" id="soilForceCheckbox">Force (ignore 30-day cache)
          </label>
        </div>
        <div id="soilResult"><p class="live-note">Not loaded yet.</p></div>
      </article>
      <article class="info-card">
        <div class="live-card-head"><div><span class="eyebrow">Satellite</span><h3>NDVI (vegetation index)</h3></div></div>
        <p class="live-intro">Reads <code>satellite_readings</code> for the selected paddock (plot id ${activePlotId}) - see
          <code>backend/README.md#satellite-ndvi-enrichment</code> for what feeds it and its licensing.</p>
        <div class="live-actions">
          <button type="button" class="secondary-button" id="satelliteLoadBtn">Load stored NDVI</button>
          <button type="button" class="secondary-button" id="satelliteRefreshBtn">Refresh from source</button>
          <label style="display:inline-flex;align-items:center;gap:5px;font-size:12.5px;color:var(--muted)">
            <input type="checkbox" id="satelliteForceCheckbox">Force (ignore 5-day cache)
          </label>
        </div>
        <div id="satelliteResult"><p class="live-note">Not loaded yet.</p></div>
      </article>
      <article class="info-card">
        <div class="live-card-head"><div><span class="eyebrow">Weather</span><h3>Daily temperature, rainfall, humidity</h3></div></div>
        <p class="live-intro">Reads <code>weather_readings</code> for the selected paddock (plot id ${activePlotId}) - the same table the crop
          classifier/soil regressor read temperature/humidity/rainfall from. See <code>backend/README.md#weather-enrichment</code>.</p>
        <div class="live-actions">
          <button type="button" class="secondary-button" id="weatherLoadBtn">Load stored weather</button>
          <button type="button" class="secondary-button" id="weatherRefreshBtn">Refresh from source</button>
          <label style="display:inline-flex;align-items:center;gap:5px;font-size:12.5px;color:var(--muted)">
            <input type="checkbox" id="weatherForceCheckbox">Force (ignore today's cache)
          </label>
        </div>
        <div id="weatherResult"><p class="live-note">Not loaded yet.</p></div>
      </article>
      <article class="info-card">
        <div class="live-card-head"><div><span class="eyebrow">Crop recommendation</span><h3>Classifier + regressor</h3></div></div>
        <p class="live-intro">Runs the Random Forest classifier and soil-target regressor against this plot's latest cached readings.</p>
        <div class="live-actions">
          <button type="button" class="primary-button" id="liveRunBtn">Run recommendation</button>
        </div>
        <div id="liveResult"><p class="live-note">Not run yet.</p></div>
      </article>
    </div>`;
}

function depthLabel(depth) {
  if (depth?.top == null && depth?.bottom == null) return '–';
  return `${depth?.top ?? '?'}–${depth?.bottom ?? '?'} cm`;
}

function renderSoilProperties(data) {
  if (!data.soil_properties.length) {
    return `<p class="live-note">No soil properties are stored yet for plot ${data.plot_id}. Click
      <strong>Refresh from source</strong>, or run <code>scripts/ingest_soil_data.py</code> on the backend.</p>`;
  }

  const rows = data.soil_properties.map((p) => `
    <tr>
      <td>${esc(p.property.replaceAll('_', ' '))}</td>
      <td class="mono">${p.value != null ? `${p.value}${p.unit ? ` ${esc(p.unit)}` : ''}` : (p.value_text ? esc(p.value_text) : '—')}</td>
      <td>${esc(depthLabel(p.depth_cm))}</td>
      <td><span class="live-pill">${esc(PROVENANCE_LABEL[p.provenance] ?? p.provenance)}</span></td>
      <td><span class="live-pill live-pill-${esc(p.quality)}">${esc(QUALITY_LABEL[p.quality] ?? p.quality)}</span></td>
      <td>${esc(p.source)}${p.source_vintage ? `<br><small>${esc(p.source_vintage)}</small>` : ''}</td>
    </tr>`).join('');

  return `
    <div class="table-scroll">
      <table class="comparison-table live-soil-table">
        <thead><tr><th>Property</th><th>Value</th><th>Depth</th><th>Provenance</th><th>Quality</th><th>Source</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    ${data.attribution.map((line) => `<p class="live-attribution">${esc(line)}</p>`).join('')}`;
}

async function loadSoilProperties() {
  const btn = $('#soilLoadBtn');
  const out = $('#soilResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Loading...</p>';
  try {
    const data = await getSoilProperties(activePlotId);
    out.innerHTML = renderSoilProperties(data);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderSoilRefreshResults(result) {
  const rows = result.results.map((r) => `
    <li><span class="mono">${esc(r.property_code.replaceAll('_', ' '))}</span>
      <span class="live-pill live-pill-${r.status === 'stored' ? 'valid' : r.status === 'error' ? 'missing' : 'estimated'}">${esc(r.status.replaceAll('_', ' '))}</span>
      ${r.detail ? `<small>${esc(r.detail)}</small>` : ''}
    </li>`).join('');
  return `<ul class="live-refresh-list">${rows}</ul>
    <p class="live-note">Reload with <strong>Load stored properties</strong> above to see anything newly stored.</p>`;
}

async function handleRefreshSoilProperties() {
  const btn = $('#soilRefreshBtn');
  const out = $('#soilResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Querying the source (this can be slow - see backend/README.md for retry/backoff behaviour)...</p>';
  try {
    const result = await refreshSoilProperties(activePlotId, { force: $('#soilForceCheckbox')?.checked });
    out.innerHTML = renderSoilRefreshResults(result);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderSatelliteHistory(data) {
  if (!data.readings.length) {
    return `<p class="live-note">No NDVI readings are stored yet for plot ${data.plot_id}. Click
      <strong>Refresh from source</strong> below.</p>`;
  }

  const rows = data.readings.map((r) => `
    <tr><td>${esc(r.date)}</td><td class="mono">${r.ndvi_mean.toFixed(3)}</td></tr>`).join('');
  const latest = data.readings[data.readings.length - 1];

  return `
    <p class="live-note">Latest: <strong class="mono">${latest.ndvi_mean.toFixed(3)}</strong> (${esc(latest.date)})</p>
    <div class="table-scroll">
      <table class="comparison-table">
        <thead><tr><th>Date</th><th>NDVI mean</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    ${data.attribution.map((line) => `<p class="live-attribution">${esc(line)}</p>`).join('')}`;
}

async function loadSatelliteHistory() {
  const btn = $('#satelliteLoadBtn');
  const out = $('#satelliteResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Loading...</p>';
  try {
    const data = await getSatelliteHistory(activePlotId);
    out.innerHTML = renderSatelliteHistory(data);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderSatelliteRefreshResults(result) {
  const rows = result.results.map((r) => `
    <li><span class="mono">${esc(r.date_from || 'all intervals')}</span>
      <span class="live-pill live-pill-${r.status === 'stored' ? 'valid' : r.status === 'error' ? 'missing' : 'estimated'}">${esc(r.status.replaceAll('_', ' '))}</span>
      ${r.detail ? `<small>${esc(r.detail)}</small>` : ''}
    </li>`).join('');
  return `<ul class="live-refresh-list">${rows}</ul>
    <p class="live-note">Reload with <strong>Load stored NDVI</strong> above to see anything newly stored.</p>`;
}

async function handleRefreshSatellite() {
  const btn = $('#satelliteRefreshBtn');
  const out = $('#satelliteResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Querying the source (this can be slow - see backend/README.md for retry/backoff behaviour)...</p>';
  try {
    const result = await refreshSatellite(activePlotId, { force: $('#satelliteForceCheckbox')?.checked });
    out.innerHTML = renderSatelliteRefreshResults(result);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderWeatherHistory(data) {
  if (!data.readings.length) {
    return `<p class="live-note">No weather readings are stored yet for plot ${data.plot_id}. Click
      <strong>Refresh from source</strong> below.</p>`;
  }

  const rows = data.readings.map((r) => `
    <tr>
      <td>${esc(r.date)}</td>
      <td class="mono">${r.temp != null ? `${r.temp.toFixed(1)}°C` : '—'}</td>
      <td class="mono">${r.rainfall != null ? `${r.rainfall.toFixed(1)} mm` : '—'}</td>
      <td class="mono">${r.humidity != null ? `${r.humidity.toFixed(0)}%` : '—'}</td>
    </tr>`).join('');
  const latest = data.readings[data.readings.length - 1];

  return `
    <p class="live-note">Latest (${esc(latest.date)}): <strong class="mono">${latest.temp?.toFixed(1) ?? '—'}°C</strong>,
      ${latest.rainfall?.toFixed(1) ?? '—'} mm, ${latest.humidity?.toFixed(0) ?? '—'}% humidity</p>
    <div class="table-scroll">
      <table class="comparison-table">
        <thead><tr><th>Date</th><th>Temp</th><th>Rainfall</th><th>Humidity</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function loadWeatherHistory() {
  const btn = $('#weatherLoadBtn');
  const out = $('#weatherResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Loading...</p>';
  try {
    const data = await getWeatherHistory(activePlotId);
    out.innerHTML = renderWeatherHistory(data);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderWeatherRefreshResults(result) {
  const rows = result.results.map((r) => `
    <li><span class="mono">${esc(r.date || 'request')}</span>
      <span class="live-pill live-pill-${r.status === 'stored' ? 'valid' : r.status === 'error' ? 'missing' : 'estimated'}">${esc(r.status.replaceAll('_', ' '))}</span>
      ${r.detail ? `<small>${esc(r.detail)}</small>` : ''}
    </li>`).join('');
  return `<ul class="live-refresh-list">${rows}</ul>
    <p class="live-note">Reload with <strong>Load stored weather</strong> above to see anything newly stored.</p>`;
}

async function handleRefreshWeather() {
  const btn = $('#weatherRefreshBtn');
  const out = $('#weatherResult');
  if (!btn || !out) return;
  btn.disabled = true;
  out.innerHTML = '<p class="live-note">Querying the source...</p>';
  try {
    const result = await refreshWeather(activePlotId, { force: $('#weatherForceCheckbox')?.checked });
    out.innerHTML = renderWeatherRefreshResults(result);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
  }
}

function renderRecommendation(rec) {
  const rows = rec.crops.map((c) => `
    <div class="live-crop-row">
      <div class="live-crop-rank mono">${Math.round(c.confidence * 100)}%</div>
      <div>
        <strong>${esc(c.crop)}</strong>
        <div class="live-note">Top factors: ${c.top_factors.map(esc).join(', ') || 'n/a'}</div>
      </div>
    </div>`).join('');

  const targets = ['n', 'p', 'k', 'ph'];
  const targetRows = targets.map((k) => `
    <tr><td>${k.toUpperCase()}</td><td class="mono">${rec.soil_targets[k]}</td><td class="mono">${rec.soil_gap[k]}</td></tr>
  `).join('');

  return `
    <p class="live-note">Model version <code>${esc(rec.model_version)}</code> · recommendation #${rec.recommendation_id}</p>
    ${rows}
    <div class="table-scroll">
      <table class="comparison-table">
        <thead><tr><th>Nutrient</th><th>Target</th><th>Gap (target − current)</th></tr></thead>
        <tbody>${targetRows}</tbody>
      </table>
    </div>
    <button type="button" class="secondary-button" id="livePlanBtn" data-recommendation-id="${rec.recommendation_id}" style="margin-top:12px">Generate future plan</button>
    <div id="livePlanResult"></div>
  `;
}

function renderPlan(plan) {
  const c = plan.content;
  const heuristics = c.heuristics.map((h) => `<li>${esc(h)}</li>`).join('');
  const f = c.finances;
  return `
    <p class="live-note" style="margin-top:14px">Future plan #${plan.id} · sow ${esc(c.timeline.sow_date)} → harvest ${esc(c.timeline.harvest_date)} (${c.timeline.days_to_harvest} days)</p>
    <ul class="bullets">${heuristics}</ul>
    <div class="soil-kpis" style="margin-top:12px">
      <div><span>Estimated yield</span><strong class="mono">${f.estimated_yield.toFixed(2)}</strong></div>
      <div><span>Revenue</span><strong class="mono">$${f.revenue.toFixed(2)}</strong></div>
      <div><span>Amendment cost</span><strong class="mono">$${f.amendment_cost.toFixed(2)}</strong></div>
      <div><span>Margin</span><strong class="mono">$${f.margin.toFixed(2)}</strong></div>
    </div>
    <a class="secondary-button" href="${planPdfUrl(plan.id)}" target="_blank" rel="noopener" style="display:inline-flex;margin-top:12px;text-decoration:none">Download PDF</a>
  `;
}

async function runRecommendation() {
  const btn = $('#liveRunBtn');
  const out = $('#liveResult');
  if (!btn || !out) return;
  btn.disabled = true;
  btn.textContent = 'Running...';
  out.innerHTML = '<p class="live-note">Fetching plot data and running the classifier + regressor...</p>';
  try {
    await getPlotData(activePlotId); // confirms the plot/readings exist before running the pipeline
    const rec = await recommend(activePlotId);
    out.innerHTML = renderRecommendation(rec);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run recommendation';
  }
}

async function runPlan(recommendationId) {
  const btn = $('#livePlanBtn');
  const out = $('#livePlanResult');
  if (!btn || !out) return;
  btn.disabled = true;
  btn.textContent = 'Generating...';
  out.innerHTML = '<p class="live-note">Generating plan...</p>';
  try {
    const plan = await createPlan(recommendationId);
    out.innerHTML = renderPlan(plan);
  } catch (err) {
    out.innerHTML = errorBanner(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate future plan';
  }
}

document.addEventListener('click', (event) => {
  if (event.target.closest('#soilLoadBtn')) loadSoilProperties();
  if (event.target.closest('#soilRefreshBtn')) handleRefreshSoilProperties();
  if (event.target.closest('#satelliteLoadBtn')) loadSatelliteHistory();
  if (event.target.closest('#satelliteRefreshBtn')) handleRefreshSatellite();
  if (event.target.closest('#weatherLoadBtn')) loadWeatherHistory();
  if (event.target.closest('#weatherRefreshBtn')) handleRefreshWeather();
  if (event.target.closest('#liveRunBtn')) runRecommendation();
  const planBtn = event.target.closest('#livePlanBtn');
  if (planBtn) runPlan(Number(planBtn.dataset.recommendationId));
});
