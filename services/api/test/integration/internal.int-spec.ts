import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer, type RegisteredUser } from './auth-helpers';
import { planPayload } from './fixtures';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';

const SERVICE_TOKEN = process.env.SERVICE_TOKEN as string;

describe('Internal service endpoints (integration)', () => {
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

  describe('ServiceTokenGuard', () => {
    it('rejects requests with no token', async () => {
      await request(app.getHttpServer())
        .get(`/internal/athletes/${user.athleteId}`)
        .expect(401);
    });

    it('rejects requests with the wrong token', async () => {
      await request(app.getHttpServer())
        .get(`/internal/athletes/${user.athleteId}`)
        .set(bearer('not-the-service-token'))
        .expect(401);
    });
  });

  it('returns a snake_case athlete DTO with a valid service token', async () => {
    const res = await request(app.getHttpServer())
      .get(`/internal/athletes/${user.athleteId}`)
      .set(bearer(SERVICE_TOKEN))
      .expect(200);
    expect(res.body).toMatchObject({
      id: user.athleteId,
      training_experience: 'intermediate',
      rpe_calibration_factor: 1,
    });
  });

  it('returns the active plan with nested days/exercises', async () => {
    await request(app.getHttpServer())
      .post('/plans')
      .set(bearer(user.accessToken))
      .send(planPayload())
      .expect(201);

    const res = await request(app.getHttpServer())
      .get(`/internal/athletes/${user.athleteId}/active-plan`)
      .set(bearer(SERVICE_TOKEN))
      .expect(200);

    expect(res.body).toMatchObject({
      athlete_id: user.athleteId,
      is_active: true,
      training_type: 'hypertrophy',
    });
    expect(res.body.days).toHaveLength(1);
    expect(res.body.days[0].exercises).toHaveLength(2);
    expect(res.body.days[0].exercises[0]).toHaveProperty('target_rpe');
  });

  it('lists recovery metrics and personal records (empty initially)', async () => {
    const recovery = await request(app.getHttpServer())
      .get(`/internal/athletes/${user.athleteId}/recovery-metrics`)
      .set(bearer(SERVICE_TOKEN))
      .expect(200);
    expect(recovery.body).toEqual([]);

    const prs = await request(app.getHttpServer())
      .get(`/internal/athletes/${user.athleteId}/personal-records`)
      .set(bearer(SERVICE_TOKEN))
      .expect(200);
    expect(prs.body).toEqual([]);
  });
});
