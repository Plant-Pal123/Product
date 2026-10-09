// Placeholder soil data for the Soil tab. Everything here is demo-only and is
// meant to be replaced by the backend: units, range thresholds, dropdown
// options and the per-paddock values can all be changed in this one file.

// Range labels shown under/next to a value once it has a threshold.
// N/P/K keep the wording the soil bars already used.
const NUTRIENT_LABELS = { low: 'Below target', ok: 'Within working range', high: 'Above target' };
const PH_LABELS = { low: 'Low', ok: 'Optimal', high: 'High' };

// Range thresholds. `lo`–`hi` is the target band; `max` is the right-hand end
// of the bar. N/P/K reproduce the soil bars' original cut-offs (below 45% /
// above 88% of the bar). Add an entry here (e.g. `calcium: { lo: 8, hi: 12 }`) and that
// field gets a range badge automatically.
export const SOIL_THRESHOLDS = {
  nitrogen: { lo: 45, hi: 88, max: 100, labels: NUTRIENT_LABELS },
  phosphorus: { lo: 22.5, hi: 44, max: 50, labels: NUTRIENT_LABELS },
  potassium: { lo: 112.5, hi: 220, max: 250, labels: NUTRIENT_LABELS },
  ph: { lo: 6.0, hi: 7.0, labels: PH_LABELS },
};

// Texture, drainage and depth use S-map's own class names, exactly as S-map
// publishes them (full lists checked against the LRIS layers on 2026-10-09).
export const SOIL_OPTIONS = {
  texture: ['Sandy', 'Loamy', 'Silty', 'Clayey', 'Peaty'],
  drainage: ['Well drained', 'Moderately well drained', 'Imperfectly drained', 'Poorly drained', 'Very poorly drained'],
  depthClass: ['Deep', 'Moderately Deep', 'Shallow', 'Very Shallow'],
  dataSource: ['lab test', 'S-map', 'manual entry'],
};

// ESTIMATES ONLY - rough rooting depth (cm) per S-map depth class, used only
// when FSL has no rooting-depth number for the paddock, and always labelled
// "estimate" on screen. Unverified round figures: confirm against S-map's
// data dictionary before relying on them. Never sent to or stored by the backend.
export const SOIL_DEPTH_CM_ESTIMATES = {
  Deep: 100,
  'Moderately Deep': 70,
  Shallow: 35,
  'Very Shallow': 15,
};

// ESTIMATES ONLY - illustrative sand/silt/clay % per S-map texture group,
// for the "Soil composition" donut. Peaty soils are mostly organic matter,
// so they have no sand/silt/clay split here.
export const TEXTURE_COMPOSITION = {
  Sandy: [70, 20, 10],
  Loamy: [42, 40, 18],
  Silty: [20, 65, 15],
  Clayey: [25, 30, 45],
};

// Sample dates older than this show a "Data is over 2 years old" warning.
export const SOIL_SAMPLE_MAX_AGE_YEARS = 2;

// Field definitions, in display order, grouped under the three headings.
// type: number | select | date | text. `step` applies to number inputs.
export const SOIL_GROUPS = [
  {
    id: 'chemistry', title: 'Soil chemistry',
    fields: [
      { key: 'nitrogen', label: 'Nitrogen', unit: 'mg/kg', type: 'number', step: 1 },
      { key: 'phosphorus', label: 'Phosphorus', unit: 'mg/kg', type: 'number', step: 1 },
      { key: 'potassium', label: 'Potassium', unit: 'mg/kg', type: 'number', step: 1 },
      { key: 'ph', label: 'pH', unit: '', type: 'number', step: 0.1 },
      { key: 'organic', label: 'Organic matter', unit: '%', type: 'number', step: 0.1 },
      { key: 'cec', label: 'CEC', unit: 'me/100g', type: 'number', step: 0.1 },
      { key: 'calcium', label: 'Calcium', unit: 'MAF QT units', type: 'number', step: 1 },
      { key: 'magnesium', label: 'Magnesium', unit: 'MAF QT units', type: 'number', step: 1 },
      { key: 'sulphur', label: 'Sulphur', unit: 'MAF QT units', type: 'number', step: 1 },
      { key: 'sodium', label: 'Sodium', unit: 'MAF QT units', type: 'number', step: 1 },
    ],
  },
  {
    id: 'physical', title: 'Physical soil',
    fields: [
      { key: 'texture', label: 'Texture', unit: '', type: 'select', options: SOIL_OPTIONS.texture },
      { key: 'drainage', label: 'Drainage class', unit: '', type: 'select', options: SOIL_OPTIONS.drainage },
      { key: 'depthClass', label: 'Soil depth class', unit: '', type: 'select', options: SOIL_OPTIONS.depthClass },
      { key: 'rootingDepth', label: 'Rooting depth', unit: 'cm', type: 'number', step: 5 },
      { key: 'paw', label: 'Plant-available water (PAW)', unit: 'mm', type: 'number', step: 1 },
    ],
  },
  {
    id: 'sample', title: 'Sample info',
    fields: [
      { key: 'sampleDate', label: 'Sample date', unit: '', type: 'date' },
      { key: 'sampleDepth', label: 'Sample depth', unit: '', type: 'text' },
      { key: 'dataSource', label: 'Data source', unit: '', type: 'select', options: SOIL_OPTIONS.dataSource },
    ],
  },
];

// Per-paddock soil values. `defaults` applies to the whole paddock; `zones`
// is empty for now. When paddock zones exist, each zone goes in here as
// `{ id, name, values: { ...any of the keys below } }` and its values
// override the paddock defaults for that zone only.
export const SOIL_PROFILES = {
  'riverflat-a': {
    defaults: {
      nitrogen: 78, phosphorus: 31, potassium: 164, ph: 6.4, organic: 3.8, cec: 18.4,
      calcium: 10, magnesium: 22, sulphur: 9, sodium: 6,
      texture: 'Silty', drainage: 'Well drained', depthClass: 'Deep', rootingDepth: 90, paw: 140,
      sampleDate: '2026-09-18', sampleDepth: '0–15 cm', dataSource: 'lab test',
    },
    zones: [],
  },
  'riverflat-b': {
    defaults: {
      nitrogen: 66, phosphorus: 27, potassium: 148, ph: 6.1, organic: 3.1, cec: 16.8,
      calcium: 8, magnesium: 18, sulphur: 8, sodium: 5,
      texture: 'Sandy', drainage: 'Moderately well drained', depthClass: 'Moderately Deep', rootingDepth: 70, paw: 95,
      sampleDate: '2026-09-18', sampleDepth: '0–15 cm', dataSource: 'lab test',
    },
    zones: [],
  },
  'terrace-north': {
    defaults: {
      nitrogen: 71, phosphorus: 35, potassium: 176, ph: 6.7, organic: 4.2, cec: 19.2,
      calcium: 11, magnesium: 20, sulphur: 10, sodium: 6,
      texture: 'Loamy', drainage: 'Well drained', depthClass: 'Deep', rootingDepth: 100, paw: 150,
      sampleDate: '2026-09-18', sampleDepth: '0–15 cm', dataSource: 'lab test',
    },
    zones: [],
  },
  'clay-flat': {
    defaults: {
      nitrogen: 83, phosphorus: 24, potassium: 202, ph: 6.0, organic: 4.7, cec: 20.3,
      calcium: 12, magnesium: 25, sulphur: 11, sodium: 9,
      texture: 'Clayey', drainage: 'Imperfectly drained', depthClass: 'Moderately Deep', rootingDepth: 60, paw: 120,
      sampleDate: '2026-09-18', sampleDepth: '0–15 cm', dataSource: 'lab test',
    },
    zones: [],
  },
};
