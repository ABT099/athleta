import 'dotenv/config';
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  out: './drizzle',
  schema: './src/db/schema.ts',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
  casing: 'snake_case',
  strict: true,
  verbose: true,
  tablesFilter: [
      '!alembic_version',
      '!plan_entries',
      '!workout_sessions',
      '!exercise_sets',
      '!recovery_metrics',
      '!athlete_rpe_calibration',
      '!performance_trends',
      '!exercise_progression_tracking',
      '!ml_model_metadata',
      '!exercise_personal_records',
    ], // Exclude alembic_version table from Drizzle operations
});
