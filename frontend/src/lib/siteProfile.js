// Site-specific inputs + a transparent compute engine (Approach A: frontend
// computes, backend stays a thin proxy). The user enters structured, typed
// parameters about their own site; pure functions here turn those + the district
// snapshot into GROUNDED "calculated" metrics (demand-side numbers we can defend
// from agronomy/engineering coefficients) plus a short summary the AI prompt
// references. These are explicitly NOT AI estimates — they are arithmetic on the
// user's own figures, so they carry a "calculated" tag in the UI.
//
// Coefficients are representative defaults, not site-calibrated values; the UI
// says so and lets users override the ones that matter (efficiency, leakage,
// per-capita use). Keep every function pure and null-safe so a half-filled form
// still produces what it can.

// --- Coefficients (documented, representative) ----------------------------- //

// Monthly net crop water requirement (mm/month). Coarse, dry-season-leaning
// defaults; 1 mm over 1 ha = 10 m3.
const CROP_WATER_MM = { rice: 200, vegetables: 120, fruit: 110, mixed: 140, other: 140 };
const MM_HA_TO_M3 = 10;

// Field application efficiency by irrigation method (fraction reaching the crop).
const IRRIGATION_EFFICIENCY = { flood: 0.45, furrow: 0.55, sprinkler: 0.75, drip: 0.9 };
const DRIP_EFFICIENCY = IRRIGATION_EFFICIENCY.drip;

const DEFAULT_LPD = 120; // litres/person/day (domestic default)
const DEFAULT_LEAKAGE_PCT = 25;
const DAYS_PER_MONTH = 30;

const REUSE_TARGET_PCT = 50; // a commonly achievable process-water reuse target
const CONSERVATION_TARGET_PCT = 15;

// --- Field definitions per need (drive SiteProfileForm) --------------------- //
// type: 'number' | 'select'. `required` marks the field the compute needs.

export const SITE_FIELDS = {
  water_sustainability: [
    { id: 'monthly_volume_m3', label: 'Monthly water use', type: 'number', unit: 'm³/mo', required: true, placeholder: 'e.g. 800' },
    { id: 'num_wells', label: 'Number of wells', type: 'number', placeholder: 'e.g. 2' },
    { id: 'well_depth_m', label: 'Typical well depth', type: 'number', unit: 'm', placeholder: 'e.g. 40' },
    {
      id: 'source', label: 'Main source', type: 'select', placeholder: 'Select…',
      options: [
        { value: 'well', label: 'Groundwater well' },
        { value: 'surface', label: 'Surface water' },
        { value: 'piped', label: 'Piped supply' },
        { value: 'mixed', label: 'Mixed' },
      ],
    },
  ],
  agriculture: [
    { id: 'irrigated_area_ha', label: 'Irrigated area', type: 'number', unit: 'ha', required: true, placeholder: 'e.g. 4' },
    {
      id: 'crop', label: 'Main crop', type: 'select', placeholder: 'Select…',
      options: [
        { value: 'rice', label: 'Rice' },
        { value: 'vegetables', label: 'Vegetables' },
        { value: 'fruit', label: 'Fruit / orchard' },
        { value: 'mixed', label: 'Mixed' },
        { value: 'other', label: 'Other' },
      ],
    },
    {
      id: 'irrigation_method', label: 'Irrigation method', type: 'select', placeholder: 'Select…',
      options: [
        { value: 'flood', label: 'Flood / basin' },
        { value: 'furrow', label: 'Furrow' },
        { value: 'sprinkler', label: 'Sprinkler' },
        { value: 'drip', label: 'Drip' },
      ],
    },
    { id: 'well_depth_m', label: 'Well depth', type: 'number', unit: 'm', placeholder: 'e.g. 35' },
    { id: 'monthly_volume_m3', label: 'Water used / month (if known)', type: 'number', unit: 'm³/mo', placeholder: 'optional' },
  ],
  urban_supply: [
    { id: 'population_served', label: 'People served', type: 'number', unit: 'people', required: true, placeholder: 'e.g. 5000' },
    { id: 'per_capita_lpd', label: 'Use per person', type: 'number', unit: 'L/day', placeholder: `default ${DEFAULT_LPD}` },
    { id: 'leakage_pct', label: 'Network leakage', type: 'number', unit: '%', placeholder: `default ${DEFAULT_LEAKAGE_PCT}` },
    { id: 'storage_m3', label: 'Storage capacity', type: 'number', unit: 'm³', placeholder: 'e.g. 500' },
  ],
  industrial: [
    { id: 'monthly_volume_m3', label: 'Process water / month', type: 'number', unit: 'm³/mo', required: true, placeholder: 'e.g. 1200' },
    { id: 'reuse_pct', label: 'Water reused', type: 'number', unit: '%', placeholder: 'e.g. 10' },
    {
      id: 'process_type', label: 'Main use', type: 'select', placeholder: 'Select…',
      options: [
        { value: 'cooling', label: 'Cooling' },
        { value: 'washing', label: 'Washing / cleaning' },
        { value: 'product', label: 'In product' },
        { value: 'mixed', label: 'Mixed' },
      ],
    },
  ],
};

// --- Small helpers --------------------------------------------------------- //

function num(value) {
  if (value === '' || value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function round(value, digits = 0) {
  if (value == null || !Number.isFinite(value)) return null;
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}

function clamp(value, lo, hi) {
  return Math.min(Math.max(value, lo), hi);
}

/** Latest monthly precipitation (mm) present in the snapshot, or null. */
function latestPrecip(snapshot) {
  const obs = (snapshot?.satellite ?? []).filter((m) => m.precipitation != null);
  return obs.length ? obs[obs.length - 1].precipitation : null;
}

const metric = (label, value, unit, note = '') => ({ label, value, unit, note });

// --- Per-need compute ------------------------------------------------------ //

function computeAgriculture(inputs, snapshot) {
  const area = num(inputs.irrigated_area_ha);
  if (!area || area <= 0) return null;
  const crop = inputs.crop || 'mixed';
  const method = inputs.irrigation_method || 'flood';
  const mm = CROP_WATER_MM[crop] ?? CROP_WATER_MM.mixed;
  const eff = IRRIGATION_EFFICIENCY[method] ?? IRRIGATION_EFFICIENCY.flood;

  const net = area * mm * MM_HA_TO_M3; // delivered to crop, m3/mo
  const gross = net / eff; // abstracted, m3/mo
  const grossDrip = net / DRIP_EFFICIENCY;
  const dripSaving = Math.max(gross - grossDrip, 0);
  const dripSavingPct = gross ? (dripSaving / gross) * 100 : 0;

  const precip = latestPrecip(snapshot);
  const rainContrib = precip != null ? area * precip * MM_HA_TO_M3 : null;
  const rainCoverPct = rainContrib != null && net ? clamp((rainContrib / net) * 100, 0, 100) : null;

  const reported = num(inputs.monthly_volume_m3);

  const metrics = [
    metric('Crop water demand', round(net), 'm³/mo', `${crop}, ~${mm} mm/month`),
    metric('Gross abstraction', round(gross), 'm³/mo', `${method} ~${Math.round(eff * 100)}% efficient`),
    metric('Saving if you switch to drip', round(dripSaving), 'm³/mo', `${round(dripSavingPct)}% less pumping`),
  ];
  if (rainCoverPct != null) {
    metrics.push(metric('Rainfall covers', round(rainCoverPct), '% of demand', 'from latest satellite rainfall'));
  }
  if (reported) {
    const ratio = gross ? (reported / gross) * 100 : null;
    metrics.push(
      metric('Reported vs estimated need', round(ratio), '%', ratio > 115 ? 'possible over-irrigation' : ratio < 85 ? 'below estimated need' : 'roughly matched'),
    );
  }

  return {
    metrics,
    comparison: {
      title: 'Monthly abstraction by method',
      unit: 'm³/mo',
      bars: [
        { label: `Current (${method})`, value: round(gross), tone: 'current' },
        { label: 'Drip', value: round(grossDrip), tone: 'target' },
      ],
    },
    summaryForAi:
      `Site: ${area} ha of ${crop}, ${method} irrigation. Estimated crop demand ~${round(net)} m3/mo, ` +
      `gross abstraction ~${round(gross)} m3/mo; switching to drip could save ~${round(dripSaving)} m3/mo ` +
      `(${round(dripSavingPct)}%).` +
      (reported ? ` User reports using ~${reported} m3/mo.` : ''),
  };
}

function computeUrban(inputs) {
  const pop = num(inputs.population_served);
  if (!pop || pop <= 0) return null;
  const lpd = num(inputs.per_capita_lpd) || DEFAULT_LPD;
  const leak = clamp(num(inputs.leakage_pct) ?? DEFAULT_LEAKAGE_PCT, 0, 95);
  const storage = num(inputs.storage_m3);

  const demandDay = (pop * lpd) / 1000; // m3/day delivered
  const grossDay = demandDay / (1 - leak / 100); // abstracted
  const lossDay = grossDay - demandDay;
  const halvedGrossDay = demandDay / (1 - leak / 2 / 100);
  const halveLeakSavingMo = (grossDay - halvedGrossDay) * DAYS_PER_MONTH;
  const coverDays = storage ? storage / grossDay : null;

  const metrics = [
    metric('Daily demand delivered', round(demandDay), 'm³/day', `${pop} people @ ${lpd} L/day`),
    metric('Gross abstraction', round(grossDay), 'm³/day', `incl. ${round(leak)}% leakage`),
    metric('Lost to leakage', round(lossDay), 'm³/day', `${round(leak)}% of supply`),
  ];
  if (coverDays != null) metrics.push(metric('Storage cover', round(coverDays, 1), 'days', 'at gross abstraction'));
  metrics.push(metric('Saving if leakage halved', round(halveLeakSavingMo), 'm³/mo', `to ${round(leak / 2)}% leakage`));

  return {
    metrics,
    comparison: {
      title: 'Daily water balance',
      unit: 'm³/day',
      bars: [
        { label: 'Delivered', value: round(demandDay), tone: 'target' },
        { label: 'Leakage loss', value: round(lossDay), tone: 'current' },
      ],
    },
    summaryForAi:
      `Site: supply serves ${pop} people at ~${lpd} L/person/day with ~${round(leak)}% leakage. ` +
      `Delivered demand ~${round(demandDay)} m3/day, gross abstraction ~${round(grossDay)} m3/day. ` +
      `Halving leakage could save ~${round(halveLeakSavingMo)} m3/mo.` +
      (coverDays != null ? ` Storage covers ~${round(coverDays, 1)} days.` : ''),
  };
}

function computeIndustrial(inputs) {
  const vol = num(inputs.monthly_volume_m3);
  if (!vol || vol <= 0) return null;
  const reuse = clamp(num(inputs.reuse_pct) ?? 0, 0, 95);
  const freshwater = vol * (1 - reuse / 100);
  const reused = vol - freshwater;
  const targetReuse = Math.max(reuse, REUSE_TARGET_PCT);
  const potentialSaving = Math.max(((targetReuse - reuse) / 100) * vol, 0);

  const metrics = [
    metric('Process water use', round(vol), 'm³/mo', inputs.process_type ? `mainly ${inputs.process_type}` : ''),
    metric('Freshwater intake', round(freshwater), 'm³/mo', `${round(reuse)}% reused`),
    metric('Current reuse rate', round(reuse), '%', `target ${REUSE_TARGET_PCT}%`),
    metric('Extra saving at 50% reuse', round(potentialSaving), 'm³/mo', 'less freshwater abstraction'),
  ];

  return {
    metrics,
    comparison: {
      title: 'Process water split',
      unit: 'm³/mo',
      bars: [
        { label: 'Freshwater', value: round(freshwater), tone: 'current' },
        { label: 'Reused', value: round(reused), tone: 'target' },
      ],
    },
    summaryForAi:
      `Site: ~${vol} m3/mo process water${inputs.process_type ? ` (mainly ${inputs.process_type})` : ''}, ` +
      `~${round(reuse)}% reused (freshwater intake ~${round(freshwater)} m3/mo). Reaching ${REUSE_TARGET_PCT}% reuse ` +
      `could save ~${round(potentialSaving)} m3/mo of freshwater.`,
  };
}

function computeSustainability(inputs) {
  const vol = num(inputs.monthly_volume_m3);
  if (!vol || vol <= 0) return null;
  const wells = num(inputs.num_wells) || 1;
  const daily = vol / DAYS_PER_MONTH;
  const conserve = (vol * CONSERVATION_TARGET_PCT) / 100;

  const metrics = [
    metric('Monthly abstraction', round(vol), 'm³/mo', `${inputs.source || 'source n/a'}`),
    metric('Daily abstraction', round(daily, 1), 'm³/day', `across ${wells} well${wells > 1 ? 's' : ''}`),
    metric('Conservation target (−15%)', round(conserve), 'm³/mo', 'saving if demand trimmed 15%'),
  ];

  return {
    metrics,
    comparison: {
      title: 'Abstraction vs conservation target',
      unit: 'm³/mo',
      bars: [
        { label: 'Current', value: round(vol), tone: 'current' },
        { label: 'Target (−15%)', value: round(vol - conserve), tone: 'target' },
      ],
    },
    summaryForAi:
      `Site: ~${vol} m3/mo total abstraction (${round(daily, 1)} m3/day) from ${wells} well(s), ` +
      `source ${inputs.source || 'n/a'}. A 15% conservation target would save ~${round(conserve)} m3/mo.`,
  };
}

const COMPUTERS = {
  water_sustainability: computeSustainability,
  agriculture: computeAgriculture,
  urban_supply: computeUrban,
  industrial: computeIndustrial,
};

/**
 * Compute grounded site metrics for a need from the user's inputs + the district
 * snapshot. Returns null when the required input is missing (so the caller can
 * skip the section). Result: { metrics:[{label,value,unit,note}], comparison, summaryForAi }.
 */
export function computeSiteMetrics(need, inputs = {}, snapshot = {}) {
  const fn = COMPUTERS[need];
  if (!fn) return null;
  const result = need === 'agriculture' ? fn(inputs, snapshot) : fn(inputs);
  if (!result || !result.metrics?.length) return null;
  // Drop any metric whose value didn't compute, so the UI never shows blanks.
  result.metrics = result.metrics.filter((m) => m.value != null && Number.isFinite(m.value));
  return result.metrics.length ? result : null;
}

/** Field definitions for a need (empty array if unknown). */
export function siteFieldsFor(need) {
  return SITE_FIELDS[need] ?? [];
}

/** True when every required field for the need has a non-empty value. */
export function hasRequiredSiteInputs(need, inputs = {}) {
  return siteFieldsFor(need)
    .filter((f) => f.required)
    .every((f) => num(inputs[f.id]) != null && num(inputs[f.id]) > 0);
}
