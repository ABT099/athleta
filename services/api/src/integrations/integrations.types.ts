import { TrainingPhase } from 'src/modules/common/common.types';
import { TrainingType } from '../constants';
import { IntensityCategory } from 'src/modules/exercise/exercise.types';

export interface MuscleImageResponse {
  url: string;
}

export interface JointStressProfileDto {
  avoidJoints: string[];
  reason: string;
}

export interface PrescriptionRequestDto {
  intensityCategory: IntensityCategory;
  trainingType: TrainingType;
  trainingPhase: TrainingPhase;
  weekInPhase: number;
  isPrimary: boolean;
}

export interface PrescriptionResponseDto {
  target_rpe: number;
  target_rir: number;
  rest_period_seconds: number;
}

// --- Session analysis (request-push contract to auto-regulation) -----------
// Payload shapes are snake_case to match auto-regulation's pydantic DTOs.

export interface AnalyzeSessionPayload {
  athlete: Record<string, unknown>;
  plan: Record<string, unknown> | null;
  session: Record<string, unknown>;
  recovery: Record<string, unknown> | null;
  personal_records: Record<string, unknown>[];
}

/** A single PR write-back the api persists into exercise_personal_records. */
export interface PrUpdate {
  exercise_id: number;
  pr_type: string; // '1RM' | '3RM' | ... | 'volume' | 'total_reps'
  rep_max?: number;
  old_value: number | null;
  new_value: number;
  improvement: number;
  reps?: number;
  date: string;
  is_new_pr: boolean;
}

export interface AnalyzeSessionResponse {
  session_id: number;
  adjustments: Record<string, unknown>;
  next_workout: Record<string, unknown>;
  performance_analysis: Record<string, unknown>;
  ai_insights: string[];
  pr_updates: { achievements?: string[]; updates: PrUpdate[] };
  calibration_factor: number;
}
