export type IntensityCategory =
  | 'compound_heavy'
  | 'compound_moderate'
  | 'isolation';

export type ExerciseType = 'compound' | 'isolation';

export type MuscleRole = 'prime_mover' | 'synergist' | 'stabilizer';

export type MuscleTarget = {
  name: string;
  role: MuscleRole;
};

export type MuscleActivation = {
  id: number;
  name: string;
  displayName: string;
  activationPercent: number;
};

export type Exercise = {
  id: number;
  name: string;
  equipment: string;
  muscles: MuscleActivation[];
  injuryRiskLevel: number;
  jointStressAreas: string[];
  movementPattern: string;
  exerciseType: ExerciseType;
  complexityScore: number;
};

export type MatchDetails = {
  muscleSimilarity: number;
  movementPatternMatch: number;
  exerciseTypeMatch: number;
  complexitySimilarity: number;
  patternSimilarity: number;
  modifierMatch: number;
  hierarchyDistance: number;
};

export type SubstitutionResult = {
  exercise: Exercise;
  similarityScore: number;
  reason: string;
  matchDetails: MatchDetails;
};
