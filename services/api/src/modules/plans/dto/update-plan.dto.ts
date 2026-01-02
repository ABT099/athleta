import {
  IsArray,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
} from 'class-validator';
import { PeriodizationModel, TrainingType } from 'src/constants';

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
}
