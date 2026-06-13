import { describe, expect, test } from 'vitest';
import {
  RISK_BANDS,
  RISK_RAMP,
  formatCellName,
  formatMonth,
  riskBand,
  riskRampGradient,
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

describe('RISK_RAMP', () => {
  test('pins band boundaries to the band colours so the legend cannot drift', () => {
    const at = (stop) => RISK_RAMP.find((s) => s.stop === stop)?.color;
    expect(at(0)).toBe(RISK_BANDS[0].color);
    expect(at(25)).toBe(RISK_BANDS[1].color);
    expect(at(50)).toBe(RISK_BANDS[2].color);
    expect(at(75)).toBe(RISK_BANDS[3].color);
  });

  test('stops are strictly ascending and within range (MapLibre interpolate requires it)', () => {
    for (let i = 1; i < RISK_RAMP.length; i += 1) {
      expect(RISK_RAMP[i].stop).toBeGreaterThan(RISK_RAMP[i - 1].stop);
    }
    expect(RISK_RAMP[0].stop).toBe(0);
    expect(RISK_RAMP[RISK_RAMP.length - 1].stop).toBe(100);
  });
});

describe('riskRampGradient', () => {
  test('builds a CSS linear-gradient spanning the ramp', () => {
    const gradient = riskRampGradient();
    expect(gradient).toMatch(/^linear-gradient\(to right, /);
    expect(gradient).toContain(`${RISK_BANDS[0].color} 0%`);
    expect(gradient).toContain('#6A0000 100%');
  });

  test('honours a custom direction', () => {
    expect(riskRampGradient('to top')).toMatch(/^linear-gradient\(to top, /);
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
