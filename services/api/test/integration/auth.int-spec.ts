import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { eq } from 'drizzle-orm';
import { athletes, refreshTokens, users } from 'src/db/schema';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import { createTestApp, closeTestApp } from './test-app';
import { truncateAll } from './db-clean';
import { registerAndLogin, bearer } from './auth-helpers';

describe('Auth (integration)', () => {
  let app: INestApplication;
  let db: DrizzleDB;

  beforeAll(async () => {
    ({ app, db } = await createTestApp());
  });

  afterEach(async () => {
    await truncateAll(db);
  });

  afterAll(async () => {
    await closeTestApp({ app, db });
  });

  describe('guards', () => {
    it('leaves the health check anonymous', async () => {
      await request(app.getHttpServer())
        .get('/health')
        .expect(200)
        .expect({ status: 'healthy', service: 'athleta-api' });
    });

    it('rejects a protected route without a bearer token', async () => {
      await request(app.getHttpServer()).get('/athletes/me').expect(401);
    });
  });

  describe('register', () => {
    it('creates a user + athlete and returns tokens', async () => {
      const email = `reg-${Date.now()}@test.com`;
      const res = await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          firstName: 'Ada',
          lastName: 'Lovelace',
          email,
          password: 'password123',
          age: 28,
          gender: 'female',
          weight: 60,
          weightUnit: 'kg',
          trainingExperience: 'beginner',
        })
        .expect(201);

      expect(res.body.access_token).toEqual(expect.any(String));
      expect(res.body.refresh_token).toEqual(expect.any(String));
      expect(res.body.hasInitialPlan).toBe(false);

      const [user] = await db
        .select()
        .from(users)
        .where(eq(users.email, email));
      expect(user).toBeDefined();
      expect(user.password).not.toBe('password123'); // hashed

      const [athlete] = await db
        .select()
        .from(athletes)
        .where(eq(athletes.userId, user.id));
      expect(athlete).toBeDefined();
      expect(athlete.age).toBe(28);
    });

    it('rejects a duplicate email', async () => {
      const user = await registerAndLogin(app, db);
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          firstName: 'Dup',
          lastName: 'User',
          email: user.email,
          password: 'password123',
          age: 30,
          gender: 'male',
          weight: 80,
          weightUnit: 'kg',
          trainingExperience: 'intermediate',
        })
        .expect(400);
    });
  });

  describe('login', () => {
    it('authenticates with valid credentials', async () => {
      const email = `login-${Date.now()}@test.com`;
      await request(app.getHttpServer())
        .post('/auth/register')
        .send({
          firstName: 'Grace',
          lastName: 'Hopper',
          email,
          password: 'password123',
          age: 40,
          gender: 'female',
          weight: 65,
          weightUnit: 'kg',
          trainingExperience: 'advanced',
        })
        .expect(201);

      const res = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email, password: 'password123' })
        .expect(201);

      expect(res.body.access_token).toEqual(expect.any(String));
    });

    it('rejects a wrong password with 401', async () => {
      const user = await registerAndLogin(app, db);
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: user.email, password: 'wrong-password' })
        .expect(401);
    });
  });

  describe('refresh', () => {
    it('rotates a valid refresh token', async () => {
      const user = await registerAndLogin(app, db);
      const res = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: user.refreshToken })
        .expect(201);

      expect(res.body.access_token).toEqual(expect.any(String));
      expect(res.body.refresh_token).toEqual(expect.any(String));
      expect(res.body.refresh_token).not.toBe(user.refreshToken);
    });

    it('detects reuse of a consumed token and revokes all tokens', async () => {
      const user = await registerAndLogin(app, db);

      // First use succeeds and marks the token used (and issues a new one).
      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: user.refreshToken })
        .expect(201);

      // Reusing the same (now-used) token is rejected as reuse.
      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: user.refreshToken })
        .expect(401);

      // Reuse detection wipes every token for the user (committed after the
      // rotation transaction so the throw can't roll it back).
      const remaining = await db
        .select()
        .from(refreshTokens)
        .where(eq(refreshTokens.userId, user.userId));
      expect(remaining).toHaveLength(0);
    });

    it('rejects an expired refresh token', async () => {
      const user = await registerAndLogin(app, db);
      const expiredToken = `expired-${Date.now()}`;
      await db.insert(refreshTokens).values({
        userId: user.userId,
        token: expiredToken,
        expiresAt: new Date(Date.now() - 1000).toISOString(),
      });

      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: expiredToken })
        .expect(401);
    });

    it('rejects an unknown refresh token', async () => {
      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: 'does-not-exist' })
        .expect(401);
    });
  });

  describe('authenticated access', () => {
    it('allows a protected route with a valid bearer token', async () => {
      const user = await registerAndLogin(app, db);
      const res = await request(app.getHttpServer())
        .get('/athletes/me')
        .set(bearer(user.accessToken))
        .expect(200);
      expect(res.body.id).toBe(user.athleteId);
    });
  });
});
