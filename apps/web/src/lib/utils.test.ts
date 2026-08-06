import { describe, it, expect } from 'vitest';
import { cn } from './utils';
describe('cn utility', () => {
  it('merges tailwind classes correctly', () => {
    expect(cn('bg-red-500', 'bg-blue-500')).toBe('bg-blue-500');
    expect(cn('p-4', { 'm-4': true, 'm-2': false })).toBe('p-4 m-4');
  });
});
