export class MatchDetailsDto {
  // Existing muscle-based metrics
  muscleSimilarity: number; // Weighted similarity based on activation percentages
  movementPatternMatch: number;
  exerciseTypeMatch: number;
  complexitySimilarity: number;

  // NEW: Pattern-based metrics from Neo4j
  patternSimilarity?: number; // Biomechanical pattern similarity (0-1)
  modifierMatch?: number; // Equipment/angle/laterality match (0-1)
  hierarchyDistance?: number; // Distance in Neo4j exercise tree
}

export class MuscleActivationDto {
  id: number;
  name: string;
  displayName: string;
  activationPercent: number;
}

export class ExerciseDto {
  id: number;
  name: string;
  description: string;
  equipment: string;
  muscles: MuscleActivationDto[]; // Replaces primaryMuscles and secondaryMuscles
  injuryRiskLevel: number;
  jointStressAreas: string[];
  movementPattern: string;
  exerciseType: 'compound' | 'isolation';
  complexityScore: number;
}

export class SubstitutionResultDto {
  exercise: ExerciseDto;
  similarityScore: number;
  reason: string;
  matchDetails: MatchDetailsDto;
}
