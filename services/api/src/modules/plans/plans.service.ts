import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import { PeriodizationModel, TrainingType } from 'src/constants';
import { workoutDays, workoutPlans, workoutDayExercises } from 'src/db/schema';
import { and, asc, eq, inArray } from 'drizzle-orm';
import { ExerciseService } from '../exercise/exercise.service';
import { WorkoutsService } from '../workouts/workouts.service';
import { AIEngineIntegration } from 'src/integrations/ai-engine.integration';
import {
  CreateWorkoutDayInput,
  CreateWorkoutExerciseInput,
} from '../workouts/workout.types';
import { PrescriptionRequestDto } from 'src/integrations/integrations.types';
import {
  ExerciseType,
  IntensityCategory,
  MuscleTarget,
} from '../exercise/exercise.types';

type WorkoutDay = CreateWorkoutDayInput;
type WorkoutExercise = CreateWorkoutExerciseInput;

@Injectable()
export class PlansService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly exerciseService: ExerciseService,
    private readonly workoutsService: WorkoutsService,
    private readonly aiEngineIntegration: AIEngineIntegration,
  ) {}

  async getPlans(athleteId: number) {
    return this.db.query.workoutPlans.findMany({
      where: eq(workoutPlans.athleteId, athleteId),
    });
  }

  async getPlan(athleteId: number, planId: number) {
    const plan = await this.db.query.workoutPlans.findFirst({
      where: and(
        eq(workoutPlans.id, planId),
        eq(workoutPlans.athleteId, athleteId),
      ),
      with: {
        workoutDays: {
          orderBy: [asc(workoutDays.orderInWeek)],
          with: {
            workoutDayExercises: {
              orderBy: [asc(workoutDayExercises.orderInWorkout)],
              with: {
                exercise: true,
              },
            },
          },
        },
      },
    });

    if (!plan) {
      throw new NotFoundException('Plan not found');
    }
    return plan;
  }

  async createPlan(createPlanDto: {
    athleteId: number;
    name: string;
    description?: string;
    trainingType: TrainingType;
    periodizationModel: PeriodizationModel;
    frequency: number;
    durationWeeks: number;
    focusAreas?: string[];
    workoutDays: WorkoutDay[];
  }) {
    const allExerciseNames = createPlanDto.workoutDays.flatMap((workoutDay) =>
      workoutDay.exercises.map((exercise) => exercise.name),
    );

    const exercisesWithMuscles =
      await this.exerciseService.batchUpsertExercises(allExerciseNames);

    // Store full exercise data for prescription generation
    const exerciseDataMap = new Map(
      exercisesWithMuscles.map((ex, index) => [
        allExerciseNames[index].toLowerCase(),
        ex,
      ]),
    );

    // Collect workout day data for batch image generation
    const workoutDaysData: Array<{
      id: number;
      muscles: Array<MuscleTarget>;
    }> = [];

    // Collect all prescription requests for batch processing (before transaction)
    const prescriptionRequests: PrescriptionRequestDto[] = [];

    // Build prescription requests and metadata (before transaction)
    // We need to prepare the requests, but we'll need workoutDayIds from the transaction
    // So we'll build the structure here and populate IDs after insertion
    const exerciseMetadataPreInsert: Array<{
      dayIndex: number;
      exercise: WorkoutExercise;
      exerciseData: {
        id: number;
        name: string;
        intensityCategory: IntensityCategory;
        exerciseType: ExerciseType;
        muscles: Array<MuscleTarget>;
      };
      isPrimary: boolean;
    }> = [];

    for (
      let dayIndex = 0;
      dayIndex < createPlanDto.workoutDays.length;
      dayIndex++
    ) {
      const workoutDay = createPlanDto.workoutDays[dayIndex];
      const totalExercises = workoutDay.exercises.length;

      for (const exercise of workoutDay.exercises) {
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
          trainingType: createPlanDto.trainingType,
          trainingPhase: 'accumulation', // Default phase for new plans
          weekInPhase: 1, // Week 1
          isPrimary: isPrimary,
        });

        exerciseMetadataPreInsert.push({
          dayIndex,
          exercise,
          exerciseData,
          isPrimary,
        });
      }
    }

    // Generate all prescriptions in one batch request (outside transaction)
    const prescriptions =
      await this.aiEngineIntegration.generateBatchPrescriptions(
        prescriptionRequests,
      );

    // Validate response length matches request length
    if (prescriptions.length !== prescriptionRequests.length) {
      throw new Error(
        `Prescription API returned ${prescriptions.length} prescriptions but expected ${prescriptionRequests.length}`,
      );
    }

    await this.db.transaction(async (tx) => {
      await tx
        .update(workoutPlans)
        .set({
          isActive: false,
        })
        .where(eq(workoutPlans.athleteId, createPlanDto.athleteId));

      const workoutPlanId: number = await tx
        .insert(workoutPlans)
        .values({
          athleteId: createPlanDto.athleteId,
          name: createPlanDto.name,
          description: createPlanDto.description ?? null,
          trainingType: createPlanDto.trainingType,
          periodizationModel: createPlanDto.periodizationModel,
          frequency: createPlanDto.frequency,
          durationWeeks: createPlanDto.durationWeeks,
          endDate: new Date(
            new Date().getTime() +
              createPlanDto.durationWeeks * 7 * 24 * 60 * 60 * 1000,
          ).toISOString(),
          focusAreas: createPlanDto.focusAreas,
        })
        .returning({ id: workoutPlans.id })
        .then(([workoutPlan]) => workoutPlan.id);

      const workoutDayValues = createPlanDto.workoutDays.map((workoutDay) => {
        const musclesWithRoles: Array<MuscleTarget> = [];

        for (const exercise of workoutDay.exercises) {
          const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
          if (exerciseData) {
            for (const muscle of exerciseData.muscles) {
              musclesWithRoles.push(muscle);
            }
          }
        }

        // dayOfWeek must be in enum format (0=Monday, 1=Tuesday, ..., 6=Sunday) to match
        // database schema and getCurrentWorkoutDay queries. If frontend uses JavaScript's
        // getDay() (0=Sunday), it must convert using jsDayToDayOfWeek before sending.
        const dayOfWeekValue = workoutDay.dayOfWeek;

        return {
          values: {
            workoutPlanId: workoutPlanId,
            name: workoutDay.name,
            dayOfWeek: dayOfWeekValue,
            orderInWeek: workoutDay.orderInWeek,
            muscleImageUrl: null,
          },
          muscles: musclesWithRoles,
        };
      });

      const insertedWorkoutDays = await tx
        .insert(workoutDays)
        .values(workoutDayValues.map((wd) => wd.values))
        .returning({ id: workoutDays.id });

      // Map the returned IDs to the muscle data
      insertedWorkoutDays.forEach((insertedDay, index) => {
        workoutDaysData.push({
          id: insertedDay.id,
          muscles: workoutDayValues[index].muscles,
        });
      });

      // Map workout day IDs to exercise metadata
      const exerciseMetadata: Array<{
        dayIndex: number;
        workoutDayId: number;
        exercise: WorkoutExercise;
        exerciseData: {
          id: number;
          name: string;
          intensityCategory: IntensityCategory;
          exerciseType: ExerciseType;
          muscles: Array<MuscleTarget>;
        };
        isPrimary: boolean;
      }> = [];

      let prescriptionIndex = 0;
      for (
        let dayIndex = 0;
        dayIndex < insertedWorkoutDays.length;
        dayIndex++
      ) {
        const workoutDayId = insertedWorkoutDays[dayIndex].id;
        const workoutDay = createPlanDto.workoutDays[dayIndex];

        for (let i = 0; i < workoutDay.exercises.length; i++) {
          const preInsertMeta = exerciseMetadataPreInsert[prescriptionIndex];
          exerciseMetadata.push({
            dayIndex,
            workoutDayId,
            exercise: preInsertMeta.exercise,
            exerciseData: preInsertMeta.exerciseData,
            isPrimary: preInsertMeta.isPrimary,
          });
          prescriptionIndex++;
        }
      }

      // Map prescriptions back to exercises and insert
      const allExerciseInserts = exerciseMetadata.map((meta, index) => ({
        workoutDayId: meta.workoutDayId,
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

      // Batch insert all exercises at once
      if (allExerciseInserts.length > 0) {
        await tx.insert(workoutDayExercises).values(allExerciseInserts);
      }
    });

    // Generate muscle images in batch outside transaction
    await this.workoutsService.generateMuscleImagesForWorkoutDay(
      workoutDaysData,
    );
  }

  async updatePlan(
    athleteId: number,
    planId: number,
    fieldsToUpdate: {
      name: string;
      description?: string;
      trainingType: TrainingType;
      periodizationModel: PeriodizationModel;
      workoutDaysToAdd: WorkoutDay[];
      workoutDaysToRemove: number[];
      frequency: number;
      durationWeeks: number;
      focusAreas?: string[];
    },
  ) {
    // Verify the plan exists and belongs to the athlete
    const plan = await this.db.query.workoutPlans.findFirst({
      where: and(
        eq(workoutPlans.id, planId),
        eq(workoutPlans.athleteId, athleteId),
      ),
    });

    if (!plan) {
      throw new NotFoundException('Plan not found');
    }

    // Update plan fields
    await this.db
      .update(workoutPlans)
      .set({
        name: fieldsToUpdate.name,
        description: fieldsToUpdate.description ?? null,
        trainingType: fieldsToUpdate.trainingType,
        periodizationModel: fieldsToUpdate.periodizationModel,
        frequency: fieldsToUpdate.frequency,
        durationWeeks: fieldsToUpdate.durationWeeks,
        focusAreas: fieldsToUpdate.focusAreas,
      })
      .where(
        and(eq(workoutPlans.id, planId), eq(workoutPlans.athleteId, athleteId)),
      );

    // Handle workout days removal
    if (fieldsToUpdate.workoutDaysToRemove.length > 0) {
      // Delete workout days (cascade will handle workout day exercises)
      await this.db
        .delete(workoutDays)
        .where(
          and(
            eq(workoutDays.workoutPlanId, planId),
            inArray(workoutDays.id, fieldsToUpdate.workoutDaysToRemove),
          ),
        );
    }

    // Handle workout days addition
    if (fieldsToUpdate.workoutDaysToAdd.length > 0) {
      await this.workoutsService.createWorkoutDays(
        planId,
        fieldsToUpdate.trainingType,
        fieldsToUpdate.workoutDaysToAdd,
      );
    }
  }

  async deletePlan(athleteId: number, planId: number) {
    await this.db
      .delete(workoutPlans)
      .where(
        and(eq(workoutPlans.id, planId), eq(workoutPlans.athleteId, athleteId)),
      );
  }

  async activatePlan(athleteId: number, planId: number) {
    await this.db.transaction(async (tx) => {
      const planResult = await tx
        .select({ durationWeeks: workoutPlans.durationWeeks })
        .from(workoutPlans)
        .where(
          and(
            eq(workoutPlans.id, planId),
            eq(workoutPlans.athleteId, athleteId),
          ),
        )
        .limit(1);

      if (!planResult || planResult.length === 0) {
        throw new NotFoundException('Plan not found');
      }

      const durationWeeks = planResult[0].durationWeeks;

      await tx
        .update(workoutPlans)
        .set({
          isActive: false,
          endDate: new Date().toISOString(),
        })
        .where(
          and(
            eq(workoutPlans.athleteId, athleteId),
            eq(workoutPlans.isActive, true),
          ),
        );

      await tx
        .update(workoutPlans)
        .set({
          isActive: true,
          startDate: new Date().toISOString(),
          endDate: new Date(
            new Date().getTime() + durationWeeks * 7 * 24 * 60 * 60 * 1000,
          ).toISOString(),
        })
        .where(eq(workoutPlans.id, planId));
    });
  }
}
