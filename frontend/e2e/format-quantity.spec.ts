import { expect, test } from '@playwright/test';

import { formatQuantity } from '../src/domain/format';

test.describe('formatQuantity', () => {
  test('normalizes decimal quantity strings without changing unit text', () => {
    const cases: Array<[string | null | undefined, string]> = [
      ['3.0', '3'],
      ['3.50', '3.5'],
      ['3.00', '3'],
      ['3.5', '3.5'],
      ['32py', '32py'],
      ['4대', '4대'],
      ['3.0대', '3대'],
      ['3.50평', '3.5평'],
      ['', ''],
      [' ', ' '],
      [null, ''],
      [undefined, ''],
    ];

    for (const [input, expected] of cases) {
      expect(formatQuantity(input)).toBe(expected);
    }
  });
});
