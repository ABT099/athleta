import {
  pgTable,
  index,
  check,
  integer,
  varchar,
  timestamp,
  boolean,
  unique,
  serial,
  foreignKey,
  real,
  text,
  jsonb,
  pgEnum,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

export const exerciseTypeEnum = pgEnum('exercise_type_enum', [
  'compound',
  'isolation',
]);
export const intensityCategoryEnum = pgEnum('intensity_category_enum', [
  'compound_heavy',
  'compound_moderate',
  'isolation',
]);
export const periodizationModelEnum = pgEnum('periodization_model_enum', [
  'linear',
  'undulating',
  'block',
]);
export const repStyleEnum = pgEnum('rep_style_enum', [
  'normal',
  'lengthened_partials',
  'tempo_eccentric',
  'tempo_paused',
  'eccentric_overload',
]);
export const setTypeEnum = pgEnum('set_type_enum', [
  'straight',
  'drop_set',
  'rest_pause',
  'myo_reps',
  'cluster_set',
  'superset_antagonist',
  'pre_exhaust',
]);
export const sleepQualityEnum = pgEnum('sleep_quality_enum', [
  'poor',
  'not_bad',
  'good',
  'excellent',
]);
export const trainingPhaseEnum = pgEnum('training_phase_enum', [
  'accumulation',
  'intensification',
  'realization',
]);
export const trainingTypeEnum = pgEnum('training_type_enum', [
  'hypertrophy',
  'strength',
  'hybrid',
]);

export const flywaySchemaHistory = pgTable(
  'flyway_schema_history',
  {
    installedRank: integer('installed_rank').primaryKey().notNull(),
    version: varchar({ length: 50 }),
    description: varchar({ length: 200 }).notNull(),
    type: varchar({ length: 20 }).notNull(),
    script: varchar({ length: 1000 }).notNull(),
    checksum: integer(),
    installedBy: varchar('installed_by', { length: 100 }).notNull(),
    installedOn: timestamp('installed_on', { mode: 'string' })
      .defaultNow()
      .notNull(),
    executionTime: integer('execution_time').notNull(),
    success: boolean().notNull(),
  },
  (table) => [
    index('flyway_schema_history_s_idx').using(
      'btree',
      table.success.asc().nullsLast().op('bool_ops'),
    ),
    check(
      'flyway_schema_history_installed_rank_not_null',
      sql`NOT NULL installed_rank`,
    ),
    check(
      'flyway_schema_history_description_not_null',
      sql`NOT NULL description`,
    ),
    check('flyway_schema_history_type_not_null', sql`NOT NULL type`),
    check('flyway_schema_history_script_not_null', sql`NOT NULL script`),
    check(
      'flyway_schema_history_installed_by_not_null',
      sql`NOT NULL installed_by`,
    ),
    check(
      'flyway_schema_history_installed_on_not_null',
      sql`NOT NULL installed_on`,
    ),
    check(
      'flyway_schema_history_execution_time_not_null',
      sql`NOT NULL execution_time`,
    ),
    check('flyway_schema_history_success_not_null', sql`NOT NULL success`),
  ],
);

export const users = pgTable(
  'users',
  {
    id: serial().primaryKey().notNull(),
    email: varchar({ length: 255 }).notNull(),
    password: varchar({ length: 255 }),
    firstName: varchar('first_name', { length: 255 }).notNull(),
    lastName: varchar('last_name', { length: 255 }).notNull(),
    role: varchar({ length: 10 }).notNull(),
    googleId: varchar('google_id', { length: 255 }),
    appleId: varchar('apple_id', { length: 255 }),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    hasInitialPlan: boolean('has_initial_plan').default(false).notNull(),
  },
  (table) => [
    unique('users_email_unique').on(table.email),
    unique('users_google_id_unique').on(table.googleId),
    unique('users_apple_id_unique').on(table.appleId),
    check('users_id_not_null', sql`NOT NULL id`),
    check('users_email_not_null', sql`NOT NULL email`),
    check('users_first_name_not_null', sql`NOT NULL first_name`),
    check('users_last_name_not_null', sql`NOT NULL last_name`),
    check('users_role_not_null', sql`NOT NULL role`),
    check('users_created_at_not_null', sql`NOT NULL created_at`),
    check('users_has_initial_plan_not_null', sql`NOT NULL has_initial_plan`),
  ],
);

export const athletes = pgTable(
  'athletes',
  {
    id: serial().primaryKey().notNull(),
    userId: integer('user_id').notNull(),
    age: integer().notNull(),
    gender: varchar({ length: 10 }).notNull(),
    trainingExperience: varchar('training_experience', {
      length: 12,
    }).notNull(),
    rpeCalibrationFactor: real('rpe_calibration_factor').notNull().default(1.0),
    bodyWeightKg: real('body_weight_kg'),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: 'athletes_user_id_users_id_fk',
    }),
    check('athletes_id_not_null', sql`NOT NULL id`),
    check('athletes_user_id_not_null', sql`NOT NULL user_id`),
    check('athletes_age_not_null', sql`NOT NULL age`),
    check('athletes_gender_not_null', sql`NOT NULL gender`),
    check(
      'athletes_training_experience_not_null',
      sql`NOT NULL training_experience`,
    ),
    check(
      'athletes_rpe_calibration_factor_not_null',
      sql`NOT NULL rpe_calibration_factor`,
    ),
  ],
);

export const workoutPlans = pgTable(
  'workout_plans',
  {
    id: serial().primaryKey().notNull(),
    athleteId: integer('athlete_id').notNull(),
    name: varchar({ length: 255 }).notNull(),
    description: text().notNull(),
    trainingType: trainingTypeEnum('training_type')
      .default('hypertrophy')
      .notNull(),
    periodizationModel: periodizationModelEnum('periodization_model')
      .default('linear')
      .notNull(),
    frequency: integer().notNull(),
    durationWeeks: integer('duration_weeks').notNull(),
    startDate: timestamp('start_date', { mode: 'string' }),
    endDate: timestamp('end_date', { mode: 'string' }),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    isActive: boolean('is_active').notNull(),
    focusAreas: jsonb('focus_areas'),
  },
  (table) => [
    foreignKey({
      columns: [table.athleteId],
      foreignColumns: [athletes.id],
      name: 'workout_plans_athlete_id_athletes_id_fk',
    }),
    check('workout_plans_id_not_null', sql`NOT NULL id`),
    check('workout_plans_athlete_id_not_null', sql`NOT NULL athlete_id`),
    check('workout_plans_name_not_null', sql`NOT NULL name`),
    check('workout_plans_description_not_null', sql`NOT NULL description`),
    check('workout_plans_training_type_not_null', sql`NOT NULL training_type`),
    check(
      'workout_plans_periodization_model_not_null',
      sql`NOT NULL periodization_model`,
    ),
    check('workout_plans_frequency_not_null', sql`NOT NULL frequency`),
    check(
      'workout_plans_duration_weeks_not_null',
      sql`NOT NULL duration_weeks`,
    ),
    check('workout_plans_created_at_not_null', sql`NOT NULL created_at`),
    check('workout_plans_is_active_not_null', sql`NOT NULL is_active`),
  ],
);

export const workoutDays = pgTable(
  'workout_days',
  {
    id: serial().primaryKey().notNull(),
    workoutPlanId: integer('workout_plan_id').notNull(),
    name: varchar({ length: 255 }).notNull(),
    dayOfWeek: integer('day_of_week'),
    orderInWeek: integer('order_in_week').notNull(),
    targetMuscleGroups: jsonb('target_muscle_groups').notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.workoutPlanId],
      foreignColumns: [workoutPlans.id],
      name: 'workout_days_workout_plan_id_workout_plans_id_fk',
    }),
    check('workout_days_id_not_null', sql`NOT NULL id`),
    check(
      'workout_days_workout_plan_id_not_null',
      sql`NOT NULL workout_plan_id`,
    ),
    check('workout_days_name_not_null', sql`NOT NULL name`),
    check('workout_days_order_in_week_not_null', sql`NOT NULL order_in_week`),
    check(
      'workout_days_target_muscle_groups_not_null',
      sql`NOT NULL target_muscle_groups`,
    ),
  ],
);

export const workoutDayExercises = pgTable(
  'workout_day_exercises',
  {
    id: serial().primaryKey().notNull(),
    workoutDayId: integer('workout_day_id').notNull(),
    exerciseId: integer('exercise_id').notNull(),
    orderInWorkout: integer('order_in_workout').notNull(),
    targetSetsMin: integer('target_sets_min').notNull(),
    targetSetsMax: integer('target_sets_max').notNull(),
    targetRepsMin: integer('target_reps_min').notNull(),
    targetRepsMax: integer('target_reps_max').notNull(),
    targetRpe: real('target_rpe'),
    targetRir: integer('target_rir'),
    restPeriodSeconds: integer('rest_period_seconds'),
    tempo: varchar({ length: 20 }),
    notes: text(),
    isPrimary: boolean('is_primary').notNull(),
    progressionScheme: varchar('progression_scheme', { length: 50 }),
    warmUpSets: integer('warm_up_sets').notNull(),
    autoGenerateWarmups: boolean('auto_generate_warmups').notNull(),
    setType: setTypeEnum('set_type').default('straight').notNull(),
    repStyle: repStyleEnum('rep_style').default('normal').notNull(),
    setTypeParams: jsonb('set_type_params'),
    repStyleParams: jsonb('rep_style_params'),
  },
  (table) => [
    foreignKey({
      columns: [table.workoutDayId],
      foreignColumns: [workoutDays.id],
      name: 'workout_day_exercises_workout_day_id_workout_days_id_fk',
    }),
    foreignKey({
      columns: [table.exerciseId],
      foreignColumns: [exercises.id],
      name: 'workout_day_exercises_exercise_id_exercises_id_fk',
    }),
    check('workout_day_exercises_id_not_null', sql`NOT NULL id`),
    check(
      'workout_day_exercises_workout_day_id_not_null',
      sql`NOT NULL workout_day_id`,
    ),
    check(
      'workout_day_exercises_exercise_id_not_null',
      sql`NOT NULL exercise_id`,
    ),
    check(
      'workout_day_exercises_order_in_workout_not_null',
      sql`NOT NULL order_in_workout`,
    ),
    check(
      'workout_day_exercises_target_sets_min_not_null',
      sql`NOT NULL target_sets_min`,
    ),
    check(
      'workout_day_exercises_target_sets_max_not_null',
      sql`NOT NULL target_sets_max`,
    ),
    check(
      'workout_day_exercises_target_reps_min_not_null',
      sql`NOT NULL target_reps_min`,
    ),
    check(
      'workout_day_exercises_target_reps_max_not_null',
      sql`NOT NULL target_reps_max`,
    ),
    check(
      'workout_day_exercises_is_primary_not_null',
      sql`NOT NULL is_primary`,
    ),
    check(
      'workout_day_exercises_warm_up_sets_not_null',
      sql`NOT NULL warm_up_sets`,
    ),
    check(
      'workout_day_exercises_auto_generate_warmups_not_null',
      sql`NOT NULL auto_generate_warmups`,
    ),
    check('workout_day_exercises_set_type_not_null', sql`NOT NULL set_type`),
    check('workout_day_exercises_rep_style_not_null', sql`NOT NULL rep_style`),
  ],
);

export const exercises = pgTable(
  'exercises',
  {
    id: serial().primaryKey().notNull(),
    name: varchar({ length: 255 }).notNull(),
    equipment: varchar({ length: 100 }).notNull(),
    injuryRiskLevel: real('injury_risk_level').notNull(),
    jointStressAreas: varchar('joint_stress_areas', { length: 255 })
      .array()
      .notNull(),
    movementPattern: varchar('movement_pattern', { length: 100 }).notNull(),
    exerciseType: exerciseTypeEnum('exercise_type').notNull(),
    complexityScore: real('complexity_score').default(1).notNull(),
    intensityCategory: intensityCategoryEnum('intensity_category')
      .default('isolation')
      .notNull(),
  },
  (table) => [
    unique('exercises_name_unique').on(table.name),
    check('exercises_id_not_null', sql`NOT NULL id`),
    check('exercises_name_not_null', sql`NOT NULL name`),
    check('exercises_equipment_not_null', sql`NOT NULL equipment`),
    check(
      'exercises_injury_risk_level_not_null',
      sql`NOT NULL injury_risk_level`,
    ),
    check(
      'exercises_joint_stress_areas_not_null',
      sql`NOT NULL joint_stress_areas`,
    ),
    check(
      'exercises_movement_pattern_not_null',
      sql`NOT NULL movement_pattern`,
    ),
    check('exercises_exercise_type_not_null', sql`NOT NULL exercise_type`),
    check(
      'exercises_complexity_score_not_null',
      sql`NOT NULL complexity_score`,
    ),
    check(
      'exercises_intensity_category_not_null',
      sql`NOT NULL intensity_category`,
    ),
  ],
);

export const refreshTokens = pgTable(
  'refresh_tokens',
  {
    id: serial().primaryKey().notNull(),
    userId: integer('user_id').notNull(),
    token: text().notNull(),
    expiresAt: timestamp('expires_at', { mode: 'string' }).notNull(),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    usedAt: timestamp('used_at', { mode: 'string' }),
  },
  (table) => [
    index('refresh_tokens_expires_at_idx').using(
      'btree',
      table.expiresAt.asc().nullsLast().op('timestamp_ops'),
    ),
    index('refresh_tokens_user_id_idx').using(
      'btree',
      table.userId.asc().nullsLast().op('int4_ops'),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: 'refresh_tokens_user_id_users_id_fk',
    }),
    unique('refresh_tokens_token_unique').on(table.token),
    check('refresh_tokens_id_not_null', sql`NOT NULL id`),
    check('refresh_tokens_user_id_not_null', sql`NOT NULL user_id`),
    check('refresh_tokens_token_not_null', sql`NOT NULL token`),
    check('refresh_tokens_expires_at_not_null', sql`NOT NULL expires_at`),
    check('refresh_tokens_created_at_not_null', sql`NOT NULL created_at`),
  ],
);

export const passwordResetTokens = pgTable(
  'password_reset_tokens',
  {
    id: serial().primaryKey().notNull(),
    userId: integer('user_id').notNull(),
    code: text().notNull(),
    verified: boolean().default(false).notNull(),
    expiresAt: timestamp('expires_at', { mode: 'string' }).notNull(),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index('password_reset_tokens_expires_at_idx').using(
      'btree',
      table.expiresAt.asc().nullsLast().op('timestamp_ops'),
    ),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [users.id],
      name: 'password_reset_tokens_user_id_users_id_fk',
    }),
    unique('password_reset_tokens_userId_unique').on(table.userId),
    unique('password_reset_tokens_code_unique').on(table.code),
    check('password_reset_tokens_id_not_null', sql`NOT NULL id`),
    check('password_reset_tokens_user_id_not_null', sql`NOT NULL user_id`),
    check('password_reset_tokens_code_not_null', sql`NOT NULL code`),
    check('password_reset_tokens_verified_not_null', sql`NOT NULL verified`),
    check(
      'password_reset_tokens_expires_at_not_null',
      sql`NOT NULL expires_at`,
    ),
    check(
      'password_reset_tokens_created_at_not_null',
      sql`NOT NULL created_at`,
    ),
  ],
);

export const muscleGroups = pgTable(
  'muscle_groups',
  {
    id: serial().primaryKey().notNull(),
    name: varchar({ length: 50 }).notNull(),
    displayName: varchar('display_name', { length: 100 }).notNull(),
    size: varchar({ length: 20 }).notNull(),
    baseRecoveryHours: integer('base_recovery_hours').notNull(),
    isCompoundTarget: boolean('is_compound_target').default(false).notNull(),
    antagonistId: integer('antagonist_id'),
  },
  (table) => [
    foreignKey({
      columns: [table.antagonistId],
      foreignColumns: [table.id],
      name: 'muscle_groups_antagonist_id_muscle_groups_id_fk',
    }),
    unique('muscle_groups_name_unique').on(table.name),
    check('muscle_groups_id_not_null', sql`NOT NULL id`),
    check('muscle_groups_name_not_null', sql`NOT NULL name`),
    check('muscle_groups_display_name_not_null', sql`NOT NULL display_name`),
    check('muscle_groups_size_not_null', sql`NOT NULL size`),
    check(
      'muscle_groups_base_recovery_hours_not_null',
      sql`NOT NULL base_recovery_hours`,
    ),
    check(
      'muscle_groups_is_compound_target_not_null',
      sql`NOT NULL is_compound_target`,
    ),
  ],
);

export const exerciseMuscles = pgTable(
  'exercise_muscles',
  {
    id: serial().primaryKey().notNull(),
    exerciseId: integer('exercise_id').notNull(),
    muscleGroupId: integer('muscle_group_id').notNull(),
    role: varchar({ length: 20 }).notNull(),
  },
  (table) => [
    index('exercise_muscles_exercise_idx').using(
      'btree',
      table.exerciseId.asc().nullsLast().op('int4_ops'),
    ),
    index('exercise_muscles_muscle_idx').using(
      'btree',
      table.muscleGroupId.asc().nullsLast().op('int4_ops'),
    ),
    foreignKey({
      columns: [table.exerciseId],
      foreignColumns: [exercises.id],
      name: 'exercise_muscles_exercise_id_exercises_id_fk',
    }).onDelete('cascade'),
    foreignKey({
      columns: [table.muscleGroupId],
      foreignColumns: [muscleGroups.id],
      name: 'exercise_muscles_muscle_group_id_muscle_groups_id_fk',
    }).onDelete('cascade'),
    check('exercise_muscles_id_not_null', sql`NOT NULL id`),
    check('exercise_muscles_exercise_id_not_null', sql`NOT NULL exercise_id`),
    check(
      'exercise_muscles_muscle_group_id_not_null',
      sql`NOT NULL muscle_group_id`,
    ),
    check('exercise_muscles_role_not_null', sql`NOT NULL role`),
  ],
);
