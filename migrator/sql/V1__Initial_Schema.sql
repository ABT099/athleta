-- ============================================
-- API: Public Schema
-- ============================================

CREATE TABLE "users" (
	"id" serial PRIMARY KEY NOT NULL,
	"email" varchar(255) NOT NULL,
	"password" varchar(255),
	"first_name" varchar(255) NOT NULL,
	"last_name" varchar(255) NOT NULL,
	"role" varchar(10) NOT NULL,
	"google_id" varchar(255),
	"apple_id" varchar(255),
	"created_at" timestamp DEFAULT now() NOT NULL,
	"has_initial_plan" boolean DEFAULT false NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email"),
	CONSTRAINT "users_google_id_unique" UNIQUE("google_id"),
	CONSTRAINT "users_apple_id_unique" UNIQUE("apple_id")
);

CREATE TABLE "athletes" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"age" integer NOT NULL,
	"gender" varchar(10) NOT NULL,
	"training_experience" varchar(12) NOT NULL,
	"rpe_calibration_factor" real NOT NULL,
	"body_weight_kg" real,
	CONSTRAINT "athletes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action
);

CREATE TYPE exercise_type_enum AS ENUM (
    'compound', 'isolation'
);

CREATE TYPE intensity_category_enum AS ENUM (
    'compound_heavy', 'compound_moderate', 'isolation'
);

CREATE TABLE "exercises" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"equipment" varchar(100) NOT NULL,
	"injury_risk_level" real NOT NULL,
	"joint_stress_areas" varchar(255)[] NOT NULL,
	"movement_pattern" varchar(100) NOT NULL,
	"exercise_type" exercise_type_enum NOT NULL,
	"complexity_score" real NOT NULL DEFAULT 1.0,
	"intensity_category" intensity_category_enum NOT NULL DEFAULT 'isolation',
	CONSTRAINT "exercises_name_unique" UNIQUE("name")
);

CREATE TYPE training_type_enum AS ENUM (
    'hypertrophy', 'strength', 'hybrid'
);

CREATE TYPE periodization_model_enum AS ENUM (
    'linear', 'undulating', 'block'
);

CREATE TABLE "workout_plans" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"training_type" training_type_enum NOT NULL DEFAULT 'hypertrophy',
	"periodization_model" periodization_model_enum NOT NULL DEFAULT 'linear',
	"frequency" integer NOT NULL,
	"duration_weeks" integer NOT NULL,
	"start_date" timestamp,
	"end_date" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"is_active" boolean NOT NULL,
	"focus_areas" jsonb,
	CONSTRAINT "workout_plans_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action
);

CREATE TABLE "workout_days" (
	"id" serial PRIMARY KEY NOT NULL,
	"workout_plan_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"day_of_week" integer,
	"order_in_week" integer NOT NULL,
	"target_muscle_groups" jsonb NOT NULL,
	CONSTRAINT "workout_days_workout_plan_id_workout_plans_id_fk" FOREIGN KEY ("workout_plan_id") REFERENCES "public"."workout_plans"("id") ON DELETE no action ON UPDATE no action
);

CREATE TYPE set_type_enum AS ENUM (
    'straight', 'drop_set', 'rest_pause', 'myo_reps', 
    'cluster_set', 'superset_antagonist', 'pre_exhaust'
);

CREATE TYPE rep_style_enum AS ENUM (
    'normal', 'lengthened_partials', 'tempo_eccentric', 
    'tempo_paused', 'eccentric_overload'
);

CREATE TABLE "workout_day_exercises" (
	"id" serial PRIMARY KEY NOT NULL,
	"workout_day_id" integer NOT NULL,
	"exercise_id" integer NOT NULL,
	"order_in_workout" integer NOT NULL,
	"target_sets_min" integer NOT NULL,
	"target_sets_max" integer NOT NULL,
	"target_reps_min" integer NOT NULL,
	"target_reps_max" integer NOT NULL,
	"target_rpe" real,
	"target_rir" integer,
	"rest_period_seconds" integer,
	"tempo" varchar(20),
	"notes" text,
	"is_primary" boolean NOT NULL,
	"progression_scheme" varchar(50),
	"warm_up_sets" integer NOT NULL,
	"auto_generate_warmups" boolean NOT NULL,
	"set_type" set_type_enum NOT NULL DEFAULT 'straight',
	"rep_style" rep_style_enum NOT NULL DEFAULT 'normal',
	"set_type_params" jsonb,
	"rep_style_params" jsonb,
	CONSTRAINT "workout_day_exercises_workout_day_id_workout_days_id_fk" FOREIGN KEY ("workout_day_id") REFERENCES "public"."workout_days"("id") ON DELETE no action ON UPDATE no action,
	CONSTRAINT "workout_day_exercises_exercise_id_exercises_id_fk" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id") ON DELETE no action ON UPDATE no action
);

CREATE TABLE "refresh_tokens" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"token" text NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"used_at" timestamp,
	CONSTRAINT "refresh_tokens_token_unique" UNIQUE("token"),
	CONSTRAINT "refresh_tokens_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action
);

CREATE TABLE "password_reset_tokens" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"code" text NOT NULL,
	"verified" boolean DEFAULT false NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "password_reset_tokens_userId_unique" UNIQUE("user_id"),
	CONSTRAINT "password_reset_tokens_code_unique" UNIQUE("code"),
	CONSTRAINT "password_reset_tokens_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action
);

CREATE TABLE "muscle_groups" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(50) NOT NULL,
	"display_name" varchar(100) NOT NULL,
	"size" varchar(20) NOT NULL,
	"base_recovery_hours" integer NOT NULL,
	"is_compound_target" boolean DEFAULT false NOT NULL,
	"antagonist_id" integer,
	CONSTRAINT "muscle_groups_name_unique" UNIQUE("name"),
	CONSTRAINT "muscle_groups_antagonist_id_muscle_groups_id_fk" FOREIGN KEY ("antagonist_id") REFERENCES "public"."muscle_groups"("id") ON DELETE no action ON UPDATE no action
);

CREATE TABLE "exercise_muscles" (
	"id" serial PRIMARY KEY NOT NULL,
	"exercise_id" integer NOT NULL,
	"muscle_group_id" integer NOT NULL,
	"role" varchar(20) NOT NULL,
	CONSTRAINT "exercise_muscles_exercise_id_exercises_id_fk" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id") ON DELETE cascade ON UPDATE no action,
	CONSTRAINT "exercise_muscles_muscle_group_id_muscle_groups_id_fk" FOREIGN KEY ("muscle_group_id") REFERENCES "public"."muscle_groups"("id") ON DELETE cascade ON UPDATE no action
);

-- Create indexes for API tables
CREATE INDEX "password_reset_tokens_expires_at_idx" ON "password_reset_tokens" USING btree ("expires_at");
CREATE INDEX "refresh_tokens_user_id_idx" ON "refresh_tokens" USING btree ("user_id");
CREATE INDEX "refresh_tokens_expires_at_idx" ON "refresh_tokens" USING btree ("expires_at");
CREATE INDEX "exercise_muscles_exercise_idx" ON "exercise_muscles" USING btree ("exercise_id");
CREATE INDEX "exercise_muscles_muscle_idx" ON "exercise_muscles" USING btree ("muscle_group_id");

-- Seed muscle groups data
-- First pass: Insert muscles without antagonist relationships
INSERT INTO muscle_groups (name, display_name, size, base_recovery_hours, is_compound_target) VALUES
-- Chest (3)
('upper_chest', 'Upper Chest', 'large', 72, true),
('mid_chest', 'Mid Chest', 'large', 72, true),
('lower_chest', 'Lower Chest', 'large', 72, true),
-- Back (4)
('lats', 'Lats', 'large', 72, true),
('upper_traps', 'Upper Traps', 'medium', 60, false),
('mid_back', 'Mid Back', 'medium', 60, true),
('lower_traps', 'Lower Traps', 'medium', 60, false),
-- Shoulders (3)
('anterior_delt', 'Front Delts', 'medium', 60, true),
('lateral_delt', 'Side Delts', 'small', 48, false),
('posterior_delt', 'Rear Delts', 'small', 48, false),
-- Arms (3)
('biceps', 'Biceps', 'small', 48, false),
('triceps', 'Triceps', 'small', 48, false),
('forearms', 'Forearms', 'small', 48, false),
-- Legs (5)
('quadriceps', 'Quadriceps', 'large', 72, true),
('hamstrings', 'Hamstrings', 'large', 72, true),
('glutes', 'Glutes', 'large', 72, true),
('hip_flexors', 'Hip Flexors', 'medium', 60, false),
('calves', 'Calves', 'small', 48, false),
-- Core (2)
('abs', 'Abs', 'medium', 48, false),
('erector_spinae', 'Lower Back', 'medium', 60, true);

-- Second pass: Update antagonist relationships
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_back') WHERE name = 'upper_chest';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_back') WHERE name = 'mid_chest';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'lats') WHERE name = 'lower_chest';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'lower_chest') WHERE name = 'lats';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_chest') WHERE name = 'mid_back';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'posterior_delt') WHERE name = 'anterior_delt';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'anterior_delt') WHERE name = 'posterior_delt';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'triceps') WHERE name = 'biceps';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'biceps') WHERE name = 'triceps';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'hamstrings') WHERE name = 'quadriceps';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'quadriceps') WHERE name = 'hamstrings';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'hip_flexors') WHERE name = 'glutes';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'glutes') WHERE name = 'hip_flexors';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'erector_spinae') WHERE name = 'abs';
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'abs') WHERE name = 'erector_spinae';

-- ============================================
-- AI ENGINE: ai_analysis Schema
-- ============================================

CREATE SCHEMA IF NOT EXISTS ai_analysis;

CREATE TYPE training_phase_enum AS ENUM (
    'accumulation', 'intensification', 'realization'
);

CREATE TYPE sleep_quality_enum AS ENUM (
    'poor', 'not_bad', 'good', 'excellent'
);

CREATE TABLE ai_analysis.plan_entries (
    id serial PRIMARY KEY NOT NULL,
    workout_plan_id integer NOT NULL,
    week_number integer NOT NULL,
    start_date timestamp NOT NULL,
    end_date timestamp NOT NULL,
    training_phase training_phase_enum NOT NULL,
    target_volume_multiplier real NOT NULL,
    target_intensity_multiplier real NOT NULL,
    is_deload_week integer NOT NULL,
    ai_adjustments jsonb,
    completed_workouts integer NOT NULL,
    average_rpe real,
    average_recovery_score real,
    total_volume real,
    notes text,
    CONSTRAINT plan_entries_workout_plan_id_fkey FOREIGN KEY (workout_plan_id) REFERENCES public.workout_plans(id)
);
CREATE INDEX ix_plan_entries_id ON ai_analysis.plan_entries (id);

CREATE TABLE ai_analysis.workout_sessions (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    workout_day_id integer NOT NULL,
    session_date timestamp NOT NULL,
    duration_minutes integer,
    overall_rpe real,
    overall_feeling varchar(50),
    notes text,
    total_volume real,
    estimated_fatigue real,
    CONSTRAINT workout_sessions_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id),
    CONSTRAINT workout_sessions_workout_day_id_fkey FOREIGN KEY (workout_day_id) REFERENCES public.workout_days(id)
);
CREATE INDEX ix_workout_sessions_id ON ai_analysis.workout_sessions (id);

CREATE TABLE ai_analysis.exercise_sets (
    id serial PRIMARY KEY NOT NULL,
    workout_session_id integer NOT NULL,
    exercise_id integer NOT NULL,
    set_number integer NOT NULL,
    weight real NOT NULL,
    reps integer NOT NULL,
    rpe real,
    rir integer,
    form_quality varchar(50),
    notes text,
    created_at timestamp NOT NULL,
    set_type_used set_type_enum,
    rep_style_used rep_style_enum,
    technique_details jsonb,
    CONSTRAINT exercise_sets_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id),
    CONSTRAINT exercise_sets_workout_session_id_fkey FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id)
);
CREATE INDEX ix_exercise_sets_id ON ai_analysis.exercise_sets (id);

CREATE TABLE ai_analysis.recovery_metrics (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    date timestamp NOT NULL,
    sleep_quality sleep_quality_enum NOT NULL,
    sleep_hours real,
    overall_soreness integer,
    muscle_soreness text,
    stress_level integer,
    energy_level integer,
    readiness_score real,
    nutrition_adherence varchar(50),
    hydration_level varchar(50),
    notes text,
    created_at timestamp NOT NULL,
    CONSTRAINT recovery_metrics_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id)
);
CREATE INDEX ix_recovery_metrics_date ON ai_analysis.recovery_metrics (date);
CREATE INDEX ix_recovery_metrics_id ON ai_analysis.recovery_metrics (id);

CREATE TABLE ai_analysis.athlete_rpe_calibration (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    exercise_id integer NOT NULL,
    reported_rpe real NOT NULL,
    predicted_rir real NOT NULL,
    actual_rir real,
    weight_used real NOT NULL,
    reps_completed integer NOT NULL,
    session_date timestamp NOT NULL,
    calibration_accuracy real,
    created_at timestamp NOT NULL,
    CONSTRAINT athlete_rpe_calibration_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE,
    CONSTRAINT athlete_rpe_calibration_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
);
CREATE INDEX ix_athlete_rpe_calibration_athlete_id ON ai_analysis.athlete_rpe_calibration (athlete_id);
CREATE INDEX ix_athlete_rpe_calibration_id ON ai_analysis.athlete_rpe_calibration (id);

CREATE TABLE ai_analysis.performance_trends (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    workout_session_id integer NOT NULL,
    session_date timestamp NOT NULL,
    total_volume real NOT NULL,
    average_intensity real NOT NULL,
    average_rpe real NOT NULL,
    readiness_score real NOT NULL,
    performance_score real NOT NULL,
    fatigue_index real NOT NULL,
    volume_load real NOT NULL,
    training_monotony real,
    training_strain real,
    acute_load real,
    chronic_load real,
    acwr real,
    deload_triggered boolean NOT NULL DEFAULT false,
    deload_reason text,
    created_at timestamp NOT NULL,
    CONSTRAINT performance_trends_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE,
    CONSTRAINT performance_trends_workout_session_id_fkey FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id) ON DELETE CASCADE
);
CREATE INDEX ix_performance_trends_athlete_id ON ai_analysis.performance_trends (athlete_id);
CREATE INDEX ix_performance_trends_id ON ai_analysis.performance_trends (id);
CREATE INDEX ix_performance_trends_session_date ON ai_analysis.performance_trends (session_date);

CREATE TABLE ai_analysis.exercise_progression_tracking (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    exercise_id integer NOT NULL,
    workout_session_id integer NOT NULL,
    session_date timestamp NOT NULL,
    weight_used real NOT NULL,
    total_reps integer NOT NULL,
    total_sets integer NOT NULL,
    average_rpe real NOT NULL,
    estimated_1rm real NOT NULL,
    volume_load real NOT NULL,
    progression_state varchar(50) NOT NULL,
    weeks_at_weight integer NOT NULL DEFAULT 0,
    sessions_at_weight integer NOT NULL DEFAULT 0,
    rep_progression_target integer,
    weight_progression_ready boolean NOT NULL DEFAULT false,
    familiarity_score real NOT NULL DEFAULT 0.0,
    created_at timestamp NOT NULL,
    CONSTRAINT exercise_progression_tracking_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE,
    CONSTRAINT exercise_progression_tracking_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE,
    CONSTRAINT exercise_progression_tracking_workout_session_id_fkey FOREIGN KEY (workout_session_id) REFERENCES ai_analysis.workout_sessions(id) ON DELETE CASCADE
);
CREATE INDEX ix_exercise_progression_tracking_athlete_id ON ai_analysis.exercise_progression_tracking (athlete_id);
CREATE INDEX ix_exercise_progression_tracking_exercise_id ON ai_analysis.exercise_progression_tracking (exercise_id);
CREATE INDEX ix_exercise_progression_tracking_id ON ai_analysis.exercise_progression_tracking (id);

CREATE TABLE ai_analysis.ml_model_metadata (
    id serial PRIMARY KEY NOT NULL,
    model_name varchar(255) NOT NULL,
    model_type varchar(100) NOT NULL,
    athlete_id integer,
    version varchar(50) NOT NULL,
    training_date timestamp NOT NULL,
    training_samples integer NOT NULL,
    feature_count integer NOT NULL,
    target_count integer NOT NULL,
    model_path text NOT NULL,
    performance_metrics text,
    feature_importance text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    CONSTRAINT ml_model_metadata_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
);
CREATE INDEX ix_ml_model_metadata_athlete_id ON ai_analysis.ml_model_metadata (athlete_id);
CREATE INDEX ix_ml_model_metadata_id ON ai_analysis.ml_model_metadata (id);
CREATE INDEX ix_ml_model_metadata_model_name ON ai_analysis.ml_model_metadata (model_name);

CREATE TABLE ai_analysis.form_quality_trends (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    exercise_id integer NOT NULL,
    date timestamp NOT NULL,
    average_form_score real NOT NULL,
    sets_analyzed integer NOT NULL,
    degradation_rate real,
    high_rpe_poor_form_count integer NOT NULL DEFAULT 0,
    CONSTRAINT form_quality_trends_athlete_id_athletes_id_fk FOREIGN KEY (athlete_id) REFERENCES public.athletes(id),
    CONSTRAINT form_quality_trends_exercise_id_exercises_id_fk FOREIGN KEY (exercise_id) REFERENCES public.exercises(id)
);
CREATE INDEX ix_form_quality_trends_id ON ai_analysis.form_quality_trends (id);
CREATE INDEX ix_form_quality_trends_athlete_exercise_date ON ai_analysis.form_quality_trends (athlete_id, exercise_id, date);

CREATE TABLE ai_analysis.exercise_personal_records (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    exercise_id integer NOT NULL,
    one_rep_max real,
    one_rm_date timestamp,
    three_rep_max real,
    three_rm_date timestamp,
    five_rep_max real,
    five_rm_date timestamp,
    eight_rep_max real,
    eight_rm_date timestamp,
    ten_rep_max real,
    ten_rm_date timestamp,
    twelve_rep_max real,
    twelve_rm_date timestamp,
    max_volume_session real,
    max_volume_date timestamp,
    max_total_reps integer,
    max_reps_date timestamp,
    total_pr_count integer NOT NULL DEFAULT 0,
    last_pr_date timestamp,
    created_at timestamp NOT NULL DEFAULT now(),
    updated_at timestamp NOT NULL DEFAULT now(),
    CONSTRAINT uq_athlete_exercise_pr UNIQUE (athlete_id, exercise_id),
    CONSTRAINT exercise_personal_records_athlete_id_fk FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE,
    CONSTRAINT exercise_personal_records_exercise_id_fk FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
);
CREATE INDEX idx_exercise_personal_records_athlete_id ON ai_analysis.exercise_personal_records (athlete_id);
CREATE INDEX idx_exercise_personal_records_exercise_id ON ai_analysis.exercise_personal_records (exercise_id);

CREATE TABLE ai_analysis.workout_prescription_history (
    id serial PRIMARY KEY NOT NULL,
    athlete_id integer NOT NULL,
    workout_day_id integer NOT NULL,
    exercise_id integer NOT NULL,
    prescribed_date timestamp NOT NULL,
    prescribed_weight real,
    prescribed_sets integer,
    prescribed_reps_min integer,
    prescribed_reps_max integer,
    prescribed_rpe real,
    prescribed_rir integer,
    rest_period_seconds integer,
    set_type varchar(50),
    rep_style varchar(50),
    set_type_params jsonb,
    rep_style_params jsonb,
    volume_multiplier real NOT NULL,
    intensity_multiplier real NOT NULL,
    adjustment_reason text,
    week_number integer,
    readiness_score real,
    training_phase varchar(50),
    created_at timestamp NOT NULL,
    CONSTRAINT workout_prescription_history_athlete_id_fkey FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE,
    CONSTRAINT workout_prescription_history_workout_day_id_fkey FOREIGN KEY (workout_day_id) REFERENCES public.workout_days(id) ON DELETE CASCADE,
    CONSTRAINT workout_prescription_history_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.exercises(id) ON DELETE CASCADE
);
CREATE INDEX idx_athlete_workout_exercise_date ON ai_analysis.workout_prescription_history (athlete_id, workout_day_id, exercise_id, prescribed_date);
CREATE INDEX idx_athlete_exercise ON ai_analysis.workout_prescription_history (athlete_id, exercise_id);

