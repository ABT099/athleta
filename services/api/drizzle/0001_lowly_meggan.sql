ALTER TABLE "workout_day_exercises" ADD COLUMN "target_sets_min" integer NOT NULL;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD COLUMN "target_sets_max" integer NOT NULL;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD COLUMN "warm_up_sets" integer NOT NULL;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" ADD COLUMN "auto_generate_warmups" boolean NOT NULL;--> statement-breakpoint
ALTER TABLE "workout_day_exercises" DROP COLUMN "target_sets";--> statement-breakpoint
ALTER TABLE "workout_plans" DROP COLUMN "split_type";