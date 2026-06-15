import { Injectable, NotFoundException, Inject, Logger } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import {
  workoutDayExercises,
  workoutDays,
  workoutPlans,
  athletes,
  workoutSessions,
  exerciseSets,
  recoveryMetrics,
  exercisePersonalRecords,
} from 'src/db/schema';
import { eq, and, inArray, sql } from 'drizzle-orm';
import { WorkoutExerciseDto } from '../plans/dto/create-plan.dto';
import { ExerciseClientService } from '../exercise/exercise-client.service';
import { MuscleImageIntegration } from 'src/integrations/muscle-image.integration';
import { AutoRegulationServiceIntegration } from 'src/integrations/auto-regulation-service.integration';
import {
  PrescriptionRequestDto,
  PrUpdate,
} from 'src/integrations/integrations.types';
import { InternalService } from '../internal/internal.service';
import { CompleteWorkoutDto } from './dto/complete-workout.dto';
import { DayOfWeek, TrainingType } from 'src/constants';
import { InferredExercise, MuscleTarget } from '../exercise/exercise.types';
import {
  CreateWorkoutExerciseInput,
  CreateWorkoutDayInput,
} from './workout.types';
import { determineIsPrimary } from './workout.utils';

@Injectable()
export class WorkoutsService {
  private readonly logger = new Logger(WorkoutsService.name);

  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly exerciseClient: ExerciseClientService,
    private readonly muscleImageIntegration: MuscleImageIntegration,
    private readonly autoReg: AutoRegulationServiceIntegration,
    private readonly internalService: InternalService,
  ) {}

  /**
   * Complete a logged workout: persist the session/sets/recovery in api's DB,
   * push the full context to auto-regulation for analysis, then persist the
   * write-backs it returns (PRs + calibration factor). The log is committed
   * first; analysis is best-effort, so a transient auto-reg failure still keeps
   * the workout the athlete logged.
   */
  async completeWorkout(userId: number, dto: CompleteWorkoutDto) {
    const athlete = await this.db.query.athletes.findFirst({
      where: eq(athletes.userId, userId),
    });
    if (!athlete) {
      throw new NotFoundException(`No athlete profile for user ${userId}`);
    }

    const sessionDate = dto.sessionDate ?? new Date().toISOString();
    const totalVolume = dto.exerciseSets.reduce(
      (sum, s) => sum + s.weight * s.reps,
      0,
    );

    // 1. Persist the log (one transaction in api's DB).
    const { session, sets, recovery } = await this.db.transaction(
      async (tx) => {
        const [session] = await tx
          .insert(workoutSessions)
          .values({
            athleteId: athlete.id,
            workoutDayId: dto.workoutDayId,
            sessionDate,
            durationMinutes: dto.durationMinutes ?? null,
            overallRpe: dto.overallRpe ?? null,
            overallFeeling: dto.overallFeeling ?? null,
            notes: dto.notes ?? null,
            totalVolume,
          })
          .returning();

        const sets = await tx
          .insert(exerciseSets)
          .values(
            dto.exerciseSets.map((s) => ({
              workoutSessionId: session.id,
              exerciseId: s.exerciseId,
              setNumber: s.setNumber,
              weight: s.weight,
              reps: s.reps,
              rpe: s.rpe ?? null,
              rir: s.rir ?? null,
              formQuality: s.formQuality ?? null,
              setTypeUsed: (s.setTypeUsed ??
                null) as (typeof exerciseSets.$inferInsert)['setTypeUsed'],
              repStyleUsed: (s.repStyleUsed ??
                null) as (typeof exerciseSets.$inferInsert)['repStyleUsed'],
              techniqueDetails: s.techniqueDetails ?? null,
              notes: s.notes ?? null,
            })),
          )
          .returning();

        let recovery: typeof recoveryMetrics.$inferSelect | null = null;
        if (dto.recoveryMetrics) {
          const r = dto.recoveryMetrics;
          [recovery] = await tx
            .insert(recoveryMetrics)
            .values({
              athleteId: athlete.id,
              date: sessionDate,
              sleepQuality: r.sleepQuality as (typeof recoveryMetrics.$inferInsert)['sleepQuality'],
              sleepHours: r.sleepHours ?? null,
              overallSoreness: r.overallSoreness ?? null,
              muscleSoreness: r.muscleSoreness ?? null,
              stressLevel: r.stressLevel ?? null,
              energyLevel: r.energyLevel ?? null,
              nutritionAdherence: r.nutritionAdherence ?? null,
              hydrationLevel: r.hydrationLevel ?? null,
              notes: r.notes ?? null,
            })
            .returning();
        }

        return { session, sets, recovery };
      },
    );

    // 2. Assemble the analyze request api pushes (athlete-owned data + the log).
    const [athleteDto, planDto, prDtos] = await Promise.all([
      this.internalService.getAthlete(athlete.id),
      this.internalService.getActivePlanOrNull(athlete.id),
      this.internalService.listPersonalRecords(athlete.id),
    ]);

    const sessionDto = {
      id: session.id,
      athlete_id: session.athleteId,
      workout_day_id: session.workoutDayId,
      session_date: session.sessionDate,
      duration_minutes: session.durationMinutes,
      overall_rpe: session.overallRpe,
      overall_feeling: session.overallFeeling,
      total_volume: session.totalVolume,
      estimated_fatigue: session.estimatedFatigue,
      notes: session.notes,
      sets: sets.map((s) => ({
        id: s.id,
        workout_session_id: s.workoutSessionId,
        exercise_id: s.exerciseId,
        set_number: s.setNumber,
        weight: s.weight,
        reps: s.reps,
        rpe: s.rpe,
        rir: s.rir,
        form_quality: s.formQuality,
        set_type_used: s.setTypeUsed,
        rep_style_used: s.repStyleUsed,
        technique_details: s.techniqueDetails,
        notes: s.notes,
      })),
    };
    const recoveryDto = recovery
      ? this.internalService.toRecoveryDto(recovery)
      : null;

    // 3. Push to auto-regulation. Analysis is best-effort.
    let analysis;
    try {
      analysis = await this.autoReg.analyzeSession({
        athlete: athleteDto,
        plan: planDto,
        session: sessionDto,
        recovery: recoveryDto,
        personal_records: prDtos,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.logger.error(
        `Session ${session.id} persisted but analysis failed: ${message}`,
      );
      return { session_id: session.id, analysis: null };
    }

    // 4. Persist the write-backs (PRs + calibration factor).
    await this.persistPrUpdates(athlete.id, analysis.pr_updates?.updates ?? []);
    if (typeof analysis.calibration_factor === 'number') {
      await this.db
        .update(athletes)
        .set({ rpeCalibrationFactor: analysis.calibration_factor })
        .where(eq(athletes.id, athlete.id));
    }

    return { session_id: session.id, analysis };
  }

  /**
   * Apply PR write-backs from auto-regulation into exercise_personal_records,
   * grouped per exercise and upserted on (athlete_id, exercise_id).
   */
  private async persistPrUpdates(athleteId: number, updates: PrUpdate[]) {
    if (updates.length === 0) return;

    const byExercise = new Map<number, PrUpdate[]>();
    for (const u of updates) {
      const list = byExercise.get(u.exercise_id) ?? [];
      list.push(u);
      byExercise.set(u.exercise_id, list);
    }

    const now = new Date().toISOString();
    for (const [exerciseId, exerciseUpdates] of byExercise) {
      const fields: Partial<typeof exercisePersonalRecords.$inferInsert> = {};
      let prCount = 0;
      let latestDate = now;
      for (const u of exerciseUpdates) {
        const date = typeof u.date === 'string' ? u.date : now;
        switch (u.pr_type) {
          case '1RM':
            fields.oneRepMax = u.new_value;
            fields.oneRmDate = date;
            break;
          case '3RM':
            fields.threeRepMax = u.new_value;
            fields.threeRmDate = date;
            break;
          case '5RM':
            fields.fiveRepMax = u.new_value;
            fields.fiveRmDate = date;
            break;
          case '8RM':
            fields.eightRepMax = u.new_value;
            fields.eightRmDate = date;
            break;
          case '10RM':
            fields.tenRepMax = u.new_value;
            fields.tenRmDate = date;
            break;
          case '12RM':
            fields.twelveRepMax = u.new_value;
            fields.twelveRmDate = date;
            break;
          case 'volume':
            fields.maxVolumeSession = u.new_value;
            fields.maxVolumeDate = date;
            break;
          case 'total_reps':
            fields.maxTotalReps = Math.round(u.new_value);
            fields.maxRepsDate = date;
            break;
          default:
            continue;
        }
        prCount += 1;
        latestDate = date;
      }
      if (prCount === 0) continue;

      await this.db
        .insert(exercisePersonalRecords)
        .values({
          athleteId,
          exerciseId,
          ...fields,
          totalPrCount: prCount,
          lastPrDate: latestDate,
          updatedAt: now,
        })
        .onConflictDoUpdate({
          target: [
            exercisePersonalRecords.athleteId,
            exercisePersonalRecords.exerciseId,
          ],
          set: {
            ...fields,
            totalPrCount: sql`${exercisePersonalRecords.totalPrCount} + ${prCount}`,
            lastPrDate: latestDate,
            updatedAt: now,
          },
        });
    }
  }

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

    // Verify substitute exercise exists in the exercise service
    const substituteExercise =
      await this.exerciseClient.getExercise(substituteExerciseId);

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

    const inferredExercises =
      await this.exerciseClient.inferExercises(allExerciseNames);
    const exerciseDataMap = this.mapByRequestedName(inferredExercises);

    const musclesTargets: Array<MuscleTarget> = [];

    for (const exercise of exercisesToAdd) {
      const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
      if (exerciseData) {
        for (const muscle of exerciseData.exercise.muscles) {
          musclesTargets.push(muscle);
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

    const trainingType = workoutPlanData[0].trainingType as TrainingType;

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
      const isPrimary = determineIsPrimary(
        exerciseData.exercise.intensityCategory,
        exercise.orderInWorkout,
        totalExercises,
      );

      prescriptionRequests.push({
        intensityCategory: exerciseData.exercise.intensityCategory,
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
        ? await this.autoReg.generateBatchPrescriptions(
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

        await tx.insert(workoutDayExercises).values(exerciseValues);
      }
    });

    // Move image generation outside transaction to avoid holding it open
    if (exercisesToAdd.length > 0) {
      await this.generateMuscleImagesForWorkoutDay([
        { id: workoutDayId, muscles: musclesTargets },
      ]);
    }
  }

  async createWorkoutDays(
    workoutPlanId: number,
    trainingType: TrainingType,
    workoutDaysData: CreateWorkoutDayInput[],
  ): Promise<number[]> {
    if (!workoutDaysData || workoutDaysData.length === 0) {
      return [];
    }

    // Get all exercise names
    const allExerciseNames = workoutDaysData.flatMap((workoutDay) =>
      workoutDay.exercises.map((exercise) => exercise.name),
    );

    const inferredExercises =
      await this.exerciseClient.inferExercises(allExerciseNames);
    const exerciseDataMap = this.mapByRequestedName(inferredExercises);

    // Collect prescription requests
    const prescriptionRequests: PrescriptionRequestDto[] = [];
    const exerciseMetadataPreInsert: Array<{
      dayIndex: number;
      exercise: CreateWorkoutExerciseInput;
      exerciseData: InferredExercise;
      isPrimary: boolean;
    }> = [];

    for (let dayIndex = 0; dayIndex < workoutDaysData.length; dayIndex++) {
      const workoutDay = workoutDaysData[dayIndex];
      const totalExercises = workoutDay.exercises.length;

      for (const exercise of workoutDay.exercises) {
        const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
        if (!exerciseData) {
          throw new Error(`Exercise data not found for: ${exercise.name}`);
        }

        const isPrimary = determineIsPrimary(
          exerciseData.exercise.intensityCategory,
          exercise.orderInWorkout,
          totalExercises,
        );

        prescriptionRequests.push({
          intensityCategory: exerciseData.exercise.intensityCategory,
          trainingType: trainingType,
          trainingPhase: 'accumulation',
          weekInPhase: 1,
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

    // Generate prescriptions
    const prescriptions =
      prescriptionRequests.length > 0
        ? await this.autoReg.generateBatchPrescriptions(
            prescriptionRequests,
          )
        : [];

    if (
      prescriptionRequests.length > 0 &&
      prescriptions.length !== prescriptionRequests.length
    ) {
      throw new Error(
        `Prescription API returned ${prescriptions.length} prescriptions but expected ${prescriptionRequests.length}`,
      );
    }

    // Prepare workout day values
    const workoutDayValues = workoutDaysData.map((workoutDay) => {
      const musclesWithRoles: Array<MuscleTarget> = [];

      for (const exercise of workoutDay.exercises) {
        const exerciseData = exerciseDataMap.get(exercise.name.toLowerCase());
        if (exerciseData) {
          for (const muscle of exerciseData.exercise.muscles) {
            musclesWithRoles.push(muscle);
          }
        }
      }

      return {
        values: {
          workoutPlanId: workoutPlanId,
          name: workoutDay.name,
          dayOfWeek: workoutDay.dayOfWeek,
          orderInWeek: workoutDay.orderInWeek,
          muscleImageUrl: null,
        },
        muscles: musclesWithRoles,
      };
    });

    // Insert workout days in transaction
    const workoutDaysDataForImages: Array<{
      id: number;
      muscles: Array<MuscleTarget>;
    }> = [];

    const insertedWorkoutDayIds = await this.db.transaction(async (tx) => {
      // Insert workout days
      const insertedWorkoutDays = await tx
        .insert(workoutDays)
        .values(workoutDayValues.map((wd) => wd.values))
        .returning({ id: workoutDays.id });

      // Map workout day IDs to muscle data
      insertedWorkoutDays.forEach((insertedDay, index) => {
        workoutDaysDataForImages.push({
          id: insertedDay.id,
          muscles: workoutDayValues[index].muscles,
        });
      });

      // Prepare exercise inserts
      const allExerciseInserts: Array<{
        workoutDayId: number;
        exerciseId: number;
        orderInWorkout: number;
        targetSetsMin: number;
        targetSetsMax: number;
        targetRepsMin: number;
        targetRepsMax: number;
        targetRpe: number | null;
        targetRir: number | null;
        restPeriodSeconds: number | null;
        notes: string | null;
        isPrimary: boolean;
        warmUpSets: number;
      }> = [];
      let prescriptionIndex = 0;

      for (
        let dayIndex = 0;
        dayIndex < insertedWorkoutDays.length;
        dayIndex++
      ) {
        const workoutDayId = insertedWorkoutDays[dayIndex].id;
        const workoutDay = workoutDaysData[dayIndex];

        for (let i = 0; i < workoutDay.exercises.length; i++) {
          const preInsertMeta = exerciseMetadataPreInsert[prescriptionIndex];
          allExerciseInserts.push({
            workoutDayId: workoutDayId,
            exerciseId: preInsertMeta.exerciseData.exercise.id,
            orderInWorkout: preInsertMeta.exercise.orderInWorkout,
            targetSetsMin: preInsertMeta.exercise.targetSetsMin,
            targetSetsMax:
              preInsertMeta.exercise.targetSetsMax ??
              preInsertMeta.exercise.targetSetsMin,
            targetRepsMin: preInsertMeta.exercise.targetRepsMin,
            targetRepsMax:
              preInsertMeta.exercise.targetRepsMax ??
              preInsertMeta.exercise.targetRepsMin,
            targetRpe: prescriptions[prescriptionIndex].target_rpe,
            targetRir: prescriptions[prescriptionIndex].target_rir,
            restPeriodSeconds:
              prescriptions[prescriptionIndex].rest_period_seconds,
            notes: preInsertMeta.exercise.notes ?? null,
            isPrimary: preInsertMeta.isPrimary,
            warmUpSets: 0,
          });
          prescriptionIndex++;
        }
      }

      // Insert exercises
      if (allExerciseInserts.length > 0) {
        await tx.insert(workoutDayExercises).values(allExerciseInserts);
      }

      return insertedWorkoutDays.map((wd) => wd.id);
    });

    // Generate muscle images outside transaction
    await this.generateMuscleImagesForWorkoutDay(workoutDaysDataForImages);

    return insertedWorkoutDayIds;
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

  /**
   * Index inference results by the lowercased name they were requested with.
   * Results come back in request order, one per name.
   */
  private mapByRequestedName(
    inferred: InferredExercise[],
  ): Map<string, InferredExercise> {
    return new Map(
      inferred.map((entry) => [entry.requestedName.toLowerCase(), entry]),
    );
  }
}
