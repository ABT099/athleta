import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { and, eq } from 'drizzle-orm';
import { workoutDayExercises, workoutDays, workoutPlans } from 'src/db/schema';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer, type RegisteredUser } from './auth-helpers';
import { planPayload } from './fixtures';

describe('Plans (integration)', () => {
  let app: INestApplication;
  let db: DrizzleDB;
  let user: RegisteredUser;

  beforeAll(async () => {
    ({ app, db } = await createTestApp());
  });

  afterEach(async () => {
    await truncateAll(db);
  });

  afterAll(async () => {
    await closeTestApp({ app, db });
  });

  beforeEach(async () => {
    user = await registerAndLogin(app, db);
  });

  function plansForUser() {
    return db
      .select()
      .from(workoutPlans)
      .where(eq(workoutPlans.athleteId, user.athleteId));
  }

  it('creates a plan with nested days + exercises and applied prescriptions', async () => {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);

    const plans = await plansForUser();
    expect(plans).toHaveLength(1);
    const plan = plans[0];
    expect(plan.isActive).toBe(true);
    expect(plan.trainingType).toBe('hypertrophy');

    // endDate ≈ startDate + durationWeeks * 7 days.
    const spanMs =
      new Date(plan.endDate!).getTime() - new Date(plan.startDate).getTime();
    const expectedMs = 8 * 7 * 24 * 60 * 60 * 1000;
    expect(Math.abs(spanMs - expectedMs)).toBeLessThan(60 * 1000);

    const days = await db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, plan.id));
    expect(days).toHaveLength(1);

    const exercises = await db
      .select()
      .from(workoutDayExercises)
      .where(eq(workoutDayExercises.workoutDayId, days[0].id));
    expect(exercises).toHaveLength(2);
    // Prescription values come from the auto-regulation fake.
    expect(exercises[0].targetRpe).toBe(8);
    expect(exercises[0].restPeriodSeconds).toBe(120);
  });

  it('hydrates a plan with exercise details on GET', async () => {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);
    const [plan] = await plansForUser();

    const res = await request(app.getHttpServer())
      .get(`/plans/${plan.id}`)
      .set(bearer(user.accessToken))
      .expect(200);

    expect(res.body.id).toBe(plan.id);
    expect(res.body.workoutDays).toHaveLength(1);
    const day = res.body.workoutDays[0];
    expect(day.workoutDayExercises).toHaveLength(2);
    expect(day.workoutDayExercises[0].exercise).toMatchObject({
      id: expect.any(Number),
    });
  });

  it('keeps exactly one active plan and activate flips it', async () => {
    // Creating a second plan deactivates the first.
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload({ name: 'Plan A' }))
      .expect(201);
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload({ name: 'Plan B' }))
      .expect(201);

    let plans = await plansForUser();
    const planA = plans.find((p) => p.name === 'Plan A')!;
    const planB = plans.find((p) => p.name === 'Plan B')!;
    expect(planA.isActive).toBe(false);
    expect(planB.isActive).toBe(true);

    // Re-activating Plan A flips the active flag back.
    await request(app.getHttpServer())
      .patch(`/plans/${planA.id}/activate`)
      .set(bearer(user.accessToken))
      .expect(200);

    plans = await plansForUser();
    expect(plans.filter((p) => p.isActive)).toHaveLength(1);
    expect(plans.find((p) => p.id === planA.id)!.isActive).toBe(true);
  });

  it('updates plan fields and adds workout days', async () => {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);
    const [plan] = await plansForUser();

    await request(app.getHttpServer())
      .put(`/plans/${plan.id}`)
      .set(bearer(user.accessToken))
      .send({
        name: 'Renamed Plan',
        trainingType: 'strength',
        periodizationModel: 'linear',
        frequency: 4,
        durationWeeks: 10,
        workoutDaysToAdd: [
          {
            name: 'Pull',
            dayOfWeek: 1,
            orderInWeek: 2,
            exercises: [
              {
                name: 'Barbell Row',
                targetSetsMin: 3,
                targetRepsMin: 8,
                orderInWorkout: 1,
              },
            ],
          },
        ],
        workoutDaysToRemove: [],
      })
      .expect(200);

    const [updated] = await db
      .select()
      .from(workoutPlans)
      .where(eq(workoutPlans.id, plan.id));
    expect(updated.name).toBe('Renamed Plan');
    expect(updated.trainingType).toBe('strength');

    const days = await db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, plan.id));
    expect(days).toHaveLength(2);
  });

  it('creates a day-less plan and deletes it', async () => {
    // A plan with no days is valid (a shell), and deletePlan removes only the
    // workout_plans row (no FK cascade), so a day-less plan is safely deletable.
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload({ workoutDays: [] }))
      .expect(201);
    const [plan] = await plansForUser();

    await request(app.getHttpServer())
      .delete(`/plans/${plan.id}`)
      .set(bearer(user.accessToken))
      .expect(200);

    const remaining = await db
      .select()
      .from(workoutPlans)
      .where(eq(workoutPlans.id, plan.id));
    expect(remaining).toHaveLength(0);
  });

  it("does not let another athlete read a plan", async () => {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);
    const [plan] = await plansForUser();

    const other = await registerAndLogin(app, db);
    await request(app.getHttpServer())
      .get(`/plans/${plan.id}`)
      .set(bearer(other.accessToken))
      .expect(404);
  });
});
