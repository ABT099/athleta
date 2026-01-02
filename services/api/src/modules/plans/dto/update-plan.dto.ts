import { Type } from 'class-transformer';
import {
  IsArray,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  ValidateNested,
} from 'class-validator';
import { PeriodizationModel, TrainingType } from 'src/constants';
import { WorkoutDayDto } from './create-plan.dto';

export class UpdatePlanDto {
  @IsNotEmpty()
  @IsString()
  name: string;

  @IsOptional()
  @IsString()
  description?: string;

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

  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkoutDayDto)
  workoutDaysToAdd?: WorkoutDayDto[];

  @IsOptional()
  @IsArray()
  @IsInt({ each: true })
  workoutDaysToRemove?: number[];
}
