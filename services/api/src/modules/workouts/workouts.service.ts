import { Injectable, NotFoundException } from '@nestjs/common';
import { eq, and } from 'drizzle-orm';
import * as schema from '../../db/schema';
import { DatabaseService } from '../database/database.service';

@Injectable()
export class WorkoutsService {
  constructor(private readonly databaseService: DatabaseService) {}

  async substituteExercise(
    workoutDayId: number,
    exerciseId: number,
    substituteExerciseId: number,
  ): Promise<void> {
    // Verify workout day exercise exists
    const workoutExercise = await this.databaseService.db.query.workoutDayExercisesTable.findFirst({
      where: and(
        eq(schema.workoutDayExercisesTable.workoutDayId, workoutDayId),
        eq(schema.workoutDayExercisesTable.exerciseId, exerciseId),
      ),
    });

    if (!workoutExercise) {
      throw new NotFoundException(
        `Exercise ${exerciseId} not found in workout day ${workoutDayId}`,
      );
    }

    // Verify substitute exercise exists
    const substituteExercise = await this.databaseService.db.query.exercisesTable.findFirst({
      where: eq(schema.exercisesTable.id, substituteExerciseId),
    });

    if (!substituteExercise) {
      throw new NotFoundException(
        `Substitute exercise ${substituteExerciseId} not found`,
      );
    }

    // Update the exercise ID, keeping all other parameters
    await this.databaseService.db
      .update(schema.workoutDayExercisesTable)
      .set({ exerciseId: substituteExerciseId })
      .where(eq(schema.workoutDayExercisesTable.id, workoutExercise.id));
  }
}

