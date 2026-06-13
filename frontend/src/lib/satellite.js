// Display metadata for the raw satellite variables served by /satellite/*.
// Keys match backend/models/schemas.py SatelliteMonth exactly.

// Labels are written for non-technical water-authority staff; the hint line
// renders under each label, so it carries the precise meaning. NOTE:
// sar_subsidence holds Sentinel-1 VV backscatter in dB — a *proxy* signal,
// not a measured sinking rate (see pipeline.py header).
export const SATELLITE_VARIABLES = [
  {
    key: 'grace_anomaly',
    label: 'Underground water',
    source: 'GRACE satellite',
    unit: 'cm',
    precision: 1,
    hint: 'vs the long-term normal — below 0 means less stored water than usual.',
  },
  {
    key: 'sar_subsidence',
    label: 'Ground radar signal',
    source: 'Sentinel-1 radar',
    unit: 'dB',
    precision: 1,
    hint: 'indirect clue for sinking or wet ground — not a measured sinking rate.',
  },
  {
    key: 'precipitation',
    label: 'Rainfall',
    source: 'ERA5-Land',
    unit: 'mm/mo',
    precision: 0,
    hint: 'total rain received in the month.',
  },
  {
    key: 'evapotranspiration',
    label: 'Evaporation demand',
    source: 'ERA5-Land',
    unit: 'mm/mo',
    precision: 0,
    hint: 'water the heat could pull from the land — above rainfall means the land dried.',
  },
  {
    key: 'temperature',
    label: 'Air temperature',
    source: 'ERA5-Land',
    unit: '°C',
    precision: 1,
    hint: 'monthly average, measured 2 m above ground.',
  },
];

/** Non-null observations for one variable: [{ month, value }], ascending. */
export function variableSeries(observations, key) {
  return (observations ?? [])
    .filter((row) => row?.[key] != null)
    .map((row) => ({ month: row.month, value: row[key] }));
}

export function latestPoint(series) {
  return series.length > 0 ? series[series.length - 1] : null;
}
