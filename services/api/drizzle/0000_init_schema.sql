CREATE TABLE "athletes" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"age" integer NOT NULL,
	"gender" varchar(10) NOT NULL,
	"training_experience" varchar(12) NOT NULL,
	"rpe_calibration_factor" real NOT NULL
);
--> statement-breakpoint
CREATE TABLE "exercises" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"equipment" varchar(100) NOT NULL,
	"primary_muscles" text[] NOT NULL,
	"secondary_muscles" text[] NOT NULL,
	"injury_risk_level" real NOT NULL,
	"joint_stress_areas" varchar(255)[] NOT NULL,
	"movement_pattern" varchar(100) NOT NULL,
	"exercise_type" varchar(50) NOT NULL,
	"complexity_score" real NOT NULL,
	CONSTRAINT "exercises_name_unique" UNIQUE("name")
);
--> statement-breakpoint
CREATE TABLE "form_quality_trends" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"exercise_id" integer NOT NULL,
	"date" timestamp NOT NULL,
	"average_form_score" real NOT NULL,
	"sets_analyzed" integer NOT NULL,
	"degradation_rate" real,
	"high_rpe_poor_form_count" integer NOT NULL
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
	"tempo" varchar(20),
	"notes" text,
	"is_primary" boolean NOT NULL,
	"progression_scheme" varchar(50),
	"warm_up_sets" integer NOT NULL,
	"auto_generate_warmups" boolean NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workout_days" (
	"id" serial PRIMARY KEY NOT NULL,
	"workout_plan_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"day_of_week" integer,
	"order_in_week" integer NOT NULL,
	"target_muscle_groups" jsonb NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workout_plans" (
	"id" serial PRIMARY KEY NOT NULL,
	"athlete_id" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"training_type" varchar(50) NOT NULL,
	"periodization_model" varchar(50) NOT NULL,
	"frequency" integer NOT NULL,
	"duration_weeks" integer NOT NULL,
	"start_date" timestamp,
	"end_date" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"is_active" boolean NOT NULL
);
--> statement-breakpoint
ALTER TABLE "athletes" ADD CONSTRAINT "athletes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "form_quality_trends" ADD CONSTRAINT "form_quality_trends_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "form_quality_trends" ADD CONSTRAINT "form_quality_trends_exercise_id_exercises_id_fk" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD CONSTRAINT "workout_day_exercises_workout_day_id_workout_days_id_fk" FOREIGN KEY ("workout_day_id") REFERENCES "public"."workout_days"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD CONSTRAINT "workout_day_exercises_exercise_id_exercises_id_fk" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_days" ADD CONSTRAINT "workout_days_workout_plan_id_workout_plans_id_fk" FOREIGN KEY ("workout_plan_id") REFERENCES "public"."workout_plans"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_plans" ADD CONSTRAINT "workout_plans_athlete_id_athletes_id_fk" FOREIGN KEY ("athlete_id") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;