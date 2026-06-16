export type IntensityCategory =
  | 'compound_heavy'
  | 'compound_moderate'
  | 'isolation';

export type ExerciseType = 'compound' | 'isolation';

export type MuscleRole = 'prime_mover' | 'synergist' | 'stabilizer';

export type MuscleTarget = {
  name: string;
  displayName: string;
  role: MuscleRole;
  activationPercent: number;
};

export type ExerciseAttributes = {
  equipment: string;
  laterality: string;
  angle: string;
  grip: string;
  tempo: string;
  forceVector: string;
};

export type SafetyProfile = {
  injuryRiskLevel: number;
  complexityScore: number;
  jointStressAreas: string[];
};

export type Exercise = {
  id: number;
  name: string;
  movementPattern: string;
  exerciseType: ExerciseType;
  intensityCategory: IntensityCategory;
  attributes: ExerciseAttributes;
  muscles: MuscleTarget[];
  safety: SafetyProfile;
};

export type ExerciseResolution = 'matched' | 'inferred';

export type InferredExercise = {
  exercise: Exercise;
  requestedName: string;
  resolution: ExerciseResolution;
  confidence: number;
};

export type Substitution = {
  exercise: Exercise;
  score: number;
  reason: string;
};
