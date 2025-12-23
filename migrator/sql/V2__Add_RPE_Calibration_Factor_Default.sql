-- Add default value to rpe_calibration_factor column
ALTER TABLE "athletes" 
ALTER COLUMN "rpe_calibration_factor" SET DEFAULT 1.0;

-- Update any existing NULL values (shouldn't be any, but just in case)
UPDATE "athletes" 
SET "rpe_calibration_factor" = 1.0 
WHERE "rpe_calibration_factor" IS NULL;

