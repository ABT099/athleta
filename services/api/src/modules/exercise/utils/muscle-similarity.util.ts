type MuscleActivation = {
  id: number;
  name: string;
  displayName: string;
  activationPercent: number;
};

export class MuscleSimilarityUtil {
  /**
   * Calculate weighted Jaccard similarity between two muscle activation sets.
   * Uses activation percentages to weight the similarity calculation.
   * Returns a value between 0 (no overlap) and 1 (identical activation patterns).
   */
  static calculateWeightedMuscleSimilarity(
    muscles1: MuscleActivation[],
    muscles2: MuscleActivation[],
  ): number {
    if (muscles1.length === 0 && muscles2.length === 0) {
      return 1.0;
    }
    if (muscles1.length === 0 || muscles2.length === 0) {
      return 0.0;
    }

    // Create maps of muscle name -> activation percentage
    const map1 = new Map(
      muscles1.map((m) => [m.name, m.activationPercent / 100]),
    );
    const map2 = new Map(
      muscles2.map((m) => [m.name, m.activationPercent / 100]),
    );

    // Get all unique muscle names
    const allMuscles = new Set([...map1.keys(), ...map2.keys()]);

    // Calculate weighted Jaccard similarity
    let intersectionSum = 0;
    let unionSum = 0;

    allMuscles.forEach((muscle) => {
      const act1 = map1.get(muscle) || 0;
      const act2 = map2.get(muscle) || 0;
      intersectionSum += Math.min(act1, act2);
      unionSum += Math.max(act1, act2);
    });

    return unionSum === 0 ? 0 : intersectionSum / unionSum;
  }

  /**
   * Legacy method for backward compatibility.
   * Calculate Jaccard similarity between two arrays.
   * @deprecated Use calculateWeightedMuscleSimilarity instead
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
   * Calculate pattern similarity between two exercises based on their biomechanical properties.
   * Returns a score between 0 and 1.
   */
  static calculatePatternSimilarity(
    exercise1: {
      movementPattern: string;
      equipment: string;
      exerciseType: string;
    },
    exercise2: {
      movementPattern: string;
      equipment: string;
      exerciseType: string;
    },
  ): number {
    let score = 0;

    // Same movement pattern: +0.5
    if (exercise1.movementPattern === exercise2.movementPattern) {
      score += 0.5;
    } else if (
      this.areSimilarMovementPatterns(
        exercise1.movementPattern,
        exercise2.movementPattern,
      )
    ) {
      score += 0.3;
    }

    // Same equipment: +0.3
    if (exercise1.equipment === exercise2.equipment) {
      score += 0.3;
    } else if (
      this.areSimilarEquipment(exercise1.equipment, exercise2.equipment)
    ) {
      score += 0.15;
    }

    // Same exercise type: +0.2
    if (exercise1.exerciseType === exercise2.exerciseType) {
      score += 0.2;
    }

    return Math.min(score, 1.0);
  }

  /**
   * Check if two equipment types are similar (e.g., barbell/dumbbell).
   */
  static areSimilarEquipment(equipment1: string, equipment2: string): boolean {
    const similarEquipment: Record<string, string[]> = {
      barbell: ['dumbbell', 'kettlebell'],
      dumbbell: ['barbell', 'kettlebell'],
      kettlebell: ['barbell', 'dumbbell'],
      cable: ['band', 'machine'],
      band: ['cable', 'bodyweight'],
      machine: ['cable'],
    };

    return similarEquipment[equipment1]?.includes(equipment2) ?? false;
  }

  /**
   * Map Neo4j pattern-based similar exercises to a score map.
   * Exercises returned from Neo4j are already scored by relevance.
   */
  static mapPatternMatchesToScores(
    similarExercises: string[],
    limit: number = 20,
  ): Map<string, number> {
    const scoreMap = new Map<string, number>();

    // Score decreases linearly based on position in results
    // First result gets 1.0, last gets 0.5
    similarExercises.slice(0, limit).forEach((exerciseName, index) => {
      const score = 1.0 - index / (limit * 2);
      scoreMap.set(exerciseName, Math.max(score, 0.5));
    });

    return scoreMap;
  }

  /**
   * Generate human-readable reason for substitution recommendation.
   * Enhanced to include pattern-based matching details.
   */
  static generateSubstitutionReason(matchDetails: {
    muscleSimilarity: number;
    movementPatternMatch: number;
    exerciseTypeMatch: number;
    complexitySimilarity: number;
    patternSimilarity?: number;
    modifierMatch?: number;
    hierarchyDistance?: number;
  }): string {
    const reasons: string[] = [];

    if (matchDetails.muscleSimilarity >= 0.8) {
      reasons.push('targets same muscles');
    } else if (matchDetails.muscleSimilarity >= 0.5) {
      reasons.push('targets similar muscles');
    }

    if (matchDetails.movementPatternMatch >= 0.9) {
      reasons.push('similar movement pattern');
    } else if (matchDetails.movementPatternMatch >= 0.7) {
      reasons.push('related movement pattern');
    }

    if (matchDetails.exerciseTypeMatch === 1.0) {
      reasons.push('same exercise type');
    }

    if (matchDetails.complexitySimilarity >= 0.9) {
      reasons.push('similar complexity level');
    }

    // NEW: Pattern-based reasons
    if (
      matchDetails.patternSimilarity &&
      matchDetails.patternSimilarity >= 0.8
    ) {
      reasons.push('biomechanically similar movement');
    }

    if (matchDetails.modifierMatch && matchDetails.modifierMatch >= 0.7) {
      reasons.push('uses similar equipment/setup');
    }

    if (
      matchDetails.hierarchyDistance !== undefined &&
      matchDetails.hierarchyDistance <= 1
    ) {
      reasons.push('variation of same exercise family');
    }

    return reasons.join(', ') || 'suitable alternative';
  }
}
