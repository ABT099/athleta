ALTER TABLE "exercise_muscles" ADD COLUMN "role" varchar(20) NOT NULL;--> statement-breakpoint
ALTER TABLE "exercise_muscles" DROP COLUMN "activation_percent";--> statement-breakpoint
ALTER TABLE "exercises" DROP COLUMN "description";