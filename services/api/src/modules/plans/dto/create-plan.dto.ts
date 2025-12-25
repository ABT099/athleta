import {
  IsArray,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  ValidateNested,
  IsNumber,
} from 'class-validator';
import { Type } from 'class-transformer';
import { PeriodizationModel, TrainingType } from 'src/constants';

export class WorkoutExerciseDto {
  @IsNotEmpty()
  @IsString()
  name: string;

  @IsNotEmpty()
  @IsInt()
  targetSetsMin: number;

  @IsOptional()
  @IsInt()
  targetSetsMax?: number;

  @IsNotEmpty()
  @IsInt()
  targetRepsMin: number;

  @IsOptional()
  @IsInt()
  targetRepsMax?: number;

  @IsNotEmpty()
  @IsInt()
  orderInWorkout: number;

  @IsOptional()
  @IsString()
  notes?: string;
}

export class WorkoutDayDto {
  @IsNotEmpty()
  @IsString()
  name: string;

  @IsNotEmpty()
  @IsNumber()
  dayOfWeek: number;

  @IsNotEmpty()
  @IsInt()
  orderInWeek: number;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkoutExerciseDto)
  exercises: WorkoutExerciseDto[];
}

export class CreatePlanDto {
  @IsNotEmpty()
  @IsString()
  name: string;

  @IsNotEmpty()
  @IsString()
  description: string;

  @IsNotEmpty()
  @IsEnum(TrainingType)
  trainingType: TrainingType;

  @IsNotEmpty()
  @IsEnum(PeriodizationModel)
  periodizationModel: PeriodizationModel;

  @IsNotEmpty()
  @IsInt()
  frequency: number;

  @IsNotEmpty()
  @IsInt()
  durationWeeks: number;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  focusAreas?: string[];

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkoutDayDto)
  workoutDays: WorkoutDayDto[];
}
