import {
  pgTable,
  index,
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
  ],
);

export const workoutPlans = pgTable(
  'workout_plans',
  {
    id: serial().primaryKey().notNull(),
    athleteId: integer('athlete_id').notNull(),
    name: varchar({ length: 255 }).notNull(),
    description: text(),
    trainingType: trainingTypeEnum('training_type')
      .default('hypertrophy')
      .notNull(),
    periodizationModel: periodizationModelEnum('periodization_model')
      .default('linear')
      .notNull(),
    frequency: integer().notNull(),
    durationWeeks: integer('duration_weeks').notNull(),
    startDate: timestamp('start_date', { mode: 'string' })
      .defaultNow()
      .notNull(),
    endDate: timestamp('end_date', { mode: 'string' }),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    isActive: boolean('is_active').notNull().default(true),
    focusAreas: jsonb('focus_areas'),
  },
  (table) => [
    foreignKey({
      columns: [table.athleteId],
      foreignColumns: [athletes.id],
      name: 'workout_plans_athlete_id_athletes_id_fk',
    }),
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
    muscleImageUrl: varchar('muscle_image_url', { length: 512 }),
  },
  (table) => [
    foreignKey({
      columns: [table.workoutPlanId],
      foreignColumns: [workoutPlans.id],
      name: 'workout_days_workout_plan_id_workout_plans_id_fk',
    }),
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
    notes: text(),
    isPrimary: boolean('is_primary').notNull(),
    progressionScheme: varchar('progression_scheme', { length: 50 }),
    warmUpSets: integer('warm_up_sets').notNull(),
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
    // exercise_id is a soft reference to an exercise owned by the
    // exercise-service (Neo4j); there is no local exercises table.
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
  ],
);

// ---------------------------------------------------------------------------
// Workout execution + PRs — api-owned (moved here from the shared ai_analysis
// schema). auto-regulation pushes/reads these over the wire; exercise_id is a
// soft reference to exercise-service (no local exercises table).
// ---------------------------------------------------------------------------

export const workoutSessions = pgTable(
  'workout_sessions',
  {
    id: serial().primaryKey().notNull(),
    athleteId: integer('athlete_id').notNull(),
    workoutDayId: integer('workout_day_id').notNull(),
    sessionDate: timestamp('session_date', { mode: 'string' }).notNull(),
    durationMinutes: integer('duration_minutes'),
    overallRpe: real('overall_rpe'),
    overallFeeling: varchar('overall_feeling', { length: 50 }),
    notes: text(),
    totalVolume: real('total_volume'),
    estimatedFatigue: real('estimated_fatigue'),
  },
  (table) => [
    foreignKey({
      columns: [table.athleteId],
      foreignColumns: [athletes.id],
      name: 'workout_sessions_athlete_id_athletes_id_fk',
    }),
    foreignKey({
      columns: [table.workoutDayId],
      foreignColumns: [workoutDays.id],
      name: 'workout_sessions_workout_day_id_workout_days_id_fk',
    }),
    index('workout_sessions_athlete_id_idx').using(
      'btree',
      table.athleteId.asc().nullsLast().op('int4_ops'),
    ),
  ],
);

export const exerciseSets = pgTable(
  'exercise_sets',
  {
    id: serial().primaryKey().notNull(),
    workoutSessionId: integer('workout_session_id').notNull(),
    exerciseId: integer('exercise_id').notNull(),
    setNumber: integer('set_number').notNull(),
    weight: real().notNull(),
    reps: integer().notNull(),
    rpe: real(),
    rir: integer(),
    formQuality: varchar('form_quality', { length: 50 }),
    notes: text(),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    setTypeUsed: setTypeEnum('set_type_used'),
    repStyleUsed: repStyleEnum('rep_style_used'),
    techniqueDetails: jsonb('technique_details'),
  },
  (table) => [
    foreignKey({
      columns: [table.workoutSessionId],
      foreignColumns: [workoutSessions.id],
      name: 'exercise_sets_workout_session_id_workout_sessions_id_fk',
    }),
    // exercise_id softly references an exercise-service (Neo4j) exercise.
    index('exercise_sets_workout_session_id_idx').using(
      'btree',
      table.workoutSessionId.asc().nullsLast().op('int4_ops'),
    ),
  ],
);

export const recoveryMetrics = pgTable(
  'recovery_metrics',
  {
    id: serial().primaryKey().notNull(),
    athleteId: integer('athlete_id').notNull(),
    date: timestamp({ mode: 'string' }).notNull(),
    sleepQuality: sleepQualityEnum('sleep_quality').notNull(),
    sleepHours: real('sleep_hours'),
    overallSoreness: integer('overall_soreness'),
    muscleSoreness: text('muscle_soreness'),
    stressLevel: integer('stress_level'),
    energyLevel: integer('energy_level'),
    readinessScore: real('readiness_score'),
    nutritionAdherence: varchar('nutrition_adherence', { length: 50 }),
    hydrationLevel: varchar('hydration_level', { length: 50 }),
    notes: text(),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.athleteId],
      foreignColumns: [athletes.id],
      name: 'recovery_metrics_athlete_id_athletes_id_fk',
    }),
    index('recovery_metrics_athlete_id_idx').using(
      'btree',
      table.athleteId.asc().nullsLast().op('int4_ops'),
    ),
  ],
);

export const exercisePersonalRecords = pgTable(
  'exercise_personal_records',
  {
    id: serial().primaryKey().notNull(),
    athleteId: integer('athlete_id').notNull(),
    exerciseId: integer('exercise_id').notNull(),
    oneRepMax: real('one_rep_max'),
    oneRmDate: timestamp('one_rm_date', { mode: 'string' }),
    threeRepMax: real('three_rep_max'),
    threeRmDate: timestamp('three_rm_date', { mode: 'string' }),
    fiveRepMax: real('five_rep_max'),
    fiveRmDate: timestamp('five_rm_date', { mode: 'string' }),
    eightRepMax: real('eight_rep_max'),
    eightRmDate: timestamp('eight_rm_date', { mode: 'string' }),
    tenRepMax: real('ten_rep_max'),
    tenRmDate: timestamp('ten_rm_date', { mode: 'string' }),
    twelveRepMax: real('twelve_rep_max'),
    twelveRmDate: timestamp('twelve_rm_date', { mode: 'string' }),
    maxVolumeSession: real('max_volume_session'),
    maxVolumeDate: timestamp('max_volume_date', { mode: 'string' }),
    maxTotalReps: integer('max_total_reps'),
    maxRepsDate: timestamp('max_reps_date', { mode: 'string' }),
    totalPrCount: integer('total_pr_count').default(0).notNull(),
    lastPrDate: timestamp('last_pr_date', { mode: 'string' }),
    createdAt: timestamp('created_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp('updated_at', { mode: 'string' })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.athleteId],
      foreignColumns: [athletes.id],
      name: 'exercise_personal_records_athlete_id_athletes_id_fk',
    }),
    // exercise_id softly references an exercise-service (Neo4j) exercise.
    unique('uq_athlete_exercise_pr').on(table.athleteId, table.exerciseId),
    index('exercise_personal_records_athlete_id_idx').using(
      'btree',
      table.athleteId.asc().nullsLast().op('int4_ops'),
    ),
  ],
);
