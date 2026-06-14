// Vietnam's ADM1 units are provinces or centrally-governed cities — never
// "districts" (a district is the ADM2 level below them). For historical
// reasons the data layer keys everything on `district_name`; this module maps a
// stored name to its correct administrative type so the UI can label each unit
// ("Can Tho · City", "An Giang · Province") instead of the catch-all "district".
//
// Of Vietnam's 63 ADM1 units exactly five are centrally-governed municipalities
// (thành phố trực thuộc trung ương) — every other unit is a province — so we
// list the five and default the rest. Names match the ASCII transliteration the
// seeder produces (backend/scripts/seed_districts.py): e.g. "Thành phố Cần Thơ"
// -> "Can Tho". Aliases cover common alternate spellings of the same units.

/** Collective label for the mixed province/city map layer and toggle. */
export const ADMIN_UNIT_LABEL = 'District/Province/City';

const CITY_NAMES = new Set([
  'ha noi',
  'hanoi',
  'hai phong',
  'haiphong',
  'da nang',
  'danang',
  'ho chi minh',
  'ho chi minh city',
  'can tho',
]);

const normalize = (name) => String(name ?? '').trim().replace(/\s+/g, ' ').toLowerCase();

/** 'City' for the five municipalities, 'Province' for every other ADM1 unit. */
export function adminUnitType(name) {
  return CITY_NAMES.has(normalize(name)) ? 'City' : 'Province';
}

/** Lowercase noun for mid-sentence use ("this city", "city average"). */
export function adminUnitNoun(name) {
  return adminUnitType(name).toLowerCase();
}
