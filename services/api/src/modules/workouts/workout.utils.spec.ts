import { determineIsPrimary } from './workout.utils';
import { IntensityCategory } from '../exercise/exercise.types';

describe('determineIsPrimary', () => {
  it('treats every exercise as primary when there are 1-2 exercises', () => {
    expect(determineIsPrimary('isolation', 1, 1)).toBe(true);
    expect(determineIsPrimary('isolation', 2, 2)).toBe(true);
    expect(determineIsPrimary('compound_heavy', 2, 2)).toBe(true);
  });

  it('always marks the first three exercises as primary (CNS freshness)', () => {
    expect(determineIsPrimary('isolation', 1, 10)).toBe(true);
    expect(determineIsPrimary('isolation', 2, 10)).toBe(true);
    expect(determineIsPrimary('isolation', 3, 10)).toBe(true);
  });

  describe('beyond the first three, classification depends on intensity + position', () => {
    it('compound_heavy is primary within the first 60% of the workout', () => {
      // 6/10 = 0.6 → primary (boundary inclusive)
      expect(determineIsPrimary('compound_heavy', 6, 10)).toBe(true);
      // 7/10 = 0.7 → accessory
      expect(determineIsPrimary('compound_heavy', 7, 10)).toBe(false);
    });

    it('compound_moderate is primary within the first 40% of the workout', () => {
      // 4/10 = 0.4 → primary (boundary inclusive)
      expect(determineIsPrimary('compound_moderate', 4, 10)).toBe(true);
      // 5/10 = 0.5 → accessory
      expect(determineIsPrimary('compound_moderate', 5, 10)).toBe(false);
    });

    it('isolation is always accessory past the first three', () => {
      expect(determineIsPrimary('isolation', 4, 10)).toBe(false);
      expect(determineIsPrimary('isolation', 5, 10)).toBe(false);
    });

    it('falls back to accessory for an unknown category', () => {
      expect(
        determineIsPrimary('unknown' as IntensityCategory, 4, 10),
      ).toBe(false);
    });
  });
});
