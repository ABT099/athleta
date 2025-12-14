-- Seed the 20 muscle groups
-- First pass: Insert muscles without antagonist relationships
INSERT INTO muscle_groups (name, display_name, size, base_recovery_hours, is_compound_target) VALUES
-- Chest (3)
('upper_chest', 'Upper Chest', 'large', 72, true),
('mid_chest', 'Mid Chest', 'large', 72, true),
('lower_chest', 'Lower Chest', 'large', 72, true),
-- Back (4)
('lats', 'Lats', 'large', 72, true),
('upper_traps', 'Upper Traps', 'medium', 60, false),
('mid_back', 'Mid Back', 'medium', 60, true),
('lower_traps', 'Lower Traps', 'medium', 60, false),
-- Shoulders (3)
('anterior_delt', 'Front Delts', 'medium', 60, true),
('lateral_delt', 'Side Delts', 'small', 48, false),
('posterior_delt', 'Rear Delts', 'small', 48, false),
-- Arms (3)
('biceps', 'Biceps', 'small', 48, false),
('triceps', 'Triceps', 'small', 48, false),
('forearms', 'Forearms', 'small', 48, false),
-- Legs (5)
('quadriceps', 'Quadriceps', 'large', 72, true),
('hamstrings', 'Hamstrings', 'large', 72, true),
('glutes', 'Glutes', 'large', 72, true),
('hip_flexors', 'Hip Flexors', 'medium', 60, false),
('calves', 'Calves', 'small', 48, false),
-- Core (2)
('abs', 'Abs', 'medium', 48, false),
('erector_spinae', 'Lower Back', 'medium', 60, true);
--> statement-breakpoint
-- Second pass: Update antagonist relationships
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_back') WHERE name = 'upper_chest';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_back') WHERE name = 'mid_chest';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'lats') WHERE name = 'lower_chest';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'lower_chest') WHERE name = 'lats';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'mid_chest') WHERE name = 'mid_back';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'posterior_delt') WHERE name = 'anterior_delt';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'anterior_delt') WHERE name = 'posterior_delt';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'triceps') WHERE name = 'biceps';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'biceps') WHERE name = 'triceps';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'hamstrings') WHERE name = 'quadriceps';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'quadriceps') WHERE name = 'hamstrings';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'hip_flexors') WHERE name = 'glutes';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'glutes') WHERE name = 'hip_flexors';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'erector_spinae') WHERE name = 'abs';
--> statement-breakpoint
UPDATE muscle_groups SET antagonist_id = (SELECT id FROM muscle_groups WHERE name = 'abs') WHERE name = 'erector_spinae';


