// Season management plan: the crop's template stages plus field- and
// strategy-specific actions derived from the evaluation result.

import { MACHINES } from './data/crops.js';

export function managementPlan(r, field) {
  const crop = r.crop;
  const soil = field.soil;
  const stages = crop.plan.map((s) => ({ ...s, actions: s.actions.map((text) => ({ text })) }));
  const add = (idx, text, why) => stages[Math.min(idx, stages.length - 1)].actions.push({ text, why, custom: true });

  if (r.limeT) add(0, `Spread ${r.limeT} t/ha ground limestone as early as possible, ideally 3+ months before sowing`, `pH ${soil.ph} is below the crop optimum of ${crop.ph[1]}`);
  if (soil.p < 16) add(1, `Place ${Math.round(r.pRate)} kg/ha P₂O₅ in a band at sowing rather than broadcasting`, `Soil P ${soil.p} ppm is below target`);
  if (soil.k < 120) add(0, `Apply ${Math.round(r.kRate)} kg/ha K₂O before sowing`, `Soil K ${soil.k} ppm is low`);
  if (r.nRate > 0) add(2, `Plan ${Math.round(r.nRate * r.strategy.fert)} kg N/ha in total, split into at least two doses`, `Crop demand ${crop.nutrients.n} kg/ha minus ~${Math.round(soil.nMin + soil.om * 12 + r.rotation.credit)} kg/ha supplied by soil${r.rotation.credit ? ' and the previous legume' : ''}`);
  if (field.terrain.slopeMean > crop.slopeMax / 2) add(1, 'Work across the slope, keep ≥ 30% residue cover and leave grassed buffer strips in drainage lines', `${field.terrain.slopeMean}% mean slope (max ${field.terrain.slopeMax}%)`);
  if (field.terrain.drainage === 'poor') add(0, 'Only travel when the soil is at or below field capacity; use controlled traffic lanes and check field drains before sowing', 'Poorly drained clay loam compacts easily');
  if (r.irrMm > 0) {
    const trigger = Math.round(soil.awc * 0.5);
    add(3, `Irrigate ~${Math.round(r.irrMm)} mm over the season in 25–30 mm applications, triggered when the soil moisture deficit reaches ~${trigger} mm`, 'Irrigation strategy selected');
  } else if (r.waterRatio < 0.9) {
    add(1, 'Reduce seed rate by 10–15% to match the water-limited yield potential', `Water covers ${Math.round(r.waterRatio * 100)}% of demand`);
    add(3, `If soil moisture drops below 50% available water (~${Math.round(field.moisture.wiltingPoint + (field.moisture.fieldCapacity - field.moisture.wiltingPoint) / 2)}% vol) in this stage, cut the remaining N by a third`, 'Water stress limits N response');
  }
  if (r.strategy.id === 'lowinput') {
    add(2, 'Take a soil-nitrate or crop-sensor reading before each N dose; skip it if the crop is on track', 'Low-input strategy');
    add(3, 'Spray only at published pest and disease thresholds; scout weekly instead of spraying by calendar', 'Low-input strategy');
  }
  if (r.missing.length) add(0, `Book the contractor early for ${r.missing.map((m) => MACHINES[m].label.toLowerCase()).join(', ')}`, 'Machinery not owned');
  for (const note of r.rotation.notes) if (/disease|Fusarium|Sclerotinia/.test(note)) add(3, `Extra scouting: ${note.toLowerCase()}`, 'Rotation risk');
  add(stages.length - 1, `Record yield with a yield monitor or weighbridge to recalibrate this field's model (current P50 ${r.yield.p50.toFixed(1)} ${r.yield.unit}/ha)`, 'Closes the loop for next season');
  return stages;
}
