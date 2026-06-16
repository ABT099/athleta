import { IsInt, IsOptional, IsString } from 'class-validator';

export class UpdateWorkoutDayDto {
  @IsOptional()
  @IsString()
  name?: string;

  @IsOptional()
  @IsInt()
  dayOfWeek?: number;

  @IsOptional()
  @IsInt()
  orderInWeek?: number;
}
