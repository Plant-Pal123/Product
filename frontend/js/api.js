// Thin client for the real FastAPI backend (../backend). Kept separate from
// engine.js on purpose: the backend's crop catalog (22 standard labels like
// "rice", "jute", "chickpea") is entirely disjoint from this demo's temperate
// crop set (wheat, canola, potato...), so backend output is never fed into
// rank()/evaluate() - it's rendered in its own "Live backend" panel instead.

// The presentation server exposes both the UI and API through one Cloudflare
// origin, which is more reliable on mobile and avoids cross-origin requests.
export const API_BASE = '/api/v1';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* body wasn't JSON */ }
    throw new Error(`${response.status} ${detail}`);
  }
  return response;
}

export async function getPlotData(plotId) {
  return (await request(`/plots/${plotId}/data`)).json();
}

export async function getSoilProperties(plotId) {
  return (await request(`/plots/${plotId}/soil-properties`)).json();
}

export async function refreshSoilProperties(plotId, { force = false } = {}) {
  const query = force ? '?force=true' : '';
  return (await request(`/plots/${plotId}/soil-properties/refresh${query}`, { method: 'POST' })).json();
}

export async function getSatelliteHistory(plotId) {
  return (await request(`/plots/${plotId}/satellite-history`)).json();
}

export async function refreshSatellite(plotId, { force = false } = {}) {
  const query = force ? '?force=true' : '';
  return (await request(`/plots/${plotId}/satellite/refresh${query}`, { method: 'POST' })).json();
}

export async function getWeatherHistory(plotId) {
  return (await request(`/plots/${plotId}/weather-history`)).json();
}

export async function refreshWeather(plotId, { force = false } = {}) {
  const query = force ? '?force=true' : '';
  return (await request(`/plots/${plotId}/weather/refresh${query}`, { method: 'POST' })).json();
}

export async function recommend(plotId) {
  return (await request(`/plots/${plotId}/recommend`, { method: 'POST' })).json();
}

export async function createPlan(recommendationId) {
  return (await request(`/recommendations/${recommendationId}/plan`, { method: 'POST' })).json();
}

export async function getPlan(planId, { forceAiSummary = false } = {}) {
  const query = forceAiSummary ? '?force_ai_summary=true' : '';
  return (await request(`/plans/${planId}${query}`)).json();
}

export function planPdfUrl(planId) {
  return `${API_BASE}/plans/${planId}/pdf`;
}
