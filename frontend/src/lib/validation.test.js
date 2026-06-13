import { describe, expect, test } from 'vitest';
import { passwordIssue } from './validation.js';

describe('passwordIssue', () => {
  test('accepts a matching pair that satisfies the policy', () => {
    expect(passwordIssue('correct horse battery', 'correct horse battery')).toBeNull();
  });

  test('rejects passwords under 12 characters', () => {
    expect(passwordIssue('short1!', 'short1!')).toMatch(/at least 12/);
  });

  test('rejects passwords over 72 bytes even when under 72 characters', () => {
    // 30 three-byte characters = 90 bytes but only 30 characters.
    const multibyte = 'ま'.repeat(30);
    expect(passwordIssue(multibyte, multibyte)).toMatch(/72-byte/);
  });

  test('rejects a non-matching confirmation', () => {
    expect(passwordIssue('correct horse battery', 'correct horse buttery')).toMatch(
      /do not match/,
    );
  });

  test('checks length before the match, so typos surface one at a time', () => {
    expect(passwordIssue('short', 'different')).toMatch(/at least 12/);
  });
});
