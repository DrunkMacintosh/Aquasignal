import { describe, expect, test } from 'vitest';
import { latestPoint, variableSeries } from './satellite.js';

const OBSERVATIONS = [
  { month: '2026-03', grace_anomaly: -2.5, precipitation: null },
  { month: '2026-04', grace_anomaly: null, precipitation: 120 },
  { month: '2026-05', grace_anomaly: 4.4, precipitation: 197 },
];

describe('variableSeries', () => {
  test('keeps only non-null months for the requested variable', () => {
    expect(variableSeries(OBSERVATIONS, 'grace_anomaly')).toEqual([
      { month: '2026-03', value: -2.5 },
      { month: '2026-05', value: 4.4 },
    ]);
  });

  test('treats zero as a real value, not a gap', () => {
    expect(variableSeries([{ month: '2026-01', precipitation: 0 }], 'precipitation')).toEqual([
      { month: '2026-01', value: 0 },
    ]);
  });

  test('tolerates missing input', () => {
    expect(variableSeries(undefined, 'temperature')).toEqual([]);
    expect(variableSeries([], 'temperature')).toEqual([]);
  });
});

describe('latestPoint', () => {
  test('returns the last entry or null', () => {
    expect(latestPoint(variableSeries(OBSERVATIONS, 'precipitation'))).toEqual({
      month: '2026-05',
      value: 197,
    });
    expect(latestPoint([])).toBeNull();
  });
});
