// The backend keys forecasts, exports, and alert subscriptions on names in the
// `districts` table (seeded out-of-band from GADM level-2 boundaries — see
// backend/alembic/versions/001_initial.py). There is no GET /districts
// endpoint yet, so the Mekong Delta pilot provinces are listed here as a
// fallback. Replace with an API call once the endpoint exists.
/**
 * District names from the /risk-map/districts FeatureCollection, sorted;
 * districts without scored cells are excluded (reports/alerts would be
 * empty for them). Falls back (offline / pre-load) to the static pilot list.
 */
export function districtNamesFrom(featureCollection, fallback = PILOT_DISTRICTS) {
  const names = featureCollection?.features
    ?.filter((feature) => feature?.properties?.has_data !== false)
    .map((feature) => feature?.properties?.district_name)
    .filter(Boolean);
  return names?.length ? [...names].sort() : fallback;
}

export const PILOT_DISTRICTS = [
  'An Giang',
  'Bac Lieu',
  'Ben Tre',
  'Ca Mau',
  'Can Tho',
  'Dong Thap',
  'Hau Giang',
  'Kien Giang',
  'Long An',
  'Soc Trang',
  'Tien Giang',
  'Tra Vinh',
  'Vinh Long',
];
