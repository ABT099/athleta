-- ============================================
-- V6: Remove the exercise library from Postgres
-- ============================================
--
-- The exercise domain now lives entirely in exercise-service, backed by Neo4j.
-- The api and auto-regulation-service reference exercises by integer ID only; those IDs are
-- preserved by the exercise-service `migrate` command (Postgres -> Neo4j).
--
-- After this migration:
--   * public.workout_day_exercises.exercise_id and every
--     ai_analysis.*.exercise_id become plain integer columns that softly
--     reference exercise-service IDs (no foreign key, no local table).
--
-- PREREQUISITE: run the exercise-service `migrate` command BEFORE applying
-- this migration, otherwise the exercise library data is lost.

-- 1. Drop foreign keys that reference public.exercises.
ALTER TABLE public.workout_day_exercises
    DROP CONSTRAINT IF EXISTS workout_day_exercises_exercise_id_exercises_id_fk;

ALTER TABLE ai_analysis.exercise_sets
    DROP CONSTRAINT IF EXISTS exercise_sets_exercise_id_fkey;

ALTER TABLE ai_analysis.athlete_rpe_calibration
    DROP CONSTRAINT IF EXISTS athlete_rpe_calibration_exercise_id_fkey;

ALTER TABLE ai_analysis.exercise_progression_tracking
    DROP CONSTRAINT IF EXISTS exercise_progression_tracking_exercise_id_fkey;

ALTER TABLE ai_analysis.form_quality_trends
    DROP CONSTRAINT IF EXISTS form_quality_trends_exercise_id_exercises_id_fk;

ALTER TABLE ai_analysis.exercise_personal_records
    DROP CONSTRAINT IF EXISTS exercise_personal_records_exercise_id_fk;

ALTER TABLE ai_analysis.workout_prescription_history
    DROP CONSTRAINT IF EXISTS workout_prescription_history_exercise_id_fkey;

-- 2. Drop the exercise library tables. exercise_muscles references both
--    exercises and muscle_groups, so it goes first; CASCADE clears the
--    self-referential muscle_groups antagonist FK.
DROP TABLE IF EXISTS public.exercise_muscles;
DROP TABLE IF EXISTS public.muscle_groups CASCADE;
DROP TABLE IF EXISTS public.exercises CASCADE;

-- 3. Drop enums that only the exercises table used. Exercise type and
--    intensity category are now string fields owned by exercise-service.
DROP TYPE IF EXISTS intensity_category_enum;
DROP TYPE IF EXISTS exercise_type_enum;
