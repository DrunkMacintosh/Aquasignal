import { describe, expect, test } from 'vitest';
import { ADMIN_UNIT_LABEL, adminUnitNoun, adminUnitType } from './adminUnits.js';

describe('adminUnitType', () => {
  test('classifies the five centrally-governed cities', () => {
    expect(adminUnitType('Ha Noi')).toBe('City');
    expect(adminUnitType('Hai Phong')).toBe('City');
    expect(adminUnitType('Da Nang')).toBe('City');
    expect(adminUnitType('Ho Chi Minh')).toBe('City');
    expect(adminUnitType('Can Tho')).toBe('City');
  });

  test('treats every other ADM1 unit as a province', () => {
    expect(adminUnitType('An Giang')).toBe('Province');
    expect(adminUnitType('Nghe An')).toBe('Province');
    expect(adminUnitType('Vinh Long')).toBe('Province');
  });

  test('is case- and whitespace-insensitive and tolerates aliases', () => {
    expect(adminUnitType('  ha noi ')).toBe('City');
    expect(adminUnitType('HANOI')).toBe('City');
    expect(adminUnitType('Ho Chi Minh City')).toBe('City');
    expect(adminUnitType('')).toBe('Province');
    expect(adminUnitType(undefined)).toBe('Province');
  });
});

describe('adminUnitNoun', () => {
  test('returns the lowercase noun for mid-sentence use', () => {
    expect(adminUnitNoun('Can Tho')).toBe('city');
    expect(adminUnitNoun('An Giang')).toBe('province');
  });
});

describe('ADMIN_UNIT_LABEL', () => {
  test('is the collective province/city label', () => {
    expect(ADMIN_UNIT_LABEL).toBe('District/Province/City');
  });
});
