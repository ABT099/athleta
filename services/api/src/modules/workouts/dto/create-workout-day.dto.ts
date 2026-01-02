import { Type } from 'class-transformer';
import {
  IsArray,
  ValidateNested,
  IsNotEmpty,
  IsString,
  IsNumber,
} from 'class-validator';
import { WorkoutDayDto } from 'src/modules/plans/dto/create-plan.dto';
import { TrainingType } from 'src/constants';

export class CreateWorkoutDayDto {
  @IsNotEmpty()
  @IsNumber()
  workoutPlanId: number;

  @IsNotEmpty()
  @IsString()
  trainingType: TrainingType;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkoutDayDto)
  workoutDay: WorkoutDayDto;
}
