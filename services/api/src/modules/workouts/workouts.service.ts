import { Injectable, NotFoundException, Inject, Logger } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import {
  workoutDayExercises,
  exercises,
  workoutDays,
  workoutPlans,
} from 'src/db/schema';
import { eq, and, inArray, sql } from 'drizzle-orm';
import { WorkoutExerciseDto } from '../plans/dto/create-plan.dto';
import { ExerciseService } from '../exercise/exercise.service';
import { MuscleImageIntegration } from 'src/integrations/muscle-image.integration';
import {
  AIEngineIntegration,
  type PrescriptionRequestDto,
} from 'src/integrations/ai-engine.integration';
import { DayOfWeek } from 'src/constants';

@Injectable()
export class WorkoutsService {
  private readonly logger = new Logger(WorkoutsService.name);

  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly exerciseService: ExerciseService,
    private readonly muscleImageIntegration: MuscleImageIntegration,
    private readonly AIEngineIntegration: AIEngineIntegration,
  ) {}

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

  async getCurrentWorkoutDay(athleteId: number, dayOfWeek: DayOfWeek) {
    const currentWorkoutDay = await this.db
      .select({
        id: workoutDays.id,
        workoutPlanId: workoutDays.workoutPlanId,
        name: workoutDays.name,
        dayOfWeek: workoutDays.dayOfWeek,
        orderInWeek: workoutDays.orderInWeek,
        muscleImageUrl: workoutDays.muscleImageUrl,
      })
      .from(workoutDays)
      .innerJoin(workoutPlans, eq(workoutDays.workoutPlanId, workoutPlans.id))
      .where(
        and(
          eq(workoutDays.dayOfWeek, dayOfWeek),
          eq(workoutPlans.athleteId, athleteId),
          eq(workoutPlans.isActive, true),
        ),
      )
      .limit(1);

    if (!currentWorkoutDay || currentWorkoutDay.length === 0) {
      throw new NotFoundException(
        `Workout day for day of week ${dayOfWeek} not found for active plan`,
      );
    }

    return currentWorkoutDay[0];
  }

  async updateWorkoutDayExercise(
    workoutDayId: number,
    exercisesToRemove: number[],
    exercisesToAdd: WorkoutExerciseDto[],
  ): Promise<void> {
    if (exercisesToAdd.length === 0 && exercisesToRemove.length === 0) {
      return;
    }

    const allExerciseNames = exercisesToAdd.map((exercise) => exercise.name);

    const exercisesWithMuscles =
      await this.exerciseService.batchUpsertExercises(allExerciseNames);

    // Store full exercise data for prescription generation
    const exerciseDataMap = new Map(
      exercisesWithMuscles.map((ex, index) => [
        allExerciseNames[index].toLowerCase(),
        ex,
      ]),
    );

    const musclesWithRoles: Array<{ name: string; role: string }> = [];

    for (const exercise of exercisesToAdd) {
      const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
      if (exerciseData) {
        for (const muscle of exerciseData.muscles) {
          musclesWithRoles.push(muscle);
        }
      }
    }

    // Get workout plan's training type via workout day
    const workoutDayData = await this.db
      .select({
        workoutPlanId: workoutDays.workoutPlanId,
      })
      .from(workoutDays)
      .where(eq(workoutDays.id, workoutDayId))
      .limit(1);

    if (!workoutDayData || workoutDayData.length === 0) {
      throw new NotFoundException(`Workout day ${workoutDayId} not found`);
    }

    const workoutPlanData = await this.db
      .select({
        trainingType: workoutPlans.trainingType,
      })
      .from(workoutPlans)
      .where(eq(workoutPlans.id, workoutDayData[0].workoutPlanId))
      .limit(1);

    if (!workoutPlanData || workoutPlanData.length === 0) {
      throw new NotFoundException(
        `Workout plan not found for workout day ${workoutDayId}`,
      );
    }

    const trainingType = workoutPlanData[0].trainingType;

    // Get current exercise count to calculate total exercises
    const existingExercisesCount = await this.db
      .select({ count: sql<number>`count(*)` })
      .from(workoutDayExercises)
      .where(eq(workoutDayExercises.workoutDayId, workoutDayId));

    const totalExercises =
      Number(existingExercisesCount[0]?.count ?? 0) -
      exercisesToRemove.length +
      exercisesToAdd.length;

    // Prepare prescription requests for batch processing
    const prescriptionRequests: PrescriptionRequestDto[] = [];

    const exerciseMetadata = exercisesToAdd.map((exercise) => {
      const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
      if (!exerciseData) {
        throw new Error(`Exercise data not found for: ${exercise.name}`);
      }

      // Determine if this exercise is primary
      const isPrimary = ExerciseService.determineIsPrimary(
        exerciseData.intensityCategory,
        exercise.orderInWorkout,
        totalExercises,
      );

      prescriptionRequests.push({
        intensityCategory: exerciseData.intensityCategory,
        trainingType: trainingType,
        trainingPhase: 'accumulation', // Default phase
        weekInPhase: 1, // Week 1
        isPrimary: isPrimary,
      });

      return {
        exercise,
        exerciseData,
        isPrimary,
      };
    });

    // Generate all prescriptions in one batch request
    const prescriptions =
      exercisesToAdd.length > 0
        ? await this.AIEngineIntegration.generateBatchPrescriptions(
            prescriptionRequests,
          )
        : [];

    // Validate response length matches request length
    if (
      exercisesToAdd.length > 0 &&
      prescriptions.length !== prescriptionRequests.length
    ) {
      throw new Error(
        `Prescription API returned ${prescriptions.length} prescriptions but expected ${prescriptionRequests.length}`,
      );
    }

    // Move everything into the transaction
    await this.db.transaction(async (tx) => {
      // Delete inside transaction
      if (exercisesToRemove.length > 0) {
        await tx
          .delete(workoutDayExercises)
          .where(inArray(workoutDayExercises.id, exercisesToRemove));
      }

      // Batch insert all exercises at once with prescriptions
      if (exercisesToAdd.length > 0) {
        const exerciseValues = exerciseMetadata.map((meta, index) => ({
          workoutDayId,
          exerciseId: meta.exerciseData.id,
          orderInWorkout: meta.exercise.orderInWorkout,
          targetSetsMin: meta.exercise.targetSetsMin,
          targetSetsMax:
            meta.exercise.targetSetsMax ?? meta.exercise.targetSetsMin,
          targetRepsMin: meta.exercise.targetRepsMin,
          targetRepsMax:
            meta.exercise.targetRepsMax ?? meta.exercise.targetRepsMin,
          targetRpe: prescriptions[index].target_rpe,
          targetRir: prescriptions[index].target_rir,
          restPeriodSeconds: prescriptions[index].rest_period_seconds,
          notes: meta.exercise.notes ?? null,
          isPrimary: meta.isPrimary,
          warmUpSets: 0,
        }));

        await tx.insert(workoutDayExercises).values(exerciseValues);
      }
    });

    // Move image generation outside transaction to avoid holding it open
    if (exercisesToAdd.length > 0) {
      await this.generateMuscleImagesForWorkoutDay([
        { id: workoutDayId, muscles: musclesWithRoles },
      ]);
    }
  }

  async generateMuscleImagesForWorkoutDay(
    workoutDaysData: Array<{
      id: number;
      muscles: Array<{ name: string; role: string }>;
    }>,
  ): Promise<void> {
    if (!workoutDaysData || workoutDaysData.length === 0) {
      this.logger.warn('No workout days provided for muscle image generation');
      return;
    }

    this.logger.log(
      `Generating muscle images for ${workoutDaysData.length} workout days`,
    );

    // Generate all images in parallel
    const imageGenerationPromises = workoutDaysData.map(
      async (workoutDayData) => {
        try {
          const muscleImageUrl =
            await this.muscleImageIntegration.generateAndSaveImage(
              workoutDayData.id,
              workoutDayData.muscles,
            );

          // Update workout day with image URL
          await this.db
            .update(workoutDays)
            .set({ muscleImageUrl })
            .where(eq(workoutDays.id, workoutDayData.id));

          this.logger.log(
            `Successfully generated muscle image for workout day ${workoutDayData.id}`,
          );
        } catch (error) {
          // Log error but don't fail the entire batch if one image generation fails
          this.logger.error(
            `Failed to generate muscle image for workout day ${workoutDayData.id}:`,
            error,
          );
        }
      },
    );

    // Wait for all image generations to complete (or fail)
    await Promise.allSettled(imageGenerationPromises);

    this.logger.log('Completed batch muscle image generation');
  }
}
