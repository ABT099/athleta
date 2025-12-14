CREATE TABLE "exercise_muscles" (
	"id" serial PRIMARY KEY NOT NULL,
	"exercise_id" integer NOT NULL,
	"muscle_group_id" integer NOT NULL,
	"activation_percent" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE "muscle_groups" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(50) NOT NULL,
	"display_name" varchar(100) NOT NULL,
	"size" varchar(20) NOT NULL,
	"base_recovery_hours" integer NOT NULL,
	"is_compound_target" boolean DEFAULT false NOT NULL,
	"antagonist_id" integer,
	CONSTRAINT "muscle_groups_name_unique" UNIQUE("name")
);
--> statement-breakpoint
ALTER TABLE "exercise_muscles" ADD CONSTRAINT "exercise_muscles_exercise_id_exercises_id_fk" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercises"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "exercise_muscles" ADD CONSTRAINT "exercise_muscles_muscle_group_id_muscle_groups_id_fk" FOREIGN KEY ("muscle_group_id") REFERENCES "public"."muscle_groups"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "muscle_groups" ADD CONSTRAINT "muscle_groups_antagonist_id_muscle_groups_id_fk" FOREIGN KEY ("antagonist_id") REFERENCES "public"."muscle_groups"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "exercise_muscles_exercise_idx" ON "exercise_muscles" USING btree ("exercise_id");--> statement-breakpoint
CREATE INDEX "exercise_muscles_muscle_idx" ON "exercise_muscles" USING btree ("muscle_group_id");--> statement-breakpoint
ALTER TABLE "exercises" DROP COLUMN "primary_muscles";--> statement-breakpoint
ALTER TABLE "exercises" DROP COLUMN "secondary_muscles";--> statement-breakpoint
ALTER TABLE "workout_days" DROP COLUMN "description";