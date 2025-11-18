import { jsonb, real } from 'drizzle-orm/pg-core';
import { serial } from 'drizzle-orm/pg-core';
import { boolean, integer, pgTable, text, timestamp, varchar } from 'drizzle-orm/pg-core';

export const usersTable = pgTable('users', {
  id: serial().primaryKey(),
  email: varchar({ length: 255 }).notNull().unique(),
  password: varchar({ length: 255 }),
  firstName: varchar({ length: 255 }).notNull(),
  lastName: varchar({ length: 255 }).notNull(),
  role: varchar({ length: 10 }).notNull().$type<'admin' | 'user'>(),
  googleId: varchar({ length: 255 }),
  appleId: varchar({ length: 255 }),
  createdAt: timestamp().notNull().defaultNow(),
});

export const athletesTable = pgTable('athletes', {
  id: serial().primaryKey(),
  userId: integer().references(() => usersTable.id).notNull(),
  age: integer().notNull(),
  gender: varchar({ length: 10 }).notNull().$type<('male' | 'female')>(),
  trainingExperience: varchar({ length: 12 }).notNull().$type<('beginner' | 'intermediate' | 'advanced')>(),
  rpeCalibrationFactor: real().notNull().$default(() => 1.0),
});

export const exercisesTable = pgTable('exercises', {
  id: serial().primaryKey(),
  name: varchar({ length: 255 }).notNull().unique(),
  description: text().notNull(),
  equipment: varchar({ length: 100 }).notNull(),
  primaryMuscles: text().array().notNull(),
  secondaryMuscles: text().array().notNull(),
  injuryRiskLevel: real().notNull(),
  jointStressAreas: varchar({ length: 255 }).array().notNull(),
  movementPattern: varchar({ length: 100 }).notNull(),
  exerciseType: varchar({ length: 50 }).notNull().$type<'compound' | 'isolation'>(),
  complexityScore: real().notNull().$default(() => 1.0),
});

export const workoutPlansTable = pgTable('workout_plans', {
  id: serial().primaryKey(),
  athleteId: integer().references(() => athletesTable.id).notNull(),
  name: varchar({ length: 255 }).notNull(),
  description: text().notNull(),
  trainingType: varchar({ length: 50 }).notNull().$type<('hypertrophy' | 'strength' | 'hybrid')>(),
  // will be determined by the AI engine (send the data to it)
  periodizationModel: varchar({ length: 50 }).notNull().$type<('linear' | 'undulating' | 'block')>(),
  frequency: integer().notNull(),
  durationWeeks: integer().notNull(),
  startDate: timestamp(),
  endDate: timestamp(),
  createdAt: timestamp().notNull().defaultNow(),
  isActive: boolean().notNull(),
});

export const workoutDaysTable = pgTable('workout_days', {
  id: serial().primaryKey(),
  workoutPlanId: integer().references(() => workoutPlansTable.id).notNull(),
  name: varchar({ length: 255 }).notNull(),
  description: text().notNull(),
  dayOfWeek: integer(),
  orderInWeek: integer().notNull(),
  targetMuscleGroups: jsonb().notNull(),
});

export const workoutDayExercisesTable = pgTable('workout_day_exercises', {
  id: serial().primaryKey(),
  workoutDayId: integer().references(() => workoutDaysTable.id).notNull(),
  exerciseId: integer().references(() => exercisesTable.id).notNull(),
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
  warmUpSets: integer().notNull().$default(() => 0), // 0-4 warm-up sets
  autoGenerateWarmups: boolean().notNull().$default(() => true), // Auto-generate warm-up weights/reps
});

export const formQualityTrendsTable = pgTable('form_quality_trends', {
  id: serial().primaryKey(),
  athleteId: integer().references(() => athletesTable.id).notNull(),
  exerciseId: integer().references(() => exercisesTable.id).notNull(),
  date: timestamp().notNull(),
  averageFormScore: real().notNull(), // 1.0=excellent, 0.75=good, 0.5=fair, 0.25=poor
  setsAnalyzed: integer().notNull(),
  degradationRate: real(), // Form drop across sets in session
  highRpePoorFormCount: integer().notNull().$default(() => 0),
});

export const refreshTokensTable = pgTable('refresh_tokens', {
  id: serial().primaryKey(),
  userId: integer().references(() => usersTable.id).notNull(),
  token: text().notNull().unique(),
  expiresAt: timestamp().notNull(),
  createdAt: timestamp().notNull().defaultNow(),
});
