import { describe, expect, test } from 'vitest';
import { historyTickInterval } from './chart.js';

describe('historyTickInterval', () => {
  test('labels every point when count fits within the label budget', () => {
    // Arrange / Act / Assert
    expect(historyTickInterval(6)).toBe(0);
    expect(historyTickInterval(8)).toBe(0); // exactly at the budget
  });

  test('thins a 2-year (24-month) history to ~8 labels', () => {
    // 24 points, skip 2 between labels -> a label every 3rd month = 8 labels
    expect(historyTickInterval(24)).toBe(2);
  });

  test('thins a 12-month history to one label every other month', () => {
    expect(historyTickInterval(12)).toBe(1);
  });

  test('respects a custom label budget', () => {
    expect(historyTickInterval(24, 12)).toBe(1);
    expect(historyTickInterval(24, 24)).toBe(0);
  });

  test('handles degenerate inputs without throwing', () => {
    expect(historyTickInterval(0)).toBe(0);
    expect(historyTickInterval(-5)).toBe(0);
    expect(historyTickInterval(Number.NaN)).toBe(0);
  });
});
