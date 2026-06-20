import { describe, expect, test } from 'vitest';
import {
  currentMonthKey,
  historyTickInterval,
  historyWindow,
  latestMonth,
  monthSequence,
} from './chart.js';

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

describe('currentMonthKey', () => {
  test('formats the local calendar month as YYYY-MM', () => {
    expect(currentMonthKey(new Date(2026, 5, 17))).toBe('2026-06'); // June
    expect(currentMonthKey(new Date(2025, 0, 1))).toBe('2025-01');
    expect(currentMonthKey(new Date(2024, 11, 31))).toBe('2024-12');
  });
});

describe('latestMonth', () => {
  test('returns the most recent month regardless of input order', () => {
    expect(
      latestMonth([{ month: '2024-06' }, { month: '2026-05' }, { month: '2025-01' }]),
    ).toBe('2026-05');
  });

  test('handles a single point', () => {
    expect(latestMonth([{ month: '2026-05' }])).toBe('2026-05');
  });

  test('returns null when there are no points', () => {
    expect(latestMonth([])).toBeNull();
    expect(latestMonth(undefined)).toBeNull();
  });
});

describe('monthSequence', () => {
  test('returns monthsBack + 1 ascending months, inclusive of both ends', () => {
    const seq = monthSequence('2026-06', 24);
    expect(seq).toHaveLength(25);
    expect(seq[0]).toBe('2024-06'); // the "2 years ago" month
    expect(seq[24]).toBe('2026-06'); // the current month
  });

  test('handles year rollover', () => {
    expect(monthSequence('2026-01', 3)).toEqual([
      '2025-10',
      '2025-11',
      '2025-12',
      '2026-01',
    ]);
  });

  test('returns an empty list for a malformed month', () => {
    expect(monthSequence('', 24)).toEqual([]);
    expect(monthSequence(undefined, 24)).toEqual([]);
  });
});

describe('historyWindow', () => {
  test('spans the full window, filling unscored months with null', () => {
    const points = [
      { month: '2026-04', risk: 60 },
      { month: '2026-05', risk: 65 },
    ];
    const win = historyWindow(points, '2026-06', 24);
    expect(win).toHaveLength(25);
    expect(win[0]).toEqual({ month: '2024-06', risk: null });
    expect(win.find((d) => d.month === '2026-04').risk).toBe(60);
    expect(win.find((d) => d.month === '2026-05').risk).toBe(65);
    // current month not scored yet -> trailing gap, exactly as requested
    expect(win.find((d) => d.month === '2026-06').risk).toBeNull();
  });

  test('drops observations older than the window', () => {
    const win = historyWindow([{ month: '2023-01', risk: 99 }], '2026-06', 24);
    expect(win.some((d) => d.month === '2023-01')).toBe(false);
    expect(win.every((d) => d.risk === null)).toBe(true);
  });

  test('tolerates missing points', () => {
    expect(historyWindow(undefined, '2026-06', 1)).toEqual([
      { month: '2026-05', risk: null },
      { month: '2026-06', risk: null },
    ]);
  });
});
