import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { eq } from 'drizzle-orm';
import {
  athletes,
  exercisePersonalRecords,
  exerciseSets,
  workoutDayExercises,
  workoutDays,
  workoutPlans,
  workoutSessions,
} from 'src/db/schema';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import { jsDayToDayOfWeek } from 'src/constants';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer, type RegisteredUser } from './auth-helpers';
import { planPayload } from './fixtures';
import type { FakeAutoReg } from './fakes/auto-reg.fake';
import { emptyAnalyzeResponse } from './fakes/auto-reg.fake';

describe('Workouts (integration)', () => {
  let app: INestApplication;
  let db: DrizzleDB;
  let autoReg: FakeAutoReg;
  let user: RegisteredUser;

  const today = jsDayToDayOfWeek(new Date().getDay());

  beforeAll(async () => {
    ({ app, db, autoReg } = await createTestApp());
  });

  afterEach(async () => {
    await truncateAll(db);
    autoReg.analyzeSessionImpl = () => emptyAnalyzeResponse();
  });

  afterAll(async () => {
    await closeTestApp({ app, db });
  });

  beforeEach(async () => {
    user = await registerAndLogin(app, db);
  });

  async function createActivePlan(dayOfWeek = today) {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(
        planPayload({
          workoutDays: [
            {
              name: 'Push',
              dayOfWeek,
              orderInWeek: 1,
              exercises: [
                {
                  name: 'Bench Press',
                  targetSetsMin: 3,
                  targetRepsMin: 8,
                  orderInWorkout: 1,
                },
                {
                  name: 'Tricep Pushdown',
                  targetSetsMin: 3,
                  targetRepsMin: 10,
                  orderInWorkout: 2,
                },
              ],
            },
          ],
        }),
      )
      .expect(201);

    const [plan] = await db
      .select()
      .from(workoutPlans)
      .where(eq(workoutPlans.athleteId, user.athleteId));
    const [day] = await db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, plan.id));
    const exercises = await db
      .select()
      .from(workoutDayExercises)
      .where(eq(workoutDayExercises.workoutDayId, day.id));
    return { plan, day, exercises };
  }

  it('returns the current workout day for the active plan', async () => {
    const { day } = await createActivePlan(today);
    const res = await request(app.getHttpServer())
      .get('/workouts/current')
      .set(bearer(user.accessToken))
      .expect(200);
    expect(res.body.id).toBe(day.id);
    expect(res.body.dayOfWeek).toBe(today);
  });

  it('substitutes an exercise in a workout day', async () => {
    const { day, exercises } = await createActivePlan();
    const target = exercises[0];

    await request(app.getHttpServer())
      .put(`/workouts/${day.id}/exercises/${target.exerciseId}/substitute`)
      .set(bearer(user.accessToken))
      .send({ substituteExerciseId: 999999 })
      .expect(200);

    const [row] = await db
      .select()
      .from(workoutDayExercises)
      .where(eq(workoutDayExercises.id, target.id));
    expect(row.exerciseId).toBe(999999);
  });

  it('adds and removes exercises in a workout day', async () => {
    const { day, exercises } = await createActivePlan();

    await request(app.getHttpServer())
      .put(`/workouts/${day.id}/exercises`)
      .set(bearer(user.accessToken))
      .send({
        exercisesToRemove: [exercises[1].id],
        exercisesToAdd: [
          {
            name: 'Incline Dumbbell Press',
            targetSetsMin: 3,
            targetRepsMin: 10,
            orderInWorkout: 2,
          },
        ],
      })
      .expect(200);

    const rows = await db
      .select()
      .from(workoutDayExercises)
      .where(eq(workoutDayExercises.workoutDayId, day.id));
    // Started with 2, removed 1, added 1.
    expect(rows).toHaveLength(2);
    expect(rows.some((r) => r.id === exercises[1].id)).toBe(false);
  });

  describe('completeWorkout', () => {
    it('persists the session and applies PR + calibration write-backs', async () => {
      const { day, exercises } = await createActivePlan();
      const exerciseId = exercises[0].exerciseId;

      autoReg.analyzeSessionImpl = () => ({
        ...emptyAnalyzeResponse(),
        pr_updates: {
          updates: [
            {
              exercise_id: exerciseId,
              pr_type: '1RM',
              old_value: null,
              new_value: 100,
              improvement: 100,
              date: new Date().toISOString(),
              is_new_pr: true,
            },
          ],
        },
        calibration_factor: 1.25,
      });

      const res = await request(app.getHttpServer())
        .post('/workouts/complete')
        .set(bearer(user.accessToken))
        .send({
          workoutDayId: day.id,
          durationMinutes: 60,
          overallRpe: 8,
          exerciseSets: [
            { exerciseId, setNumber: 1, weight: 80, reps: 5 },
            { exerciseId, setNumber: 2, weight: 80, reps: 5 },
          ],
          recoveryMetrics: { sleepQuality: 'good', sleepHours: 8 },
        })
        .expect(201);

      expect(res.body.session_id).toEqual(expect.any(Number));

      const [session] = await db
        .select()
        .from(workoutSessions)
        .where(eq(workoutSessions.id, res.body.session_id));
      expect(session.totalVolume).toBe(800); // 80*5 + 80*5

      const sets = await db
        .select()
        .from(exerciseSets)
        .where(eq(exerciseSets.workoutSessionId, session.id));
      expect(sets).toHaveLength(2);

      const [pr] = await db
        .select()
        .from(exercisePersonalRecords)
        .where(eq(exercisePersonalRecords.athleteId, user.athleteId));
      expect(pr.oneRepMax).toBe(100);
      expect(pr.totalPrCount).toBe(1);

      const [athlete] = await db
        .select()
        .from(athletes)
        .where(eq(athletes.id, user.athleteId));
      expect(athlete.rpeCalibrationFactor).toBeCloseTo(1.25);
    });

    it('still commits the session when analysis fails', async () => {
      const { day, exercises } = await createActivePlan();
      autoReg.analyzeSessionImpl = () => {
        throw new Error('auto-regulation unavailable');
      };

      const res = await request(app.getHttpServer())
        .post('/workouts/complete')
        .set(bearer(user.accessToken))
        .send({
          workoutDayId: day.id,
          exerciseSets: [
            { exerciseId: exercises[0].exerciseId, setNumber: 1, weight: 60, reps: 8 },
          ],
        })
        .expect(201);

      expect(res.body.session_id).toEqual(expect.any(Number));
      expect(res.body.analysis).toBeNull();

      const sessions = await db
        .select()
        .from(workoutSessions)
        .where(eq(workoutSessions.athleteId, user.athleteId));
      expect(sessions).toHaveLength(1);
    });
  });

  it('blocks deleting a workout day that has logged sessions', async () => {
    const { day, exercises } = await createActivePlan();
    await request(app.getHttpServer())
      .post('/workouts/complete')
      .set(bearer(user.accessToken))
      .send({
        workoutDayId: day.id,
        exerciseSets: [
          { exerciseId: exercises[0].exerciseId, setNumber: 1, weight: 60, reps: 8 },
        ],
      })
      .expect(201);

    await request(app.getHttpServer())
      .delete(`/workouts/${day.id}`)
      .set(bearer(user.accessToken))
      .expect(400);
  });
});
