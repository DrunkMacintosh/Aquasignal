import { describe, expect, test } from 'vitest';
import { PILOT_DISTRICTS, districtNamesFrom } from './districts.js';

const collection = (names) => ({
  features: names.map((name) => ({ properties: { district_name: name } })),
});

describe('districtNamesFrom', () => {
  test('extracts and sorts names from a FeatureCollection', () => {
    expect(districtNamesFrom(collection(['Long An', 'An Giang', 'Can Tho']))).toEqual([
      'An Giang',
      'Can Tho',
      'Long An',
    ]);
  });

  test('falls back to the pilot list when data is missing or empty', () => {
    expect(districtNamesFrom(undefined)).toEqual(PILOT_DISTRICTS);
    expect(districtNamesFrom({ features: [] })).toEqual(PILOT_DISTRICTS);
  });

  test('ignores features without a district name', () => {
    const mixed = { features: [{ properties: {} }, { properties: { district_name: 'Ben Tre' } }] };
    expect(districtNamesFrom(mixed)).toEqual(['Ben Tre']);
  });

  test('does not mutate the source feature order', () => {
    const data = collection(['Long An', 'An Giang']);
    districtNamesFrom(data);
    expect(data.features[0].properties.district_name).toBe('Long An');
  });
});
