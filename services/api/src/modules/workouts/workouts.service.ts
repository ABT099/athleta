import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import { workoutDayExercises, exercises } from 'src/db/schema';
import { eq, and } from 'drizzle-orm';

@Injectable()
export class WorkoutsService {
  constructor(@Inject(DRIZZLE) private readonly db: DrizzleDB) {}

  async substituteExercise(
    workoutDayId: number,
    exerciseId: number,
    substituteExerciseId: number,
  ): Promise<void> {
    // Verify workout day exercise exists
    const workoutExercise = await this.db.query.workoutDayExercises.findFirst({
      where: and(
        eq(workoutDayExercises.workoutDayId, workoutDayId),
        eq(workoutDayExercises.exerciseId, exerciseId),
      ),
    });

    if (!workoutExercise) {
      throw new NotFoundException(
        `Exercise ${exerciseId} not found in workout day ${workoutDayId}`,
      );
    }

    // Verify substitute exercise exists
    const substituteExercise = await this.db.query.exercises.findFirst({
      where: eq(exercises.id, substituteExerciseId),
    });

    if (!substituteExercise) {
      throw new NotFoundException(
        `Substitute exercise ${substituteExerciseId} not found`,
      );
    }

    // Update the exercise ID, keeping all other parameters
    await this.db
      .update(workoutDayExercises)
      .set({ exerciseId: substituteExerciseId })
      .where(eq(workoutDayExercises.id, workoutExercise.id));
  }
}
