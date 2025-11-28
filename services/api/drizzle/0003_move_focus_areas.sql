ALTER TABLE "workout_plans" ADD COLUMN "focus_areas" jsonb;--> statement-breakpoint
ALTER TABLE "athletes" DROP COLUMN "focus_areas";