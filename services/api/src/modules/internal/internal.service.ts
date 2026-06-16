import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { eq, and, asc, desc, gte, type SQL } from 'drizzle-orm';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import {
  athletes,
  workoutPlans,
  workoutDays,
  workoutDayExercises,
  recoveryMetrics,
  exercisePersonalRecords,
} from 'src/db/schema';

type RecoveryRow = typeof recoveryMetrics.$inferSelect;
type PersonalRecordRow = typeof exercisePersonalRecords.$inferSelect;

/**
 * Read-side for internal (service-to-service) consumers — currently
 * auto-regulation-service, which fetches api-owned data instead of joining it
 * from a shared database.
 *
 * Responses are snake_case to match auto-regulation's DTO contract.
 */
@Injectable()
export class InternalService {
  constructor(@Inject(DRIZZLE) private readonly db: DrizzleDB) {}

  async getAthlete(athleteId: number) {
    const row = await this.db.query.athletes.findFirst({
      where: eq(athletes.id, athleteId),
    });
    if (!row) {
      throw new NotFoundException(`Athlete ${athleteId} not found`);
    }
    return {
      id: row.id,
      age: row.age,
      gender: row.gender,
      training_experience: row.trainingExperience,
      rpe_calibration_factor: row.rpeCalibrationFactor,
      body_weight_kg: row.bodyWeightKg,
    };
  }

  async getActivePlan(athleteId: number) {
    const plan = await this.db.query.workoutPlans.findFirst({
      where: and(
        eq(workoutPlans.athleteId, athleteId),
        eq(workoutPlans.isActive, true),
      ),
    });
    if (!plan) {
      throw new NotFoundException(`No active plan for athlete ${athleteId}`);
    }

    const days = await this.db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, plan.id))
      .orderBy(asc(workoutDays.orderInWeek));

    const dayIds = days.map((d) => d.id);
    const exercises = dayIds.length
      ? await this.db
          .select()
          .from(workoutDayExercises)
          .orderBy(asc(workoutDayExercises.orderInWorkout))
      : [];
    const exercisesByDay = new Map<number, typeof exercises>();
    for (const ex of exercises) {
      if (!dayIds.includes(ex.workoutDayId)) continue;
      const list = exercisesByDay.get(ex.workoutDayId) ?? [];
      list.push(ex);
      exercisesByDay.set(ex.workoutDayId, list);
    }

    return {
      id: plan.id,
      athlete_id: plan.athleteId,
      name: plan.name,
      training_type: plan.trainingType,
      periodization_model: plan.periodizationModel,
      focus_areas: plan.focusAreas ?? null,
      frequency: plan.frequency,
      duration_weeks: plan.durationWeeks,
      start_date: plan.startDate,
      end_date: plan.endDate,
      is_active: plan.isActive,
      days: days.map((d) => ({
        id: d.id,
        workout_plan_id: d.workoutPlanId,
        name: d.name,
        day_of_week: d.dayOfWeek,
        order_in_week: d.orderInWeek,
        exercises: (exercisesByDay.get(d.id) ?? []).map((ex) => ({
          id: ex.id,
          workout_day_id: ex.workoutDayId,
          exercise_id: ex.exerciseId,
          order_in_workout: ex.orderInWorkout,
          target_sets_min: ex.targetSetsMin,
          target_sets_max: ex.targetSetsMax,
          target_reps_min: ex.targetRepsMin,
          target_reps_max: ex.targetRepsMax,
          target_rpe: ex.targetRpe,
          target_rir: ex.targetRir,
          rest_period_seconds: ex.restPeriodSeconds,
          notes: ex.notes,
          is_primary: ex.isPrimary,
          progression_scheme: ex.progressionScheme,
          warm_up_sets: ex.warmUpSets,
          set_type: ex.setType,
          rep_style: ex.repStyle,
          set_type_params: ex.setTypeParams ?? null,
          rep_style_params: ex.repStyleParams ?? null,
        })),
      })),
    };
  }

  /** Like {@link getActivePlan} but returns null instead of throwing. */
  async getActivePlanOrNull(athleteId: number) {
    try {
      return await this.getActivePlan(athleteId);
    } catch (err) {
      if (err instanceof NotFoundException) return null;
      throw err;
    }
  }

  /** Recovery metrics for an athlete, newest first (ML retraining bulk read). */
  async listRecoveryMetrics(athleteId: number, since?: Date, limit?: number) {
    const conditions: SQL[] = [eq(recoveryMetrics.athleteId, athleteId)];
    if (since) {
      conditions.push(gte(recoveryMetrics.date, since.toISOString()));
    }
    const base = this.db
      .select()
      .from(recoveryMetrics)
      .where(and(...conditions))
      .orderBy(desc(recoveryMetrics.date));
    const rows = limit ? await base.limit(limit) : await base;
    return rows.map((r) => this.toRecoveryDto(r));
  }

  /** All current PRs for an athlete (ML retraining bulk read). */
  async listPersonalRecords(athleteId: number) {
    const rows = await this.db
      .select()
      .from(exercisePersonalRecords)
      .where(eq(exercisePersonalRecords.athleteId, athleteId));
    return rows.map((r) => this.toPersonalRecordDto(r));
  }

  toRecoveryDto(r: RecoveryRow) {
    return {
      id: r.id,
      athlete_id: r.athleteId,
      date: r.date,
      sleep_quality: r.sleepQuality,
      sleep_hours: r.sleepHours,
      overall_soreness: r.overallSoreness,
      muscle_soreness: r.muscleSoreness,
      stress_level: r.stressLevel,
      energy_level: r.energyLevel,
      readiness_score: r.readinessScore,
      nutrition_adherence: r.nutritionAdherence,
      hydration_level: r.hydrationLevel,
      notes: r.notes,
    };
  }

  toPersonalRecordDto(r: PersonalRecordRow) {
    return {
      exercise_id: r.exerciseId,
      one_rep_max: r.oneRepMax,
      one_rm_date: r.oneRmDate,
      three_rep_max: r.threeRepMax,
      three_rm_date: r.threeRmDate,
      five_rep_max: r.fiveRepMax,
      five_rm_date: r.fiveRmDate,
      eight_rep_max: r.eightRepMax,
      eight_rm_date: r.eightRmDate,
      ten_rep_max: r.tenRepMax,
      ten_rm_date: r.tenRmDate,
      twelve_rep_max: r.twelveRepMax,
      twelve_rm_date: r.twelveRmDate,
      max_volume_session: r.maxVolumeSession,
      max_total_reps: r.maxTotalReps,
      total_pr_count: r.totalPrCount,
      last_pr_date: r.lastPrDate,
    };
  }
}
