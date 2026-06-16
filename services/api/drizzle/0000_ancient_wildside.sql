CREATE TYPE "public"."periodization_model_enum" AS ENUM('linear', 'undulating', 'block');--> statement-breakpoint
CREATE TYPE "public"."rep_style_enum" AS ENUM('normal', 'lengthened_partials', 'tempo_eccentric', 'tempo_paused', 'eccentric_overload');--> statement-breakpoint
CREATE TYPE "public"."set_type_enum" AS ENUM('straight', 'drop_set', 'rest_pause', 'myo_reps', 'cluster_set', 'superset_antagonist', 'pre_exhaust');--> statement-breakpoint
CREATE TYPE "public"."sleep_quality_enum" AS ENUM('poor', 'not_bad', 'good', 'excellent');--> statement-breakpoint
CREATE TYPE "public"."training_phase_enum" AS ENUM('accumulation', 'intensification', 'realization');--> statement-breakpoint
CREATE TYPE "public"."training_type_enum" AS ENUM('hypertrophy', 'strength', 'hybrid');--> statement-breakpoint
CREATE TABLE "athletes" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"age" integer NOT NULL,
	"gender" varchar(10) NOT NULL,
	"training_experience" varchar(12) NOT NULL,
	"rpe_calibration_factor" real DEFAULT 1 NOT NULL,
	"body_weight_kg" real
);
--> statement-breakpoint
CREATE TABLE "exercise_personal_records" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"exercise_id" integer NOT NULL,
	"one_rep_max" real,
	"one_rm_date" timestamp,
	"three_rep_max" real,
	"three_rm_date" timestamp,
	"five_rep_max" real,
	"five_rm_date" timestamp,
	"eight_rep_max" real,
	"eight_rm_date" timestamp,
	"ten_rep_max" real,
	"ten_rm_date" timestamp,
	"twelve_rep_max" real,
	"twelve_rm_date" timestamp,
	"max_volume_session" real,
	"max_volume_date" timestamp,
	"max_total_reps" integer,
	"max_reps_date" timestamp,
	"total_pr_count" integer DEFAULT 0 NOT NULL,
	"last_pr_date" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "uq_athlete_exercise_pr" UNIQUE("athlete_id","exercise_id")
);
--> statement-breakpoint
CREATE TABLE "exercise_sets" (
	"id" serial PRIMARY KEY NOT NULL,
	"workout_session_id" integer NOT NULL,
	"exercise_id" integer NOT NULL,
	"set_number" integer NOT NULL,
	"weight" real NOT NULL,
	"reps" integer NOT NULL,
	"rpe" real,
	"rir" integer,
	"form_quality" varchar(50),
	"notes" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"set_type_used" "set_type_enum",
	"rep_style_used" "rep_style_enum",
	"technique_details" jsonb
);
--> statement-breakpoint
CREATE TABLE "password_reset_tokens" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"code" text NOT NULL,
	"verified" boolean DEFAULT false NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "password_reset_tokens_userId_unique" UNIQUE("user_id"),
	CONSTRAINT "password_reset_tokens_code_unique" UNIQUE("code")
);
--> statement-breakpoint
CREATE TABLE "recovery_metrics" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"date" timestamp NOT NULL,
	"sleep_quality" "sleep_quality_enum" NOT NULL,
	"sleep_hours" real,
	"overall_soreness" integer,
	"muscle_soreness" text,
	"stress_level" integer,
	"energy_level" integer,
	"readiness_score" real,
	"nutrition_adherence" varchar(50),
	"hydration_level" varchar(50),
	"notes" text,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "refresh_tokens" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"token" text NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"used_at" timestamp,
	CONSTRAINT "refresh_tokens_token_unique" UNIQUE("token")
);
--> statement-breakpoint
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
--> statement-breakpoint
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
	"notes" text,
	"is_primary" boolean NOT NULL,
	"progression_scheme" varchar(50),
	"warm_up_sets" integer NOT NULL,
	"set_type" "set_type_enum" DEFAULT 'straight' NOT NULL,
	"rep_style" "rep_style_enum" DEFAULT 'normal' NOT NULL,
	"set_type_params" jsonb,
	"rep_style_params" jsonb
);
--> statement-breakpoint
CREATE TABLE "workout_days" (
	"id" serial PRIMARY KEY NOT NULL,
	"workout_plan_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"day_of_week" integer,
	"order_in_week" integer NOT NULL,
	"muscle_image_url" varchar(512)
);
--> statement-breakpoint
CREATE TABLE "workout_plans" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text,
	"training_type" "training_type_enum" DEFAULT 'hypertrophy' NOT NULL,
	"periodization_model" "periodization_model_enum" DEFAULT 'linear' NOT NULL,
	"frequency" integer NOT NULL,
	"duration_weeks" integer NOT NULL,
	"start_date" timestamp DEFAULT now() NOT NULL,
	"end_date" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"focus_areas" jsonb
);
--> statement-breakpoint
CREATE TABLE "workout_sessions" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"workout_day_id" integer NOT NULL,
	"session_date" timestamp NOT NULL,
	"duration_minutes" integer,
	"overall_rpe" real,
	"overall_feeling" varchar(50),
	"notes" text,
	"total_volume" real,
	"estimated_fatigue" real
);
--> statement-breakpoint
ALTER TABLE "athletes" ADD CONSTRAINT "athletes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "exercise_personal_records" ADD CONSTRAINT "exercise_personal_records_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "exercise_sets" ADD CONSTRAINT "exercise_sets_workout_session_id_workout_sessions_id_fk" FOREIGN KEY ("workout_session_id") REFERENCES "public"."workout_sessions"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "password_reset_tokens" ADD CONSTRAINT "password_reset_tokens_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "recovery_metrics" ADD CONSTRAINT "recovery_metrics_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD CONSTRAINT "workout_day_exercises_workout_day_id_workout_days_id_fk" FOREIGN KEY ("workout_day_id") REFERENCES "public"."workout_days"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_days" ADD CONSTRAINT "workout_days_workout_plan_id_workout_plans_id_fk" FOREIGN KEY ("workout_plan_id") REFERENCES "public"."workout_plans"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_plans" ADD CONSTRAINT "workout_plans_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_sessions" ADD CONSTRAINT "workout_sessions_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_sessions" ADD CONSTRAINT "workout_sessions_workout_day_id_workout_days_id_fk" FOREIGN KEY ("workout_day_id") REFERENCES "public"."workout_days"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "exercise_personal_records_athlete_id_idx" ON "exercise_personal_records" USING btree ("athlete_id" int4_ops);--> statement-breakpoint
CREATE INDEX "exercise_sets_workout_session_id_idx" ON "exercise_sets" USING btree ("workout_session_id" int4_ops);--> statement-breakpoint
CREATE INDEX "password_reset_tokens_expires_at_idx" ON "password_reset_tokens" USING btree ("expires_at" timestamp_ops);--> statement-breakpoint
CREATE INDEX "recovery_metrics_athlete_id_idx" ON "recovery_metrics" USING btree ("athlete_id" int4_ops);--> statement-breakpoint
CREATE INDEX "refresh_tokens_expires_at_idx" ON "refresh_tokens" USING btree ("expires_at" timestamp_ops);--> statement-breakpoint
CREATE INDEX "refresh_tokens_user_id_idx" ON "refresh_tokens" USING btree ("user_id" int4_ops);--> statement-breakpoint
CREATE INDEX "workout_sessions_athlete_id_idx" ON "workout_sessions" USING btree ("athlete_id" int4_ops);