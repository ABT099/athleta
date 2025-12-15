-- Add muscle role enum type
CREATE TYPE muscle_role_enum AS ENUM ('prime_mover', 'synergist', 'stabilizer');

-- Add role column to exercise_muscles table
ALTER TABLE exercise_muscles 
  ADD COLUMN role muscle_role_enum;

-- Migrate existing data based on activation_percent ranges
-- 70-100% = prime_mover
-- 40-69% = synergist
-- 1-39% = stabilizer
UPDATE exercise_muscles SET role = 
  CASE 
    WHEN activation_percent >= 70 THEN 'prime_mover'::muscle_role_enum
    WHEN activation_percent >= 40 THEN 'synergist'::muscle_role_enum
    ELSE 'stabilizer'::muscle_role_enum
  END;

-- Make role column NOT NULL after migration
ALTER TABLE exercise_muscles 
  ALTER COLUMN role SET NOT NULL;

-- Drop the old activation_percent column
ALTER TABLE exercise_muscles 
  DROP COLUMN activation_percent;

