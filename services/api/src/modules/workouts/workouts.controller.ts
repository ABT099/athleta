import {
  Controller,
  Put,
  Param,
  ParseIntPipe,
  Body,
  Get,
  Post,
} from '@nestjs/common';
import { WorkoutsService } from './workouts.service';
import { SubstituteExerciseDto } from './dto/substitute-exercise.dto';
import { UpdateWorkoutDayExerciseDto } from './dto/update-workout-day-exercises.dto';
import { jsDayToDayOfWeek } from 'src/constants';
import { CurrentUser } from 'src/decorators/user.decorator';
import { CreateWorkoutDayDto } from './dto/create-workout-day.dto';
import type { CurrentAuthUser } from '../auth/auth.types';

@Controller('workouts')
export class WorkoutsController {
  constructor(private readonly workoutsService: WorkoutsService) {}

  @Post()
  async createWorkoutDay(@Body() dto: CreateWorkoutDayDto): Promise<void> {
    await this.workoutsService.createWorkoutDays(
      dto.workoutPlanId,
      dto.trainingType,
      [dto.workoutDay],
    );
  }

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
  async getCurrentWorkoutDay(@CurrentUser() user: CurrentAuthUser) {
    const jsDay = new Date().getDay();
    const currentDayOfWeek = jsDayToDayOfWeek(jsDay);
    return await this.workoutsService.getCurrentWorkoutDay(
      user.id,
      currentDayOfWeek,
    );
  }
}
