import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { eq } from 'drizzle-orm';
import { workoutDays, workoutPlans } from 'src/db/schema';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import {
  MUSCLE_IMAGE_GENERATED_TOPIC,
  WORKOUT_DAY_CREATED_TOPIC,
} from 'src/modules/common/messaging/messaging.constants';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer, type RegisteredUser } from './auth-helpers';
import { planPayload } from './fixtures';
import { collectMessages, produceEvent, waitFor } from './kafka-helpers';

// Real Kafka round-trips are slower than the HTTP-only suites.
jest.setTimeout(90000);

describe('Muscle image events (integration, real Kafka)', () => {
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

  async function createPlanWithDay() {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);
    const [plan] = await db
      .select()
      .from(workoutPlans)
      .where(eq(workoutPlans.athleteId, user.athleteId));
    const [day] = await db
      .select()
      .from(workoutDays)
      .where(eq(workoutDays.workoutPlanId, plan.id));
    return day;
  }

  it('publishes workout-day.created when a workout day is committed', async () => {
    const collector = await collectMessages(WORKOUT_DAY_CREATED_TOPIC);
    try {
      const day = await createPlanWithDay();

      const match = await waitFor(
        () =>
          collector.messages.find(
            (m) => (m as { workoutDayId?: number }).workoutDayId === day.id,
          ),
        (m) => m !== undefined,
      );
      expect(match).toMatchObject({ workoutDayId: day.id });
      expect(Array.isArray((match as { muscles?: unknown }).muscles)).toBe(true);
    } finally {
      await collector.stop();
    }
  });

  it('persists the image URL when muscle-image.generated is consumed', async () => {
    const day = await createPlanWithDay();
    const url = `https://images.test/${day.id}.png`;

    await produceEvent(
      MUSCLE_IMAGE_GENERATED_TOPIC,
      { workoutDayId: day.id, url },
      String(day.id),
    );

    const persisted = await waitFor(
      async () => {
        const [row] = await db
          .select()
          .from(workoutDays)
          .where(eq(workoutDays.id, day.id));
        return row?.muscleImageUrl ?? null;
      },
      (value) => value === url,
    );
    expect(persisted).toBe(url);
  });
});
