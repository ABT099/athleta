export type CreateWorkoutExerciseInput = {
  name: string;
  targetSetsMin: number;
  targetSetsMax?: number;
  targetRepsMin: number;
  targetRepsMax?: number;
  orderInWorkout: number;
  notes?: string;
};

export type CreateWorkoutDayInput = {
  name: string;
  dayOfWeek: number;
  orderInWeek: number;
  exercises: CreateWorkoutExerciseInput[];
};
