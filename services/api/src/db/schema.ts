import { jsonb, real, index } from 'drizzle-orm/pg-core';
import { serial } from 'drizzle-orm/pg-core';
import {
  boolean,
  integer,
  pgTable,
  text,
  timestamp,
  varchar,
  pgSchema,
} from 'drizzle-orm/pg-core';

// Tables in public schema (default schema, no need to specify explicitly)
export const usersTable = pgTable('users', {
  id: serial().primaryKey(),
  email: varchar({ length: 255 }).notNull().unique(),
  password: varchar({ length: 255 }),
  firstName: varchar({ length: 255 }).notNull(),
  lastName: varchar({ length: 255 }).notNull(),
  role: varchar({ length: 10 }).notNull().$type<'admin' | 'user'>(),
  googleId: varchar({ length: 255 }).unique(),
  appleId: varchar({ length: 255 }).unique(),
  hasInitialPlan: boolean().notNull().default(false),
  createdAt: timestamp().notNull().defaultNow(),
});

export const passwordResetTokensTable = pgTable(
  'password_reset_tokens',
  {
    id: serial().primaryKey(),
    userId: integer()
      .references(() => usersTable.id)
      .notNull()
      .unique(),
    code: text().notNull().unique(),
    verified: boolean().notNull().default(false),
    expiresAt: timestamp().notNull(),
    createdAt: timestamp().notNull().defaultNow(),
  },
  (table) => [
    index('password_reset_tokens_expires_at_idx').on(table.expiresAt),
  ],
);

export const athletesTable = pgTable('athletes', {
  id: serial().primaryKey(),
  userId: integer()
    .references(() => usersTable.id)
    .notNull(),
  age: integer().notNull(),
  gender: varchar({ length: 10 }).notNull().$type<'male' | 'female'>(),
  trainingExperience: varchar({ length: 12 })
    .notNull()
    .$type<'beginner' | 'intermediate' | 'advanced'>(),
  rpeCalibrationFactor: real()
    .notNull()
    .$default(() => 1.0),
  bodyWeightKg: real(),
});

export const muscleGroupsTable = pgTable('muscle_groups', {
  id: serial().primaryKey(),
  name: varchar({ length: 50 }).notNull().unique(),
  displayName: varchar({ length: 100 }).notNull(),
  size: varchar({ length: 20 }).notNull().$type<'small' | 'medium' | 'large'>(),
  baseRecoveryHours: integer().notNull(),
  isCompoundTarget: boolean().notNull().default(false),
  antagonistId: integer().references((): any => muscleGroupsTable.id),
});

export const exercisesTable = pgTable('exercises', {
  id: serial().primaryKey(),
  name: varchar({ length: 255 }).notNull().unique(),
  description: text().notNull(),
  equipment: varchar({ length: 100 }).notNull(),
  injuryRiskLevel: real().notNull(),
  jointStressAreas: varchar({ length: 255 }).array().notNull(),
  movementPattern: varchar({ length: 100 }).notNull(),
  exerciseType: varchar({ length: 50 })
    .notNull()
    .$type<'compound' | 'isolation'>(),
  complexityScore: real()
    .notNull()
    .$default(() => 1.0),
  intensityCategory: varchar({ length: 20 })
    .notNull()
    .$type<'compound_heavy' | 'compound_moderate' | 'isolation'>()
    .$default(() => 'isolation'),
});

export const exerciseMusclesTable = pgTable(
  'exercise_muscles',
  {
    id: serial().primaryKey(),
    exerciseId: integer()
      .references(() => exercisesTable.id, { onDelete: 'cascade' })
      .notNull(),
    muscleGroupId: integer()
      .references(() => muscleGroupsTable.id, { onDelete: 'cascade' })
      .notNull(),
    role: varchar({ length: 20 })
      .notNull()
      .$type<'prime_mover' | 'synergist' | 'stabilizer'>(),
  },
  (table) => [
    index('exercise_muscles_exercise_idx').on(table.exerciseId),
    index('exercise_muscles_muscle_idx').on(table.muscleGroupId),
  ],
);

export const workoutPlansTable = pgTable('workout_plans', {
  id: serial().primaryKey(),
  athleteId: integer()
    .references(() => athletesTable.id)
    .notNull(),
  name: varchar({ length: 255 }).notNull(),
  description: text().notNull(),
  trainingType: varchar({ length: 50 })
    .notNull()
    .$type<'hypertrophy' | 'strength' | 'hybrid'>(),
  // will be determined by the AI engine (send the data to it)
  periodizationModel: varchar({ length: 50 })
    .notNull()
    .$type<'linear' | 'undulating' | 'block'>(),
  focusAreas:
    jsonb().$type<
      Array<'chest' | 'back' | 'shoulders' | 'arms' | 'legs' | 'core'>
    >(),
  frequency: integer().notNull(),
  durationWeeks: integer().notNull(),
  startDate: timestamp(),
  endDate: timestamp(),
  createdAt: timestamp().notNull().defaultNow(),
  isActive: boolean().notNull(),
});

export const workoutDaysTable = pgTable('workout_days', {
  id: serial().primaryKey(),
  workoutPlanId: integer()
    .references(() => workoutPlansTable.id)
    .notNull(),
  name: varchar({ length: 255 }).notNull(),
  dayOfWeek: integer(),
  orderInWeek: integer().notNull(),
  targetMuscleGroups: jsonb().notNull(),
});

export const workoutDayExercisesTable = pgTable('workout_day_exercises', {
  id: serial().primaryKey(),
  workoutDayId: integer()
    .references(() => workoutDaysTable.id)
    .notNull(),
  exerciseId: integer()
    .references(() => exercisesTable.id)
    .notNull(),
  orderInWorkout: integer().notNull(),
  targetSetsMin: integer().notNull(),
  targetSetsMax: integer().notNull(),
  targetRepsMin: integer().notNull(),
  targetRepsMax: integer().notNull(),
  targetRpe: real(),
  targetRir: integer(),
  restPeriodSeconds: integer(),
  tempo: varchar({ length: 20 }),
  notes: text(),
  isPrimary: boolean().notNull(),
  progressionScheme: varchar({ length: 50 }),
  warmUpSets: integer()
    .notNull()
    .$default(() => 0), // 0-4 warm-up sets
  autoGenerateWarmups: boolean()
    .notNull()
    .$default(() => true), // Auto-generate warm-up weights/reps
});

export const refreshTokensTable = pgTable(
  'refresh_tokens',
  {
    id: serial().primaryKey(),
    userId: integer()
      .references(() => usersTable.id)
      .notNull(),
    token: text().notNull().unique(),
    expiresAt: timestamp().notNull(),
    createdAt: timestamp().notNull().defaultNow(),
    usedAt: timestamp(),
  },
  (table) => [
    index('refresh_tokens_user_id_idx').on(table.userId),
    index('refresh_tokens_expires_at_idx').on(table.expiresAt),
  ],
);

// AI Analysis schema tables
export const aiAnalysisSchema = pgSchema('ai_analysis');

export const workoutPrescriptionHistoryTable = aiAnalysisSchema.table(
  'workout_prescription_history',
  {
    id: serial().primaryKey(),
    athleteId: integer()
      .references(() => athletesTable.id, { onDelete: 'cascade' })
      .notNull(),
    workoutDayId: integer().notNull(), // FK to workout_days
    exerciseId: integer()
      .references(() => exercisesTable.id, { onDelete: 'cascade' })
      .notNull(),
    prescribedDate: timestamp().notNull(),

    // Prescribed parameters
    prescribedWeight: real(),
    prescribedSets: integer(),
    prescribedRepsMin: integer(),
    prescribedRepsMax: integer(),
    prescribedRpe: real(),
    prescribedRir: integer(),
    restPeriodSeconds: integer(),

    // Intensity techniques
    setType: varchar({ length: 50 }),
    repStyle: varchar({ length: 50 }),
    setTypeParams: jsonb(),
    repStyleParams: jsonb(),

    // AI context
    volumeMultiplier: real().notNull(),
    intensityMultiplier: real().notNull(),
    adjustmentReason: text(),

    // Context when prescribed
    weekNumber: integer(),
    readinessScore: real(),
    trainingPhase: varchar({ length: 50 }),

    // Metadata
    createdAt: timestamp().notNull().defaultNow(),
  },
  (table) => [
    index('workout_prescription_history_athlete_workout_exercise_date_idx').on(
      table.athleteId,
      table.workoutDayId,
      table.exerciseId,
      table.prescribedDate,
    ),
    index('workout_prescription_history_athlete_exercise_idx').on(
      table.athleteId,
      table.exerciseId,
    ),
  ],
);
