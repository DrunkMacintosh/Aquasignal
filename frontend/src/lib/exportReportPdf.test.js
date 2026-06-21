import { describe, expect, test } from 'vitest';
import { exportReportPdf } from './exportReportPdf.js';

describe('exportReportPdf', () => {
  test('is a no-op (no throw) when given no node', () => {
    // Guards against SSR / missing DOM; in the node test env `document` is
    // undefined, so this must return before touching it.
    expect(() => exportReportPdf(null, 'x')).not.toThrow();
    expect(() => exportReportPdf(undefined)).not.toThrow();
  });
});
