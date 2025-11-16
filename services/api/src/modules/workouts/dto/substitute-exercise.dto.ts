import { IsNumber } from 'class-validator';

export class SubstituteExerciseDto {
  @IsNumber()
  substituteExerciseId: number;
}

