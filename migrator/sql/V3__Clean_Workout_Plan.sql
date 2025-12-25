ALTER TABLE workout_plans
ALTER COLUMN "is_active" SET DEFAULT true;

ALTER TABLE workout_plans
ALTER COLUMN "start_date" SET DEFAULT now();

ALTER TABLE workout_day_exercises DROP COLUMN auto_generate_warmups;

ALTER TABLE workout_days ADD COLUMN muscle_image_url VARCHAR(512);
ALTER TABLE workout_days DROP COLUMN target_muscle_groups;

ALTER TABLE workout_day_exercises DROP COLUMN tempo;