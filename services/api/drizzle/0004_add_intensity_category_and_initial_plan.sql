ALTER TABLE "exercises" ADD COLUMN "intensity_category" varchar(20) NOT NULL;--> statement-breakpoint
ALTER TABLE "users" ADD COLUMN "has_initial_plan" boolean DEFAULT false NOT NULL;