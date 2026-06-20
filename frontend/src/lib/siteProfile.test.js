import { describe, expect, test } from 'vitest';
import { ADVISOR_NEEDS } from './advisor.js';
import {
  SITE_FIELDS,
  computeSiteMetrics,
  hasRequiredSiteInputs,
  siteFieldsFor,
} from './siteProfile.js';

/** Value of the metric whose label contains `needle`. */
function metricValue(result, needle) {
  return result.metrics.find((m) => m.label.includes(needle))?.value;
}

describe('SITE_FIELDS', () => {
  test('covers every advisor need with at least one required field', () => {
    for (const need of ADVISOR_NEEDS) {
      const fields = SITE_FIELDS[need.id];
      expect(fields, need.id).toBeTruthy();
      expect(fields.some((f) => f.required)).toBe(true);
    }
  });

  test('select fields carry options', () => {
    for (const need of ADVISOR_NEEDS) {
      for (const field of siteFieldsFor(need.id)) {
        if (field.type === 'select') expect(field.options?.length).toBeGreaterThan(1);
      }
    }
  });
});

describe('hasRequiredSiteInputs', () => {
  test('false until the required field has a positive value', () => {
    expect(hasRequiredSiteInputs('agriculture', {})).toBe(false);
    expect(hasRequiredSiteInputs('agriculture', { irrigated_area_ha: 0 })).toBe(false);
    expect(hasRequiredSiteInputs('agriculture', { irrigated_area_ha: 4 })).toBe(true);
  });
});

describe('computeSiteMetrics — agriculture', () => {
  const snapshot = { satellite: [{ month: '2026-06', precipitation: 50 }] };

  test('computes demand, gross abstraction and drip saving from area/crop/method', () => {
    const result = computeSiteMetrics(
      'agriculture',
      { irrigated_area_ha: 4, crop: 'rice', irrigation_method: 'flood' },
      snapshot,
    );
    // net = 4 ha * 200 mm * 10 = 8000 m3/mo; gross = 8000 / 0.45 = 17778.
    expect(metricValue(result, 'Crop water demand')).toBe(8000);
    expect(metricValue(result, 'Gross abstraction')).toBe(17778);
    // drip gross = 8000 / 0.9 = 8889; saving = 17778 - 8889 ≈ 8889.
    expect(metricValue(result, 'drip')).toBeCloseTo(8889, 0);
    // rainfall (50 mm) covers 2000 / 8000 = 25% of demand.
    expect(metricValue(result, 'Rainfall covers')).toBe(25);
  });

  test('returns null without the required area', () => {
    expect(computeSiteMetrics('agriculture', { crop: 'rice' }, snapshot)).toBeNull();
  });

  test('flags reported usage against estimated need when provided', () => {
    const result = computeSiteMetrics(
      'agriculture',
      { irrigated_area_ha: 4, crop: 'rice', irrigation_method: 'flood', monthly_volume_m3: 20000 },
      snapshot,
    );
    // 20000 / 17778 ≈ 112.5% -> within the matched band.
    expect(metricValue(result, 'Reported vs estimated')).toBeCloseTo(113, 0);
  });
});

describe('computeSiteMetrics — urban', () => {
  test('derives demand, leakage loss and storage cover', () => {
    const result = computeSiteMetrics('urban_supply', {
      population_served: 5000,
      per_capita_lpd: 120,
      leakage_pct: 25,
      storage_m3: 400,
    });
    // 5000 * 120 / 1000 = 600 m3/d delivered; gross = 600 / 0.75 = 800; loss = 200.
    expect(metricValue(result, 'Daily demand')).toBe(600);
    expect(metricValue(result, 'Gross abstraction')).toBe(800);
    expect(metricValue(result, 'Lost to leakage')).toBe(200);
    expect(metricValue(result, 'Storage cover')).toBe(0.5);
  });
});

describe('computeSiteMetrics — industrial', () => {
  test('derives freshwater intake and reuse headroom', () => {
    const result = computeSiteMetrics('industrial', { monthly_volume_m3: 1200, reuse_pct: 10 });
    expect(metricValue(result, 'Freshwater intake')).toBe(1080); // 1200 * 0.9
    expect(metricValue(result, 'Current reuse rate')).toBe(10);
    expect(metricValue(result, 'Extra saving')).toBe(480); // (50-10)% of 1200
  });
});

describe('computeSiteMetrics — sustainability', () => {
  test('derives abstraction and a 15% conservation target', () => {
    const result = computeSiteMetrics('water_sustainability', { monthly_volume_m3: 800 });
    expect(metricValue(result, 'Monthly abstraction')).toBe(800);
    expect(metricValue(result, 'Conservation target')).toBe(120); // 15% of 800
    expect(result.comparison.bars.find((b) => b.label.includes('Target')).value).toBe(680);
  });
});

describe('summaryForAi', () => {
  test('every populated result carries a non-empty AI summary string', () => {
    const result = computeSiteMetrics('industrial', { monthly_volume_m3: 1200, reuse_pct: 10 });
    expect(typeof result.summaryForAi).toBe('string');
    expect(result.summaryForAi.length).toBeGreaterThan(10);
  });
});
