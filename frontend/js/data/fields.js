// Field data. In production each block comes from a provider adapter:
//   soil      <- lab soil tests + soil grids (texture, pH, OM, nutrients)
//   terrain   <- DEM (slope, aspect, elevation)
//   satellite <- Sentinel-2 NDVI time series (productivity zones)
//   weather   <- station/reanalysis normals, current-season observations, seasonal outlook
// The shapes below are the contract the engine and UI rely on.

const NORMALS = {
  rain: [45, 40, 48, 52, 68, 78, 82, 72, 58, 55, 52, 50],
  tavg: [-1, 0.5, 4.5, 9.5, 14.5, 18, 20.5, 20, 15.5, 10, 4.5, 0.5],
  tmin: [-5, -4.5, -1, 3, 7.5, 11, 13, 12.5, 9, 5, 1, -3.5],
  tmax: [3, 5, 10, 15.5, 21, 24.5, 27, 26.5, 22, 15, 8, 4],
};

// Current season (2026) observed Jan–Sep as ratio of normal rainfall / °C anomaly.
const SEASON_2026 = {
  rainRatio: [1.1, 0.8, 1.25, 0.7, 0.85, 0.6, 0.72, 1.15, 0.9],
  tempAnom: [0.8, 1.4, 0.3, 1.1, 0.6, 1.9, 1.6, 0.4, 1.2],
};

// Seasonal outlook for the planning season (Oct 2026 – Sep 2027).
export const OUTLOOK = {
  source: 'Seasonal ensemble (51 members), issued 20 Sep 2026',
  rainPct: -6,
  tempDelta: 0.5,
  forecastRainRange: [0.7, 1.25], // P10/P90 multiplier on Oct–Dec forecast
  forecastRatio: [0.95, 0.9, 1.0],
};

function climate(tempOffset, rainFactor) {
  const r = (v) => Math.round(v * 10) / 10;
  const rain = NORMALS.rain.map((v) => Math.round(v * rainFactor));
  const tavg = NORMALS.tavg.map((v) => r(v + tempOffset));
  const tmin = NORMALS.tmin.map((v) => r(v + tempOffset));
  const tmax = NORMALS.tmax.map((v) => r(v + tempOffset));
  const observedRain = SEASON_2026.rainRatio.map((k, i) => Math.round(rain[i] * k));
  const observedTemp = SEASON_2026.tempAnom.map((a, i) => r(tavg[i] + a));
  const forecastRain = OUTLOOK.forecastRatio.map((k, i) => Math.round(rain[9 + i] * k));
  const forecastTemp = [9, 10, 11].map((m) => r(tavg[m] + OUTLOOK.tempDelta));
  return { rain, tavg, tmin, tmax, observedRain, observedTemp, forecastRain, forecastTemp };
}

// Weekly volumetric soil moisture (%), Apr – Sep 2026 (26 weeks) + 4-week forecast.
function moistureSeries(fc, wp, wetness, seed) {
  const obs = [];
  let m = fc - 2;
  for (let w = 0; w < 30; w++) {
    const month = 3 + Math.floor(w / 4.35);
    const ratio = SEASON_2026.rainRatio[Math.min(month, 8)];
    const demand = 0.55 + Math.max(0, month - 3) * 0.22;
    const pulse = Math.max(0, Math.sin(w * 1.7 + seed) * 2.6) * ratio * wetness;
    m = Math.min(fc + 1, Math.max(wp - 1, m - demand + pulse + (ratio - 0.8) * 0.8));
    obs.push(Math.round(m * 10) / 10);
  }
  return { weeks: obs, fieldCapacity: fc, wiltingPoint: wp, forecastFrom: 26 };
}

export const FIELDS = [
  {
    id: 'north-slope', name: 'North Slope', farm: 'Kestrel Farm', area: 42,
    location: '52.18° N, 5.62° E', elevation: [214, 236],
    terrain: { slopeMean: 6.8, slopeMax: 12.4, aspect: 'N', drainage: 'good' },
    soil: {
      texture: { sand: 62, silt: 24, clay: 14 }, textureClass: 'Sandy loam', group: 'sandy',
      ph: 5.9, om: 1.8, nMin: 38, p: 14, k: 110, cec: 9, ec: 0.2, bulkDensity: 1.52,
      moisture: 17, depth: 70, awc: 95, sampled: '12 Aug 2026 (8 cores)',
    },
    productivity: 0.9, weatherCv: 1.15,
    history: [
      { year: 2026, crop: 'wheat', yield: 6.9 },
      { year: 2025, crop: 'maize', yield: 8.1 },
      { year: 2024, crop: 'barley', yield: 5.6 },
      { year: 2023, crop: 'canola', yield: 3.1 },
    ],
    polygon: [[8, 14], [58, 6], [92, 12], [95, 44], [74, 62], [30, 64], [6, 50]],
    zoneSeed: 1.3,
    climate: climate(-0.4, 0.95),
    moisture: moistureSeries(24, 9, 0.9, 0.4),
    ndvi: 0.71,
  },
  {
    id: 'river-flats', name: 'River Flats', farm: 'Kestrel Farm', area: 67,
    location: '52.15° N, 5.66° E', elevation: [118, 121],
    terrain: { slopeMean: 0.8, slopeMax: 2.1, aspect: 'flat', drainage: 'poor' },
    soil: {
      texture: { sand: 28, silt: 38, clay: 34 }, textureClass: 'Clay loam', group: 'clay',
      ph: 7.1, om: 3.6, nMin: 62, p: 26, k: 210, cec: 24, ec: 0.4, bulkDensity: 1.34,
      moisture: 31, depth: 120, awc: 175, sampled: '3 Aug 2026 (12 cores)',
    },
    productivity: 1.08, weatherCv: 0.95,
    history: [
      { year: 2026, crop: 'soybean', yield: 3.4 },
      { year: 2025, crop: 'maize', yield: 9.8 },
      { year: 2024, crop: 'wheat', yield: 8.9 },
      { year: 2023, crop: 'sugarbeet', yield: 71 },
    ],
    polygon: [[4, 22], [40, 8], [96, 16], [90, 40], [62, 60], [14, 58]],
    zoneSeed: 2.7,
    climate: climate(0.7, 1.03),
    moisture: moistureSeries(38, 20, 1.2, 1.9),
    ndvi: 0.78,
  },
  {
    id: 'hilltop-east', name: 'Hilltop East', farm: 'Kestrel Farm', area: 28,
    location: '52.21° N, 5.71° E', elevation: [260, 279],
    terrain: { slopeMean: 3.2, slopeMax: 7.4, aspect: 'SE', drainage: 'good' },
    soil: {
      texture: { sand: 22, silt: 58, clay: 20 }, textureClass: 'Silt loam', group: 'loam',
      ph: 6.5, om: 2.7, nMin: 50, p: 19, k: 165, cec: 15, ec: 0.25, bulkDensity: 1.41,
      moisture: 26, depth: 90, awc: 165, sampled: '19 Aug 2026 (6 cores)',
    },
    productivity: 1.0, weatherCv: 1.0,
    history: [
      { year: 2026, crop: 'peas', yield: 3.9 },
      { year: 2025, crop: 'barley', yield: 6.2 },
      { year: 2024, crop: 'wheat', yield: 8.0 },
      { year: 2023, crop: 'maize', yield: 9.4 },
    ],
    polygon: [[20, 8], [80, 10], [94, 36], [70, 62], [24, 60], [8, 34]],
    zoneSeed: 4.1,
    climate: climate(-0.2, 1.06),
    moisture: moistureSeries(33, 13, 1.0, 3.1),
    ndvi: 0.74,
  },
];

// Soil-test targets used for nutrient bullet charts and fertiliser rates.
export const SOIL_TARGETS = {
  ph: { lo: 6.0, hi: 7.2, min: 4.5, max: 8.5, unit: '', label: 'pH (water)' },
  om: { lo: 2.5, hi: 5, min: 0, max: 6, unit: '%', label: 'Organic matter' },
  nMin: { lo: 40, hi: 80, min: 0, max: 120, unit: 'kg/ha', label: 'Mineral N (0–60 cm)' },
  p: { lo: 20, hi: 35, min: 0, max: 50, unit: 'ppm', label: 'Phosphorus (Olsen)' },
  k: { lo: 150, hi: 250, min: 0, max: 320, unit: 'ppm', label: 'Potassium' },
  cec: { lo: 12, hi: 25, min: 0, max: 35, unit: 'cmol/kg', label: 'CEC' },
};
