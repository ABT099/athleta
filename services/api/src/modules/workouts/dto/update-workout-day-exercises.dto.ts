import { WorkoutExerciseDto } from 'src/modules/plans/dto/create-plan.dto';
import { IsArray, IsNumber, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';

export class UpdateWorkoutDayExerciseDto {
  @IsArray()
  @IsNumber({}, { each: true })
  exercisesToRemove: number[];

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkoutExerciseDto)
  exercisesToAdd: WorkoutExerciseDto[];
}
