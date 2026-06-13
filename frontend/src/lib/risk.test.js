import { describe, expect, test } from 'vitest';
import {
  formatCellName,
  formatMonth,
  riskBand,
  shortMonth,
  trendFromHistory,
  trendInfo,
} from './risk.js';

describe('riskBand', () => {
  test('maps band boundaries the same way as the backend (25/50/75)', () => {
    expect(riskBand(0).level).toBe('low');
    expect(riskBand(24.9).level).toBe('low');
    expect(riskBand(25).level).toBe('medium');
    expect(riskBand(49.9).level).toBe('medium');
    expect(riskBand(50).level).toBe('high');
    expect(riskBand(74.9).level).toBe('high');
    expect(riskBand(75).level).toBe('critical');
    expect(riskBand(100).level).toBe('critical');
  });

  test('clamps out-of-range values and tolerates garbage', () => {
    expect(riskBand(-10).level).toBe('low');
    expect(riskBand(140).level).toBe('critical');
    expect(riskBand('not a number').level).toBe('low');
    expect(riskBand(undefined).level).toBe('low');
  });
});

describe('trendInfo', () => {
  test('falls back to stable for unknown values', () => {
    expect(trendInfo('worsening').arrow).toBe('↑');
    expect(trendInfo('improving').arrow).toBe('↓');
    expect(trendInfo('???').label).toBe('Stable');
    expect(trendInfo(undefined).label).toBe('Stable');
  });
});

describe('trendFromHistory', () => {
  const series = (values) => values.map((risk, index) => ({ month: `2026-0${index + 1}`, risk }));

  test('applies the ±5-points-over-3-months rule', () => {
    expect(trendFromHistory(series([40, 41, 42, 46]))).toBe('worsening');
    expect(trendFromHistory(series([40, 41, 42, 34]))).toBe('improving');
    expect(trendFromHistory(series([40, 41, 42, 43]))).toBe('stable');
  });

  test('reads as stable when history is too short', () => {
    expect(trendFromHistory(series([40, 50]))).toBe('stable');
    expect(trendFromHistory([])).toBe('stable');
    expect(trendFromHistory(undefined)).toBe('stable');
  });
});

describe('formatters', () => {
  test('formatCellName renders hemispheres', () => {
    expect(formatCellName('10.125_105.625')).toBe('10.125°N · 105.625°E');
    expect(formatCellName('-3.5_-60.25')).toBe('3.500°S · 60.250°W');
    expect(formatCellName('garbage')).toBe('garbage');
  });

  test('month labels', () => {
    expect(formatMonth('2026-05')).toBe('May 2026');
    expect(shortMonth('2026-11')).toBe('Nov 26');
    expect(formatMonth('bad')).toBe('bad');
  });
});
