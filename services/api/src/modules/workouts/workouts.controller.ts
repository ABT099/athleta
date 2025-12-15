import {
  Controller,
  Post,
  Put,
  Param,
  ParseIntPipe,
  Body,
  ParseBoolPipe,
  Query,
} from '@nestjs/common';
import { WorkoutsService } from './workouts.service';
import { SubstituteExerciseDto } from './dto/substitute-exercise.dto';
import { CreateWorkoutDto } from './dto/create-workout.dto';

@Controller('workouts')
export class WorkoutsController {
  constructor(private readonly workoutsService: WorkoutsService) {}

  // @Post()
  // async createWorkout(
  //   @Body() dto: CreateWorkoutDto,
  //   @Query('initialPlan', ParseBoolPipe) initialPlan: boolean,
  // ): Promise<{ message: string }> {
  //   await this.workoutsService.createWorkout();
  //   return { message: 'Workout created successfully' };
  // }

  @Put('days/:workoutDayId/exercises/:exerciseId/substitute')
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
