import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { and, desc, eq, gte, type SQL } from 'drizzle-orm';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import {
  athletes,
  users,
  exercisePersonalRecords,
  recoveryMetrics,
} from 'src/db/schema';
import { Gender, TrainingExperience } from 'src/constants';
import { CreateRecoveryMetricDto } from './dto/create-recovery-metric.dto';
import { UpdateRecoveryMetricDto } from './dto/update-recovery-metric.dto';

type Athlete = typeof athletes.$inferSelect;
type SleepQuality = (typeof recoveryMetrics.$inferInsert)['sleepQuality'];

/**
 * Owns the athlete profile and its athlete-scoped sub-resources, and is the
 * single source of truth for translating a user id (carried by the JWT) into
 * the athlete id that athlete-owned data is keyed by. `athletes.id` is a
 * separate sequence from `users.id`, so callers must resolve through here
 * rather than assuming the two coincide.
 */
@Injectable()
export class AthletesService {
  constructor(@Inject(DRIZZLE) private readonly db: DrizzleDB) {}

  async requireAthleteByUserId(userId: number): Promise<Athlete> {
    const athlete = await this.db.query.athletes.findFirst({
      where: eq(athletes.userId, userId),
    });
    if (!athlete) {
      throw new NotFoundException(`No athlete profile for user ${userId}`);
    }
    return athlete;
  }

  async getAthleteIdByUserId(userId: number): Promise<number> {
    const athlete = await this.requireAthleteByUserId(userId);
    return athlete.id;
  }

  async getMyProfile(userId: number) {
    // Relations aren't registered with the Drizzle client, so join explicitly.
    const [profile] = await this.db
      .select({
        id: athletes.id,
        age: athletes.age,
        gender: athletes.gender,
        trainingExperience: athletes.trainingExperience,
        rpeCalibrationFactor: athletes.rpeCalibrationFactor,
        bodyWeightKg: athletes.bodyWeightKg,
        firstName: users.firstName,
        lastName: users.lastName,
        email: users.email,
      })
      .from(athletes)
      .innerJoin(users, eq(athletes.userId, users.id))
      .where(eq(athletes.userId, userId))
      .limit(1);

    if (!profile) {
      throw new NotFoundException(`No athlete profile for user ${userId}`);
    }
    return profile;
  }

  async updateMyProfile(
    userId: number,
    fields: {
      age?: number;
      gender?: Gender;
      trainingExperience?: TrainingExperience;
      bodyWeightKg?: number;
    },
  ) {
    const athleteId = await this.getAthleteIdByUserId(userId);

    const updates: Partial<typeof athletes.$inferInsert> = {};
    if (fields.age !== undefined) updates.age = fields.age;
    if (fields.gender !== undefined) updates.gender = fields.gender;
    if (fields.trainingExperience !== undefined) {
      updates.trainingExperience = fields.trainingExperience;
    }
    if (fields.bodyWeightKg !== undefined) {
      updates.bodyWeightKg = fields.bodyWeightKg;
    }

    const [updated] = await this.db
      .update(athletes)
      .set(updates)
      .where(eq(athletes.id, athleteId))
      .returning();
    return updated;
  }

  async getMyPersonalRecords(userId: number) {
    const athleteId = await this.getAthleteIdByUserId(userId);
    return this.db
      .select()
      .from(exercisePersonalRecords)
      .where(eq(exercisePersonalRecords.athleteId, athleteId));
  }

  async getMyRecoveryMetrics(userId: number, since?: Date, limit?: number) {
    const athleteId = await this.getAthleteIdByUserId(userId);
    const conditions: SQL[] = [eq(recoveryMetrics.athleteId, athleteId)];
    if (since) {
      conditions.push(gte(recoveryMetrics.date, since.toISOString()));
    }
    const base = this.db
      .select()
      .from(recoveryMetrics)
      .where(and(...conditions))
      .orderBy(desc(recoveryMetrics.date));
    return limit ? await base.limit(limit) : await base;
  }

  async createRecoveryMetric(userId: number, dto: CreateRecoveryMetricDto) {
    const athleteId = await this.getAthleteIdByUserId(userId);
    const [created] = await this.db
      .insert(recoveryMetrics)
      .values({
        athleteId,
        date: dto.date ?? new Date().toISOString(),
        sleepQuality: dto.sleepQuality as SleepQuality,
        sleepHours: dto.sleepHours ?? null,
        overallSoreness: dto.overallSoreness ?? null,
        muscleSoreness: dto.muscleSoreness ?? null,
        stressLevel: dto.stressLevel ?? null,
        energyLevel: dto.energyLevel ?? null,
        nutritionAdherence: dto.nutritionAdherence ?? null,
        hydrationLevel: dto.hydrationLevel ?? null,
        notes: dto.notes ?? null,
      })
      .returning();
    return created;
  }

  async updateRecoveryMetric(
    userId: number,
    id: number,
    dto: UpdateRecoveryMetricDto,
  ) {
    const athleteId = await this.getAthleteIdByUserId(userId);

    const updates: Partial<typeof recoveryMetrics.$inferInsert> = {};
    if (dto.date !== undefined) updates.date = dto.date;
    if (dto.sleepQuality !== undefined) {
      updates.sleepQuality = dto.sleepQuality as SleepQuality;
    }
    if (dto.sleepHours !== undefined) updates.sleepHours = dto.sleepHours;
    if (dto.overallSoreness !== undefined) {
      updates.overallSoreness = dto.overallSoreness;
    }
    if (dto.muscleSoreness !== undefined) {
      updates.muscleSoreness = dto.muscleSoreness;
    }
    if (dto.stressLevel !== undefined) updates.stressLevel = dto.stressLevel;
    if (dto.energyLevel !== undefined) updates.energyLevel = dto.energyLevel;
    if (dto.nutritionAdherence !== undefined) {
      updates.nutritionAdherence = dto.nutritionAdherence;
    }
    if (dto.hydrationLevel !== undefined) {
      updates.hydrationLevel = dto.hydrationLevel;
    }
    if (dto.notes !== undefined) updates.notes = dto.notes;

    const [updated] = await this.db
      .update(recoveryMetrics)
      .set(updates)
      .where(
        and(
          eq(recoveryMetrics.id, id),
          eq(recoveryMetrics.athleteId, athleteId),
        ),
      )
      .returning();

    if (!updated) {
      throw new NotFoundException(`Recovery metric ${id} not found`);
    }
    return updated;
  }

  async deleteRecoveryMetric(userId: number, id: number) {
    const athleteId = await this.getAthleteIdByUserId(userId);
    const deleted = await this.db
      .delete(recoveryMetrics)
      .where(
        and(
          eq(recoveryMetrics.id, id),
          eq(recoveryMetrics.athleteId, athleteId),
        ),
      )
      .returning({ id: recoveryMetrics.id });

    if (deleted.length === 0) {
      throw new NotFoundException(`Recovery metric ${id} not found`);
    }
  }
}
