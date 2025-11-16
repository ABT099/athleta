export class MuscleSimilarityUtil {
  /**
   * Calculate Jaccard similarity between two arrays.
   * Returns a value between 0 (no overlap) and 1 (identical sets).
   */
  static calculateJaccardSimilarity(
    array1: string[],
    array2: string[],
  ): number {
    if (array1.length === 0 && array2.length === 0) {
      return 1.0;
    }
    if (array1.length === 0 || array2.length === 0) {
      return 0.0;
    }

    const set1 = new Set(array1);
    const set2 = new Set(array2);
    const intersection = new Set([...set1].filter((x) => set2.has(x)));
    const union = new Set([...set1, ...set2]);

    return union.size === 0 ? 0 : intersection.size / union.size;
  }

  /**
   * Check if two movement patterns are similar.
   */
  static areSimilarMovementPatterns(
    pattern1: string,
    pattern2: string,
  ): boolean {
    if (pattern1 === pattern2) {
      return true;
    }

    const similarPatterns: Record<string, string[]> = {
      horizontal_push: ['vertical_push', 'push'],
      vertical_push: ['horizontal_push', 'push'],
      horizontal_pull: ['vertical_pull', 'pull'],
      vertical_pull: ['horizontal_pull', 'pull'],
      squat: ['lunge', 'leg_press'],
      hinge: ['deadlift', 'romanian_deadlift'],
      lunge: ['squat', 'split_squat'],
      deadlift: ['hinge', 'romanian_deadlift'],
      romanian_deadlift: ['hinge', 'deadlift'],
    };

    return similarPatterns[pattern1]?.includes(pattern2) ?? false;
  }

  /**
   * Generate human-readable reason for substitution recommendation.
   */
  static generateSubstitutionReason(matchDetails: {
    primaryMuscleOverlap: number;
    movementPatternMatch: number;
    exerciseTypeMatch: number;
    secondaryMuscleOverlap: number;
    complexitySimilarity: number;
  }): string {
    const reasons: string[] = [];

    if (matchDetails.primaryMuscleOverlap >= 0.8) {
      reasons.push('targets same primary muscles');
    } else if (matchDetails.primaryMuscleOverlap >= 0.5) {
      reasons.push('targets similar primary muscles');
    }

    if (matchDetails.movementPatternMatch >= 0.9) {
      reasons.push('similar movement pattern');
    } else if (matchDetails.movementPatternMatch >= 0.7) {
      reasons.push('related movement pattern');
    }

    if (matchDetails.exerciseTypeMatch === 1.0) {
      reasons.push('same exercise type');
    }

    if (matchDetails.secondaryMuscleOverlap >= 0.7) {
      reasons.push('similar secondary muscle involvement');
    }

    if (matchDetails.complexitySimilarity >= 0.9) {
      reasons.push('similar complexity level');
    }

    return reasons.join(', ') || 'suitable alternative';
  }
}

