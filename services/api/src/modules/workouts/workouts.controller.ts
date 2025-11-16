import {
  Controller,
  Put,
  Param,
  ParseIntPipe,
  Body,
} from '@nestjs/common';
import { WorkoutsService } from './workouts.service';
import { SubstituteExerciseDto } from './dto/substitute-exercise.dto';

@Controller('workout-days')
export class WorkoutsController {
  constructor(private readonly workoutsService: WorkoutsService) {}

  @Put(':workoutDayId/exercises/:exerciseId/substitute')
  async substituteExercise(
    @Param('workoutDayId', ParseIntPipe) workoutDayId: number,
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Body() dto: SubstituteExerciseDto,
  ): Promise<{ message: string }> {
    await this.workoutsService.substituteExercise(
      workoutDayId,
      exerciseId,
      dto.substituteExerciseId,
    );
    return { message: 'Exercise substituted successfully' };
  }
}

