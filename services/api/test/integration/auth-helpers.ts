import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { eq } from 'drizzle-orm';
import { athletes, users } from 'src/db/schema';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';

export interface RegisteredUser {
  accessToken: string;
  refreshToken: string;
  userId: number;
  athleteId: number;
  email: string;
}

let counter = 0;

/** Register a fresh user (which also creates the athlete row) and resolve ids. */
export async function registerAndLogin(
  app: INestApplication,
  db: DrizzleDB,
): Promise<RegisteredUser> {
  const email = `user-${Date.now()}-${counter++}@test.com`;

  const res = await request(app.getHttpServer())
    .post('/auth/register')
    .send({
      firstName: 'Test',
      lastName: 'User',
      email,
      password: 'password123',
      age: 30,
      gender: 'male',
      weight: 80,
      weightUnit: 'kg',
      trainingExperience: 'intermediate',
    })
    .expect(201);

  const [user] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, email));
  const [athlete] = await db
    .select({ id: athletes.id })
    .from(athletes)
    .where(eq(athletes.userId, user.id));

  return {
    accessToken: res.body.access_token,
    refreshToken: res.body.refresh_token,
    userId: user.id,
    athleteId: athlete.id,
    email,
  };
}

export function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}
