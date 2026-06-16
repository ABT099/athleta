import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer, type RegisteredUser } from './auth-helpers';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';

describe('Athletes (integration)', () => {
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

  it('returns the current athlete profile', async () => {
    const res = await request(app.getHttpServer())
      .get('/athletes/me')
      .set(bearer(user.accessToken))
      .expect(200);
    expect(res.body).toMatchObject({
      id: user.athleteId,
      email: user.email,
      trainingExperience: 'intermediate',
    });
  });

  it('updates only the provided profile fields', async () => {
    const res = await request(app.getHttpServer())
      .patch('/athletes/me')
      .set(bearer(user.accessToken))
      .send({ age: 35, weight: 100, weightUnit: 'kg' })
      .expect(200);
    expect(res.body.age).toBe(35);
    expect(res.body.bodyWeightKg).toBeCloseTo(100);
    expect(res.body.gender).toBe('male'); // untouched
  });

  describe('recovery metrics', () => {
    function createMetric(body: Record<string, unknown>) {
      return request(app.getHttpServer())
        .post('/athletes/me/recovery-metrics')
        .set(bearer(user.accessToken))
        .send(body);
    }

    it('creates, lists, updates and deletes a metric', async () => {
      const created = await createMetric({
        sleepQuality: 'good',
        sleepHours: 7.5,
        stressLevel: 3,
      }).expect(201);
      const id = created.body.id;

      const list = await request(app.getHttpServer())
        .get('/athletes/me/recovery-metrics')
        .set(bearer(user.accessToken))
        .expect(200);
      expect(list.body).toHaveLength(1);

      const updated = await request(app.getHttpServer())
        .patch(`/athletes/me/recovery-metrics/${id}`)
        .set(bearer(user.accessToken))
        .send({ stressLevel: 5 })
        .expect(200);
      expect(updated.body.stressLevel).toBe(5);
      expect(updated.body.sleepQuality).toBe('good'); // unchanged

      await request(app.getHttpServer())
        .delete(`/athletes/me/recovery-metrics/${id}`)
        .set(bearer(user.accessToken))
        .expect(200);

      const after = await request(app.getHttpServer())
        .get('/athletes/me/recovery-metrics')
        .set(bearer(user.accessToken))
        .expect(200);
      expect(after.body).toHaveLength(0);
    });

    it('filters by since and respects limit, newest first', async () => {
      await createMetric({ sleepQuality: 'poor', date: '2024-01-01T00:00:00.000Z' }).expect(201);
      await createMetric({ sleepQuality: 'good', date: '2024-06-01T00:00:00.000Z' }).expect(201);
      await createMetric({ sleepQuality: 'excellent', date: '2024-12-01T00:00:00.000Z' }).expect(201);

      const since = await request(app.getHttpServer())
        .get('/athletes/me/recovery-metrics')
        .query({ since: '2024-05-01T00:00:00.000Z' })
        .set(bearer(user.accessToken))
        .expect(200);
      expect(since.body).toHaveLength(2);
      // newest first
      expect(since.body[0].sleepQuality).toBe('excellent');

      const limited = await request(app.getHttpServer())
        .get('/athletes/me/recovery-metrics')
        .query({ limit: '1' })
        .set(bearer(user.accessToken))
        .expect(200);
      expect(limited.body).toHaveLength(1);
      expect(limited.body[0].sleepQuality).toBe('excellent');
    });

    it("does not let another athlete update or delete a metric", async () => {
      const created = await createMetric({ sleepQuality: 'good' }).expect(201);
      const id = created.body.id;

      const other = await registerAndLogin(app, db);
      await request(app.getHttpServer())
        .patch(`/athletes/me/recovery-metrics/${id}`)
        .set(bearer(other.accessToken))
        .send({ stressLevel: 9 })
        .expect(404);
      await request(app.getHttpServer())
        .delete(`/athletes/me/recovery-metrics/${id}`)
        .set(bearer(other.accessToken))
        .expect(404);
    });
  });
});
