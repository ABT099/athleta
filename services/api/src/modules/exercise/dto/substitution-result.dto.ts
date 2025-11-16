export class MatchDetailsDto {
  primaryMuscleOverlap: number;
  movementPatternMatch: number;
  exerciseTypeMatch: number;
  secondaryMuscleOverlap: number;
  complexitySimilarity: number;
}

export class ExerciseDto {
  id: number;
  name: string;
  description: string;
  equipment: string;
  primaryMuscles: string[];
  secondaryMuscles: string[];
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

