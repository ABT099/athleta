# Migration Scripts

This directory contains scripts to run database migrations in the correct order.

## Migration Order

1. **NestJS migrations (Drizzle)** - Must run first
   - Creates: `users`, `athletes`, `exercises`, `workout_plans`, `workout_days`, `workout_day_exercises`

2. **AI Engine migrations (Alembic)** - Runs after NestJS
   - Creates: `plan_entries`, `workout_sessions`, `exercise_sets`, `recovery_metrics`, `athlete_rpe_calibration`, `performance_trends`, `exercise_progression_tracking`, `ml_model_metadata`

## Usage

Run the migration script from the project root:

```bash
node scripts/migrate.js
```

This script works on all platforms (Windows, Linux, Mac).

## Prerequisites

### NestJS (API)
- Node.js installed
- Dependencies installed (`npm install` in `services/api`)
- `DATABASE_URL` environment variable set

### AI Engine
- Python installed
- Dependencies installed (virtual environment recommended)
- `DATABASE_URL` environment variable set (same as NestJS)

## What the Scripts Do

1. **Check directories exist** - Verifies both `services/api` and `services/ai-engine` exist
2. **Run NestJS migrations** - Uses `drizzle-kit push` to apply Drizzle migrations
3. **Run AI Engine migrations** - Uses `alembic upgrade head` to apply Alembic migrations
4. **Error handling** - Stops on first error and reports which step failed

## Manual Migration

If you prefer to run migrations manually:

### NestJS (Drizzle)
```bash
cd services/api
npx drizzle-kit push
```

### AI Engine (Alembic)
```bash
cd services/ai-engine
alembic upgrade head
```

## Troubleshooting

### NestJS migrations fail
- Check that `DATABASE_URL` is set correctly
- Ensure database is running and accessible
- Verify `services/api/package.json` exists
- Run `npm install` in `services/api` if needed

### AI Engine migrations fail
- Check that `DATABASE_URL` is set correctly (same as NestJS)
- Ensure NestJS migrations ran successfully first
- Verify `services/ai-engine/alembic.ini` exists
- Activate virtual environment if using one: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)

### Migration order errors
- Always run NestJS migrations first
- AI Engine migrations depend on NestJS tables existing
- If you see foreign key errors, ensure NestJS migrations completed successfully

