import { relations } from 'drizzle-orm/relations';
import {
  users,
  athletes,
  workoutPlans,
  workoutDays,
  workoutDayExercises,
  exercises,
  refreshTokens,
  passwordResetTokens,
  muscleGroups,
  exerciseMuscles,
} from './schema';

export const athletesRelations = relations(athletes, ({ one, many }) => ({
  user: one(users, {
    fields: [athletes.userId],
    references: [users.id],
  }),
  workoutPlans: many(workoutPlans),
}));

export const usersRelations = relations(users, ({ many }) => ({
  athletes: many(athletes),
  refreshTokens: many(refreshTokens),
  passwordResetTokens: many(passwordResetTokens),
}));

export const workoutPlansRelations = relations(
  workoutPlans,
  ({ one, many }) => ({
    athlete: one(athletes, {
      fields: [workoutPlans.athleteId],
      references: [athletes.id],
    }),
    workoutDays: many(workoutDays),
  }),
);

export const workoutDaysRelations = relations(workoutDays, ({ one, many }) => ({
  workoutPlan: one(workoutPlans, {
    fields: [workoutDays.workoutPlanId],
    references: [workoutPlans.id],
  }),
  workoutDayExercises: many(workoutDayExercises),
}));

export const workoutDayExercisesRelations = relations(
  workoutDayExercises,
  ({ one }) => ({
    workoutDay: one(workoutDays, {
      fields: [workoutDayExercises.workoutDayId],
      references: [workoutDays.id],
    }),
    exercise: one(exercises, {
      fields: [workoutDayExercises.exerciseId],
      references: [exercises.id],
    }),
  }),
);

export const exercisesRelations = relations(exercises, ({ many }) => ({
  workoutDayExercises: many(workoutDayExercises),
  exerciseMuscles: many(exerciseMuscles),
}));

export const refreshTokensRelations = relations(refreshTokens, ({ one }) => ({
  user: one(users, {
    fields: [refreshTokens.userId],
    references: [users.id],
  }),
}));

export const passwordResetTokensRelations = relations(
  passwordResetTokens,
  ({ one }) => ({
    user: one(users, {
      fields: [passwordResetTokens.userId],
      references: [users.id],
    }),
  }),
);

export const muscleGroupsRelations = relations(
  muscleGroups,
  ({ one, many }) => ({
    muscleGroup: one(muscleGroups, {
      fields: [muscleGroups.antagonistId],
      references: [muscleGroups.id],
      relationName: 'muscleGroups_antagonistId_muscleGroups_id',
    }),
    muscleGroups: many(muscleGroups, {
      relationName: 'muscleGroups_antagonistId_muscleGroups_id',
    }),
    exerciseMuscles: many(exerciseMuscles),
  }),
);

export const exerciseMusclesRelations = relations(
  exerciseMuscles,
  ({ one }) => ({
    exercise: one(exercises, {
      fields: [exerciseMuscles.exerciseId],
      references: [exercises.id],
    }),
    muscleGroup: one(muscleGroups, {
      fields: [exerciseMuscles.muscleGroupId],
      references: [muscleGroups.id],
    }),
  }),
);
