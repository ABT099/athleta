import { Type } from 'class-transformer';
import {
  IsArray,
  IsInt,
  IsNumber,
  IsObject,
  IsOptional,
  IsString,
  Min,
  ValidateNested,
} from 'class-validator';

export class CompletedSetDto {
  @IsInt()
  exerciseId: number;

  @IsInt()
  @Min(1)
  setNumber: number;

  @IsNumber()
  weight: number;

  @IsInt()
  @Min(0)
  reps: number;

  @IsOptional()
  @IsNumber()
  rpe?: number;

  @IsOptional()
  @IsInt()
  rir?: number;

  @IsOptional()
  @IsString()
  formQuality?: string;

  @IsOptional()
  @IsString()
  setTypeUsed?: string;

  @IsOptional()
  @IsString()
  repStyleUsed?: string;

  @IsOptional()
  @IsObject()
  techniqueDetails?: Record<string, unknown>;

  @IsOptional()
  @IsString()
  notes?: string;
}

export class RecoveryMetricsDto {
  @IsString()
  sleepQuality: string;

  @IsOptional()
  @IsNumber()
  sleepHours?: number;

  @IsOptional()
  @IsInt()
  overallSoreness?: number;

  @IsOptional()
  @IsString()
  muscleSoreness?: string;

  @IsOptional()
  @IsInt()
  stressLevel?: number;

  @IsOptional()
  @IsInt()
  energyLevel?: number;

  @IsOptional()
  @IsString()
  nutritionAdherence?: string;

  @IsOptional()
  @IsString()
  hydrationLevel?: string;

  @IsOptional()
  @IsString()
  notes?: string;
}

export class CompleteWorkoutDto {
  @IsInt()
  workoutDayId: number;

  @IsOptional()
  @IsString()
  sessionDate?: string;

  @IsOptional()
  @IsInt()
  durationMinutes?: number;

  @IsOptional()
  @IsNumber()
  overallRpe?: number;

  @IsOptional()
  @IsString()
  overallFeeling?: string;

  @IsOptional()
  @IsString()
  notes?: string;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => CompletedSetDto)
  exerciseSets: CompletedSetDto[];

  @IsOptional()
  @ValidateNested()
  @Type(() => RecoveryMetricsDto)
  recoveryMetrics?: RecoveryMetricsDto;
}
