import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import { PeriodizationModel, TrainingType } from 'src/constants';
import { workoutDays, workoutPlans, workoutDayExercises } from 'src/db/schema';
import { and, asc, eq, inArray } from 'drizzle-orm';
import { ExerciseClientService } from '../exercise/exercise-client.service';
import { WorkoutsService } from '../workouts/workouts.service';
import { AthletesService } from '../athletes/athletes.service';
import { AutoRegulationServiceIntegration } from 'src/integrations/auto-regulation-service.integration';
import {
  CreateWorkoutDayInput,
  CreateWorkoutExerciseInput,
} from '../workouts/workout.types';
import { determineIsPrimary } from '../workouts/workout.utils';
import { PrescriptionRequestDto } from 'src/integrations/integrations.types';
import { InferredExercise, MuscleTarget } from '../exercise/exercise.types';

type WorkoutDay = CreateWorkoutDayInput;
type WorkoutExercise = CreateWorkoutExerciseInput;

@Injectable()
export class PlansService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly exerciseClient: ExerciseClientService,
    private readonly workoutsService: WorkoutsService,
    private readonly athletesService: AthletesService,
    private readonly autoRegulationServiceIntegration: AutoRegulationServiceIntegration,
  ) {}

  async getPlans(userId: number) {
    const athleteId = await this.athletesService.getAthleteIdByUserId(userId);
    return this.db.query.workoutPlans.findMany({
      where: eq(workoutPlans.athleteId, athleteId),
    });
  }

  async getPlan(userId: number, planId: number) {
    const athleteId = await this.athletesService.getAthleteIdByUserId(userId);
    const plan = await this.db.query.workoutPlans.findFirst({
      where: and(
        eq(workoutPlans.id, planId),
        eq(workoutPlans.athleteId, athleteId),
      ),
    });

    if (!plan) {
      throw new NotFoundException('Plan not found');
    }

    const days = await this.db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, planId))
      .orderBy(asc(workoutDays.orderInWeek));

    const dayIds = days.map((day) => day.id);
    const dayExercises =
      dayIds.length > 0
        ? await this.db
            .select()
            .from(workoutDayExercises)
            .where(inArray(workoutDayExercises.workoutDayId, dayIds))
            .orderBy(asc(workoutDayExercises.orderInWorkout))
        : [];

    // Exercise details live in the exercise service; hydrate the stored
    // exercise IDs into full exercise objects.
    const exerciseIds = [...new Set(dayExercises.map((wde) => wde.exerciseId))];
    const exercises = await this.exerciseClient.getExercises(exerciseIds);
    const exercisesById = new Map(exercises.map((ex) => [ex.id, ex]));

    const exercisesByDay = new Map<number, typeof dayExercises>();
    for (const wde of dayExercises) {
      const list = exercisesByDay.get(wde.workoutDayId) ?? [];
      list.push(wde);
      exercisesByDay.set(wde.workoutDayId, list);
    }

    return {
      ...plan,
      workoutDays: days.map((day) => ({
        ...day,
        workoutDayExercises: (exercisesByDay.get(day.id) ?? []).map((wde) => ({
          ...wde,
          exercise: exercisesById.get(wde.exerciseId) ?? null,
        })),
      })),
    };
  }

  async createPlan(createPlanDto: {
    userId: number;
    name: string;
    description?: string;
    trainingType: TrainingType;
    periodizationModel: PeriodizationModel;
    frequency: number;
    durationWeeks: number;
    focusAreas?: string[];
    workoutDays: WorkoutDay[];
  }) {
    const athleteId = await this.athletesService.getAthleteIdByUserId(
      createPlanDto.userId,
    );

    const allExerciseNames = createPlanDto.workoutDays.flatMap((workoutDay) =>
      workoutDay.exercises.map((exercise) => exercise.name),
    );

    const inferredExercises =
      await this.exerciseClient.inferExercises(allExerciseNames);

    // Index inference results by the lowercased name they were requested with
    const exerciseDataMap = new Map<string, InferredExercise>(
      inferredExercises.map((entry) => [
        entry.requestedName.toLowerCase(),
        entry,
      ]),
    );

    // Collect workout day data for batch image generation
    const workoutDaysData: Array<{
      id: number;
      muscles: Array<MuscleTarget>;
    }> = [];

    // Collect all prescription requests for batch processing (before transaction)
    const prescriptionRequests: PrescriptionRequestDto[] = [];

    const exerciseMetadataPreInsert: Array<{
      dayIndex: number;
      exercise: WorkoutExercise;
      exerciseData: InferredExercise;
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
        const isPrimary = determineIsPrimary(
          exerciseData.exercise.intensityCategory,
          exercise.orderInWorkout,
          totalExercises,
        );

        prescriptionRequests.push({
          intensityCategory: exerciseData.exercise.intensityCategory,
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
      await this.autoRegulationServiceIntegration.generateBatchPrescriptions(
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
        .where(eq(workoutPlans.athleteId, athleteId));

      const workoutPlanId: number = await tx
        .insert(workoutPlans)
        .values({
          athleteId: athleteId,
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
            for (const muscle of exerciseData.exercise.muscles) {
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
        exerciseData: InferredExercise;
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
        exerciseId: meta.exerciseData.exercise.id,
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

    // Publish muscle-image generation events outside the transaction
    this.workoutsService.generateMuscleImagesForWorkoutDay(workoutDaysData);
  }

  async updatePlan(
    userId: number,
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
    const athleteId = await this.athletesService.getAthleteIdByUserId(userId);

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

  async deletePlan(userId: number, planId: number) {
    const athleteId = await this.athletesService.getAthleteIdByUserId(userId);
    await this.db
      .delete(workoutPlans)
      .where(
        and(eq(workoutPlans.id, planId), eq(workoutPlans.athleteId, athleteId)),
      );
  }

  async activatePlan(userId: number, planId: number) {
    const athleteId = await this.athletesService.getAthleteIdByUserId(userId);
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
