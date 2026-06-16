import { IntensityCategory } from '../exercise/exercise.types';

/**
 * Determine if an exercise should be primary or accessory based on training science.
 *
 * Scientific basis:
 * - Compound Heavy exercises have very high CNS demand → Primary when performed early
 * - Compound Moderate exercises have moderate CNS demand → Primary in first half
 * - Isolation exercises have low CNS demand → Typically accessory
 * - First 2-3 exercises should be primary (neurological freshness critical)
 *
 * This is workout-composition logic (it reasons about position within a
 * workout), which is why it lives here and not in the exercise service.
 *
 * @param intensityCategory - Exercise intensity category (compound_heavy/moderate/isolation)
 * @param orderInWorkout - Position in workout (1-indexed)
 * @param totalExercises - Total number of exercises in the workout
 * @returns true if exercise should be primary, false if accessory
 */
export function determineIsPrimary(
  intensityCategory: IntensityCategory,
  orderInWorkout: number,
  totalExercises: number,
): boolean {
  // With 1-2 exercises, all are primary
  if (totalExercises <= 2) {
    return true;
  }

  // First 3 exercises are always primary (CNS freshness critical)
  if (orderInWorkout <= 3) {
    return true;
  }

  const relativePosition = orderInWorkout / totalExercises;

  switch (intensityCategory) {
    case 'compound_heavy':
      // Compound heavy in first 60% → Primary
      return relativePosition <= 0.6;

    case 'compound_moderate':
      // Compound moderate in first 40% → Primary
      return relativePosition <= 0.4;

    case 'isolation':
      // Isolation exercises are typically accessory
      return false;

    default:
      // Conservative default: treat as accessory
      return false;
  }
}
