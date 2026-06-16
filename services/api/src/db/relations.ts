import { relations } from 'drizzle-orm/relations';
import {
  users,
  athletes,
  workoutPlans,
  workoutDays,
  workoutDayExercises,
  refreshTokens,
  passwordResetTokens,
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

// workout_day_exercises.exercise_id is a soft reference to an exercise owned
// by the exercise-service; there is no local exercises relation.
export const workoutDayExercisesRelations = relations(
  workoutDayExercises,
  ({ one }) => ({
    workoutDay: one(workoutDays, {
      fields: [workoutDayExercises.workoutDayId],
      references: [workoutDays.id],
    }),
  }),
);

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
