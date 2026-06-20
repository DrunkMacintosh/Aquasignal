import { describe, expect, test } from 'vitest';
import { ADVISOR_NEEDS } from './advisor.js';
import { manifestForNeed, normalizeAllocation, REPORT_MANIFEST } from './reportManifest.js';

describe('REPORT_MANIFEST', () => {
  test('covers every advisor need with a label, lede and sections', () => {
    for (const need of ADVISOR_NEEDS) {
      const manifest = REPORT_MANIFEST[need.id];
      expect(manifest, `manifest for ${need.id}`).toBeTruthy();
      expect(manifest.label).toBeTruthy();
      expect(manifest.lede).toBeTruthy();
      expect(manifest.sections.length).toBeGreaterThan(0);
    }
  });

  test('every section has a known key and a valid source', () => {
    const knownKeys = new Set([
      'trajectory', 'kpis', 'allocation', 'waterBalance', 'recharge', 'drivers', 'priorityActions',
    ]);
    for (const need of ADVISOR_NEEDS) {
      for (const section of REPORT_MANIFEST[need.id].sections) {
        expect(knownKeys.has(section.key), `${need.id}:${section.key}`).toBe(true);
        expect(['grounded', 'ai']).toContain(section.source);
        expect(section.title).toBeTruthy();
      }
    }
  });

  test('every need leads with the grounded risk trajectory', () => {
    // The real-data trajectory anchors the report before any AI estimate.
    for (const need of ADVISOR_NEEDS) {
      expect(REPORT_MANIFEST[need.id].sections[0].key).toBe('trajectory');
    }
  });

  test('needs differ in their section ordering (adaptive per-need)', () => {
    const order = (id) => REPORT_MANIFEST[id].sections.map((s) => s.key).join(',');
    expect(order('agriculture')).not.toBe(order('urban_supply'));
  });

  test('manifestForNeed falls back to sustainability for an unknown need', () => {
    expect(manifestForNeed('mining')).toBe(REPORT_MANIFEST.water_sustainability);
  });
});

describe('normalizeAllocation', () => {
  test('rescales positive slices to sum ~100', () => {
    const out = normalizeAllocation([
      { label: 'A', percent: 30 },
      { label: 'B', percent: 30 },
      { label: 'C', percent: 60 }, // raw total 120
    ]);
    const total = out.reduce((sum, s) => sum + s.percent, 0);
    expect(total).toBeCloseTo(100, 5);
    expect(out.find((s) => s.label === 'C').percent).toBeCloseTo(50, 5);
  });

  test('drops non-positive slices', () => {
    const out = normalizeAllocation([
      { label: 'A', percent: 80 },
      { label: 'B', percent: 0 },
      { label: 'C', percent: -10 },
    ]);
    expect(out.map((s) => s.label)).toEqual(['A']);
    expect(out[0].percent).toBeCloseTo(100, 5);
  });

  test('returns [] when there is nothing positive to show', () => {
    expect(normalizeAllocation([])).toEqual([]);
    expect(normalizeAllocation([{ label: 'x', percent: 0 }])).toEqual([]);
    expect(normalizeAllocation()).toEqual([]);
  });
});
