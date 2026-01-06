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
