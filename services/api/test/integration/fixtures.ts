/** Builders for request payloads shared across integration suites. */

export interface PlanExerciseOverride {
  name: string;
  orderInWorkout: number;
  targetSetsMin?: number;
  targetSetsMax?: number;
  targetRepsMin?: number;
  targetRepsMax?: number;
}

export function planPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    name: 'Test Plan',
    description: 'A test plan',
    trainingType: 'hypertrophy',
    periodizationModel: 'linear',
    frequency: 3,
    durationWeeks: 8,
    focusAreas: ['chest'],
    workoutDays: [
      {
        name: 'Push',
        dayOfWeek: 0,
        orderInWeek: 1,
        exercises: [
          {
            name: 'Bench Press',
            targetSetsMin: 3,
            targetSetsMax: 4,
            targetRepsMin: 8,
            targetRepsMax: 12,
            orderInWorkout: 1,
          },
          {
            name: 'Overhead Press',
            targetSetsMin: 3,
            targetRepsMin: 8,
            orderInWorkout: 2,
          },
        ],
      },
    ],
    ...overrides,
  };
}
