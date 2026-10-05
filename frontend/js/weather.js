// Live weather for the Climate tab, via Open-Meteo's free forecast API
// (no key/signup required, CORS-open - https://open-meteo.com/). Returns
// data shaped exactly like the existing weeklyForecast/extendedForecast
// arrays in app.js ({ day, icon, high, low, rain }, plus a `humidity` field
// those fake arrays don't have) so app.js can swap the data source without
// touching how it's rendered.
//
// Each paddock in app.js carries its own real `location` (see the
// `paddocks` array there) - weather is fetched per paddock, not from one
// single app-wide default.

const DEFAULT_LOCATION = { lat: -41.35, lon: 173.05 }; // Kōwhai Downs, Nelson - fallback only

const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';
const DAILY_VARS = [
  'weathercode', 'temperature_2m_max', 'temperature_2m_min',
  'precipitation_probability_max', 'relative_humidity_2m_mean',
].join(',');

// WMO weather codes (https://open-meteo.com/en/docs) mapped onto this app's
// existing four-icon set - no new icons, so nothing about the chart/list
// visuals changes.
function iconFor(code) {
  if (code === 0) return '☀';
  if (code === 1) return '☀';
  if (code === 2) return '🌤';
  if (code === 3 || code === 45 || code === 48) return '☁';
  if ([51, 53, 55, 56, 57, 80].includes(code)) return '🌦';
  return '🌧'; // rain, freezing rain, snow, showers, thunderstorm
}

function dayLabel(dateStr, index) {
  const date = new Date(`${dateStr}T00:00:00`);
  if (index === 0) return 'Today';
  const weekday = date.toLocaleDateString('en-NZ', { weekday: 'short' });
  if (index < 7) return weekday;
  return `${weekday} ${date.getDate()}`;
}

/**
 * Fetches a 16-day daily forecast and returns { weekly, extended, retrievedAt }
 * where weekly = first 7 days and extended = first 14. Throws on network/HTTP
 * failure or a malformed response - callers should catch and keep whatever
 * they were already showing rather than display a broken fetch.
 */
export async function fetchLiveForecast({ lat, lon } = DEFAULT_LOCATION) {
  const params = new URLSearchParams({
    latitude: lat, longitude: lon, daily: DAILY_VARS,
    timezone: 'auto', forecast_days: '16',
  });
  const response = await fetch(`${FORECAST_URL}?${params}`);
  if (!response.ok) throw new Error(`Open-Meteo returned HTTP ${response.status}`);
  const body = await response.json();
  const daily = body.daily;
  if (!daily?.time?.length) throw new Error('Open-Meteo response missing daily data');

  const days = daily.time
    .map((dateStr, i) => ({
      dateStr,
      code: daily.weathercode[i],
      high: daily.temperature_2m_max[i],
      low: daily.temperature_2m_min[i],
      rain: daily.precipitation_probability_max[i],
      humidity: daily.relative_humidity_2m_mean[i],
    }))
    // Open-Meteo can return a null/partial final day at the edge of its
    // forecast window - drop rather than show a broken/blank entry.
    .filter((d) => d.code != null && d.high != null && d.low != null)
    .map((d, i) => ({
      day: dayLabel(d.dateStr, i),
      icon: iconFor(d.code),
      high: Math.round(d.high),
      low: Math.round(d.low),
      rain: Math.round(d.rain ?? 0),
      humidity: Math.round(d.humidity ?? 0),
    }));

  return {
    weekly: days.slice(0, 7),
    extended: days.slice(0, 14),
    retrievedAt: new Date(),
    source: 'Open-Meteo forecast API',
  };
}
