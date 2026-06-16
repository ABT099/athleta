import { sql } from 'drizzle-orm';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';

// Children first is unnecessary with CASCADE, but listing every table keeps the
// reset explicit and independent of FK discovery.
const TABLES = [
  'exercise_sets',
  'workout_sessions',
  'exercise_personal_records',
  'recovery_metrics',
  'workout_day_exercises',
  'workout_days',
  'workout_plans',
  'password_reset_tokens',
  'refresh_tokens',
  'athletes',
  'users',
];

/** Reset every table + identity sequence between tests for isolation. */
export async function truncateAll(db: DrizzleDB): Promise<void> {
  const list = TABLES.map((t) => `"${t}"`).join(', ');
  await db.execute(
    sql.raw(`TRUNCATE TABLE ${list} RESTART IDENTITY CASCADE`),
  );
}
