import { Inject, Injectable } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import { PeriodizationModel, TrainingType } from 'src/constants';
import { workoutDays, workoutPlans } from 'src/db/schema';
import { eq } from 'drizzle-orm';
import { ExerciseService } from '../exercise/exercise.service';
import { MuscleImageIntegration } from 'src/integrations/muscle-image.integration';

type WorkoutDay = {
  name: string;
  dayOfWeek: number;
  orderInWeek: number;
  exercises: WorkoutExercise[];
};

type WorkoutExercise = {
  name: string;
  targetSetsMin: number;
  targetSetsMax?: number;
  targetRepsMin: number;
  targetRepsMax?: number;
  orderInWorkout: number;
  notes?: string;
};

@Injectable()
export class PlansService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly exerciseService: ExerciseService,
    private readonly muscleImageIntegration: MuscleImageIntegration,
  ) {}

  async createPlan(createPlanDto: {
    athleteId: number;
    name: string;
    description: string;
    trainingType: TrainingType;
    periodizationModel: PeriodizationModel;
    frequency: number;
    durationWeeks: number;
    focusAreas?: string[];
    workoutDays: WorkoutDay[];
  }) {
    const allExerciseNames = createPlanDto.workoutDays.flatMap((workoutDay) =>
      workoutDay.exercises.map((exercise) => exercise.name),
    );

    const exercisesWithMuscles =
      await this.exerciseService.batchUpsertExercises(allExerciseNames);

    const exerciseMuscleMap = new Map<
      string,
      Array<{ name: string; role: string }>
    >();
    let index = 0;
    for (const name of allExerciseNames) {
      exerciseMuscleMap.set(
        name.toLowerCase(),
        exercisesWithMuscles[index].muscles,
      );
      index++;
    }

    await this.db.transaction(async (tx) => {
      await tx
        .update(workoutPlans)
        .set({
          isActive: false,
        })
        .where(eq(workoutPlans.athleteId, createPlanDto.athleteId));

      const workoutPlanId: number = await tx
        .insert(workoutPlans)
        .values({
          athleteId: createPlanDto.athleteId,
          name: createPlanDto.name,
          description: createPlanDto.description,
          trainingType: createPlanDto.trainingType,
          periodizationModel: createPlanDto.periodizationModel,
          frequency: createPlanDto.frequency,
          durationWeeks: createPlanDto.durationWeeks,
          endDate: new Date(
            new Date().getTime() +
              createPlanDto.durationWeeks * 7 * 24 * 60 * 60 * 1000,
          ).toISOString(),
          focusAreas: createPlanDto.focusAreas,
        })
        .returning({ id: workoutPlans.id })
        .then(([workoutPlan]) => workoutPlan.id);

      for (const workoutDay of createPlanDto.workoutDays) {
        const musclesWithRoles: Array<{ name: string; role: string }> = [];

        for (const exercise of workoutDay.exercises) {
          const muscles = exerciseMuscleMap.get(exercise.name.toLowerCase());
          if (muscles) {
            for (const muscle of muscles) {
              musclesWithRoles.push(muscle);
            }
          }
        }

        const [insertedWorkoutDay] = await tx
          .insert(workoutDays)
          .values({
            workoutPlanId: workoutPlanId,
            name: workoutDay.name,
            dayOfWeek: workoutDay.dayOfWeek,
            orderInWeek: workoutDay.orderInWeek,
            muscleImageUrl: null, // Will be updated after image generation
          })
          .returning({ id: workoutDays.id });

        // Generate muscle image (outside transaction to avoid blocking)
        // We'll update the URL in a separate query
        try {
          const muscleImageUrl =
            await this.muscleImageIntegration.generateAndSaveImage(
              insertedWorkoutDay.id,
              musclesWithRoles,
            );

          // Update workout day with image URL
          await tx
            .update(workoutDays)
            .set({ muscleImageUrl })
            .where(eq(workoutDays.id, insertedWorkoutDay.id));
        } catch (error) {
          // Log error but don't block plan creation if image generation fails
          console.error(
            `Failed to generate muscle image for workout day ${insertedWorkoutDay.id}:`,
            error,
          );
        }
      }
    });
  }
}
