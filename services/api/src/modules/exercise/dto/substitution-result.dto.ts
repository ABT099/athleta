export class MatchDetailsDto {
  muscleSimilarity: number; // Weighted similarity based on activation percentages
  movementPatternMatch: number;
  exerciseTypeMatch: number;
  complexitySimilarity: number;
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
