CREATE TABLE "athletes" (
	"id" serial PRIMARY KEY NOT NULL,
	"userId" integer NOT NULL,
	"age" integer NOT NULL,
	"gender" varchar(10) NOT NULL,
	"trainingExperience" varchar(12) NOT NULL,
	"rpeCalibrationFactor" real NOT NULL
);
--> statement-breakpoint
CREATE TABLE "exercises" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"equipment" varchar(100) NOT NULL,
	"primaryMuscles" text[] NOT NULL,
	"secondaryMuscles" text[] NOT NULL,
	"injuryRiskLevel" integer NOT NULL,
	"jointStressAreas" varchar(255)[] NOT NULL,
	"movementPattern" varchar(100) NOT NULL,
	"isCompound" integer NOT NULL,
	"exerciseType" varchar(50) NOT NULL,
	"complexityScore" real NOT NULL,
	CONSTRAINT "exercises_name_unique" UNIQUE("name")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" serial PRIMARY KEY NOT NULL,
	"email" varchar(255) NOT NULL,
	"password" varchar(255) NOT NULL,
	"firstName" varchar(255) NOT NULL,
	"lastName" varchar(255) NOT NULL,
	"role" varchar(10) NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "workout_day_exercises" (
	"id" serial PRIMARY KEY NOT NULL,
	"workoutDayId" integer NOT NULL,
	"exerciseId" integer NOT NULL,
	"orderInWorkout" integer NOT NULL,
	"targetSets" integer NOT NULL,
	"targetRepsMin" integer NOT NULL,
	"targetRepsMax" integer NOT NULL,
	"targetRpe" real,
	"targetRir" integer,
	"restPeriodSeconds" integer,
	"tempo" varchar(20),
	"notes" text,
	"isPrimary" boolean NOT NULL,
	"progressionScheme" varchar(50)
);
--> statement-breakpoint
CREATE TABLE "workout_days" (
	"id" serial PRIMARY KEY NOT NULL,
	"workoutPlanId" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"dayOfWeek" integer,
	"orderInWeek" integer NOT NULL,
	"targetMuscleGroups" jsonb NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workout_plans" (
	"id" serial PRIMARY KEY NOT NULL,
	"athleteId" integer NOT NULL,
	"name" varchar(255) NOT NULL,
	"description" text NOT NULL,
	"trainingType" varchar(50) NOT NULL,
	"periodizationModel" varchar(50) NOT NULL,
	"frequency" integer NOT NULL,
	"durationWeeks" integer NOT NULL,
	"splitType" varchar(100) NOT NULL,
	"startDate" timestamp,
	"endDate" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"isActive" boolean NOT NULL
);
--> statement-breakpoint
ALTER TABLE "athletes" ADD CONSTRAINT "athletes_userId_users_id_fk" FOREIGN KEY ("userId") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD CONSTRAINT "workout_day_exercises_workoutDayId_workout_days_id_fk" FOREIGN KEY ("workoutDayId") REFERENCES "public"."workout_days"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD CONSTRAINT "workout_day_exercises_exerciseId_exercises_id_fk" FOREIGN KEY ("exerciseId") REFERENCES "public"."exercises"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_days" ADD CONSTRAINT "workout_days_workoutPlanId_workout_plans_id_fk" FOREIGN KEY ("workoutPlanId") REFERENCES "public"."workout_plans"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workout_plans" ADD CONSTRAINT "workout_plans_athleteId_athletes_id_fk" FOREIGN KEY ("athleteId") REFERENCES "public"."athletes"("id") ON DELETE no action ON UPDATE no action;