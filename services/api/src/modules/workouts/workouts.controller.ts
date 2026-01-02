import {
  Controller,
  Put,
  Param,
  ParseIntPipe,
  Body,
  Get,
} from '@nestjs/common';
import { WorkoutsService } from './workouts.service';
import { SubstituteExerciseDto } from './dto/substitute-exercise.dto';
import { UpdateWorkoutDayExerciseDto } from './dto/update-workout-day-exercises.dto';
import { jsDayToDayOfWeek } from 'src/constants';
import { CurrentUser } from 'src/decorators/user.decorator';

@Controller('workouts')
export class WorkoutsController {
  constructor(private readonly workoutsService: WorkoutsService) {}

  @Put(':workoutDayId/exercises/:exerciseId/substitute')
  async substituteExercise(
    @Param('workoutDayId', ParseIntPipe) workoutDayId: number,
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Body() dto: SubstituteExerciseDto,
  ): Promise<void> {
    await this.workoutsService.substituteExercise(
      workoutDayId,
      exerciseId,
      dto.substituteExerciseId,
    );
  }

  @Put(':workoutDayId/exercises')
  async updateWorkoutDayExercise(
    @Param('workoutDayId', ParseIntPipe) workoutDayId: number,
    @Body() dto: UpdateWorkoutDayExerciseDto,
  ): Promise<void> {
    return await this.workoutsService.updateWorkoutDayExercise(
      workoutDayId,
      dto.exercisesToRemove,
      dto.exercisesToAdd,
    );
  }

  @Get('current')
  async getCurrentWorkoutDay(@CurrentUser() user) {
    const jsDay = new Date().getDay();
    const currentDayOfWeek = jsDayToDayOfWeek(jsDay);
    return await this.workoutsService.getCurrentWorkoutDay(
      user.id,
      currentDayOfWeek,
    );
  }
}
