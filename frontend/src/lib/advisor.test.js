import { describe, expect, test } from 'vitest';
import { ADVISOR_NEEDS, buildSnapshot, needLabel } from './advisor.js';

describe('ADVISOR_NEEDS', () => {
  test('ids match the backend AdvisorNeed contract exactly', () => {
    // Renaming either side without the other would 422 every chat request.
    expect(ADVISOR_NEEDS.map((need) => need.id)).toEqual([
      'water_sustainability',
      'agriculture',
      'urban_supply',
      'industrial',
    ]);
  });

  test('every need has a label and blurb', () => {
    for (const need of ADVISOR_NEEDS) {
      expect(need.label).toBeTruthy();
      expect(need.blurb).toBeTruthy();
    }
  });
});

describe('buildSnapshot', () => {
  // +3 points/month, so the latest month is well above the value 3 months
  // prior -> 'worsening' under the backend's ±5-over-3-months rule.
  const monthly = Array.from({ length: 15 }, (_, i) => ({
    month: `2025-${String(i + 1).padStart(2, '0')}`,
    risk: 40 + i * 3,
    risk_level: 'medium',
  }));

  test('summarises the latest observed month and recent trend', () => {
    const snapshot = buildSnapshot({ monthly });
    const latest = monthly[monthly.length - 1];
    expect(snapshot.current_risk).toBe(latest.risk);
    expect(snapshot.risk_level).toBe('medium');
    expect(snapshot.latest_month).toBe(latest.month);
    expect(snapshot.trend).toBe('worsening');
  });

  test('truncates history to the last 12 months', () => {
    const snapshot = buildSnapshot({ monthly });
    expect(snapshot.history).toHaveLength(12);
    expect(snapshot.history[0].month).toBe(monthly[3].month);
  });

  test('truncates satellite to the last 6 months', () => {
    const satellite = Array.from({ length: 10 }, (_, i) => ({
      month: `2025-${String(i + 1).padStart(2, '0')}`,
      precipitation: i,
    }));
    const snapshot = buildSnapshot({ satellite });
    expect(snapshot.satellite).toHaveLength(6);
    expect(snapshot.satellite[0].precipitation).toBe(4);
  });

  test('maps forecast and permeability fields through', () => {
    const snapshot = buildSnapshot({
      forecast: [
        {
          month: '2026-06',
          predicted_risk: 64,
          confidence_interval_low: 58,
          confidence_interval_high: 70,
        },
      ],
      permeability: {
        permeability_index: 0.42,
        permeability_class: 'moderate',
        recharge_value: 10.5,
        recharge_label: 'moderate',
        net_infiltration_mm: 25,
      },
    });
    expect(snapshot.forecast[0]).toEqual({
      month: '2026-06',
      predicted_risk: 64,
      confidence_interval_low: 58,
      confidence_interval_high: 70,
    });
    expect(snapshot.permeability_index).toBe(0.42);
    expect(snapshot.recharge_label).toBe('moderate');
  });

  test('is null/empty-safe with no input', () => {
    const snapshot = buildSnapshot();
    expect(snapshot.current_risk).toBeNull();
    expect(snapshot.risk_level).toBeNull();
    expect(snapshot.trend).toBe('stable');
    expect(snapshot.history).toEqual([]);
    expect(snapshot.forecast).toEqual([]);
    expect(snapshot.satellite).toEqual([]);
    expect(snapshot.permeability_index).toBeNull();
  });
});

describe('text helpers', () => {
  test('needLabel resolves ids and falls back to the id', () => {
    expect(needLabel('agriculture')).toBe('Agriculture & irrigation');
    expect(needLabel('unknown')).toBe('unknown');
  });
});
