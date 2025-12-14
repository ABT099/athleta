import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import {
  exercisesTable,
  muscleGroupsTable,
  exerciseMusclesTable,
} from '../../db/schema';
import { eq, ne, lte, inArray, and } from 'drizzle-orm';
import { MuscleSimilarityUtil } from './utils/muscle-similarity.util';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import {
  SubstitutionResultDto,
  ExerciseDto,
  MatchDetailsDto,
  MuscleActivationDto,
} from './dto/substitution-result.dto';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';

type ExerciseEntity = typeof exercisesTable.$inferSelect;

interface ExerciseWithMuscles extends ExerciseEntity {
  muscles: MuscleActivationDto[];
}

@Injectable()
export class ExerciseService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly aiEngineIntegration: AIEngineIntegration,
  ) {}

  async findSubstitutions(
    originalExerciseId: number,
    filters?: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    // Get original exercise with muscles
    const originalExercise =
      await this.getExerciseWithMuscles(originalExerciseId);

    if (!originalExercise) {
      throw new NotFoundException(
        `Exercise with ID ${originalExerciseId} not found`,
      );
    }

    // Build query conditions
    const conditions = [ne(exercisesTable.id, originalExerciseId)];

    if (filters?.availableEquipment && filters.availableEquipment.length > 0) {
      conditions.push(
        inArray(exercisesTable.equipment, filters.availableEquipment),
      );
    }

    if (filters?.maxComplexity !== undefined) {
      conditions.push(
        lte(exercisesTable.complexityScore, filters.maxComplexity),
      );
    }

    if (filters?.maxInjuryRisk !== undefined) {
      conditions.push(
        lte(exercisesTable.injuryRiskLevel, filters.maxInjuryRisk),
      );
    }

    if (filters?.excludeIds && filters.excludeIds.length > 0) {
      filters.excludeIds.forEach((id) => {
        conditions.push(ne(exercisesTable.id, id));
      });
    }

    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;
    const candidateExercises = await this.db.query.exercisesTable.findMany({
      where: whereClause,
    });

    // Filter out exercises with excluded joint stress (if specified)
    let filteredExercises = candidateExercises;
    if (filters?.excludeJointStress && filters.excludeJointStress.length > 0) {
      filteredExercises = candidateExercises.filter((exercise) => {
        const hasExcludedJoint = filters.excludeJointStress!.some((joint) =>
          exercise.jointStressAreas?.includes(joint),
        );
        return !hasExcludedJoint;
      });
    }

    // Get muscles for all candidate exercises
    const candidateIds = filteredExercises.map((e) => e.id);
    const exercisesWithMuscles =
      await this.getMultipleExercisesWithMuscles(candidateIds);

    // Calculate similarity scores
    const scoredExercises = exercisesWithMuscles
      .map((exercise) => {
        const matchDetails = this.calculateMatchDetails(
          originalExercise,
          exercise,
        );
        const similarityScore = this.calculateSimilarityScore(matchDetails);

        return {
          exercise: this.mapToExerciseDto(exercise),
          similarityScore,
          reason: MuscleSimilarityUtil.generateSubstitutionReason(matchDetails),
          matchDetails,
        };
      })
      .sort((a, b) => b.similarityScore - a.similarityScore)
      .slice(0, filters?.limit || 5);

    return scoredExercises;
  }

  async findPersonalizedSubstitutions(
    originalExerciseId: number,
    athleteId: number,
    filters?: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    // Get AI engine insights for athlete
    const [jointProfile, problematicExercises] = await Promise.all([
      this.aiEngineIntegration.getJointStressProfile(athleteId),
      this.aiEngineIntegration.getProblematicExercises(athleteId),
    ]);

    // Merge AI insights into filters
    const enhancedFilters: SubstitutionFiltersDto = {
      ...filters,
      excludeJointStress: [
        ...(filters?.excludeJointStress || []),
        ...jointProfile.avoidJoints,
      ],
      excludeIds: [
        ...(filters?.excludeIds || []),
        ...problematicExercises.map((pe) => pe.exerciseId),
      ],
    };

    return this.findSubstitutions(originalExerciseId, enhancedFilters);
  }

  /**
   * Get a single exercise with its muscle activations
   */
  private async getExerciseWithMuscles(
    exerciseId: number,
  ): Promise<ExerciseWithMuscles | null> {
    const exercise = await this.db.query.exercisesTable.findFirst({
      where: eq(exercisesTable.id, exerciseId),
    });

    if (!exercise) {
      return null;
    }

    // Get muscle activations for this exercise
    const muscles = await this.db
      .select({
        id: muscleGroupsTable.id,
        name: muscleGroupsTable.name,
        displayName: muscleGroupsTable.displayName,
        activationPercent: exerciseMusclesTable.activationPercent,
      })
      .from(exerciseMusclesTable)
      .innerJoin(
        muscleGroupsTable,
        eq(exerciseMusclesTable.muscleGroupId, muscleGroupsTable.id),
      )
      .where(eq(exerciseMusclesTable.exerciseId, exerciseId))
      .orderBy(exerciseMusclesTable.activationPercent);

    return {
      ...exercise,
      muscles,
    };
  }

  /**
   * Get multiple exercises with their muscle activations
   */
  private async getMultipleExercisesWithMuscles(
    exerciseIds: number[],
  ): Promise<ExerciseWithMuscles[]> {
    if (exerciseIds.length === 0) {
      return [];
    }

    // Get all exercises
    const exercises = await this.db.query.exercisesTable.findMany({
      where: inArray(exercisesTable.id, exerciseIds),
    });

    // Get all muscle activations for these exercises
    const allMuscles = await this.db
      .select({
        exerciseId: exerciseMusclesTable.exerciseId,
        id: muscleGroupsTable.id,
        name: muscleGroupsTable.name,
        displayName: muscleGroupsTable.displayName,
        activationPercent: exerciseMusclesTable.activationPercent,
      })
      .from(exerciseMusclesTable)
      .innerJoin(
        muscleGroupsTable,
        eq(exerciseMusclesTable.muscleGroupId, muscleGroupsTable.id),
      )
      .where(inArray(exerciseMusclesTable.exerciseId, exerciseIds));

    // Group muscles by exercise ID
    const musclesByExercise = new Map<number, MuscleActivationDto[]>();
    allMuscles.forEach((muscle) => {
      if (!musclesByExercise.has(muscle.exerciseId)) {
        musclesByExercise.set(muscle.exerciseId, []);
      }
      musclesByExercise.get(muscle.exerciseId)!.push({
        id: muscle.id,
        name: muscle.name,
        displayName: muscle.displayName,
        activationPercent: muscle.activationPercent,
      });
    });

    // Combine exercises with their muscles
    return exercises.map((exercise) => ({
      ...exercise,
      muscles: musclesByExercise.get(exercise.id) || [],
    }));
  }

  private calculateMatchDetails(
    exercise1: ExerciseWithMuscles,
    exercise2: ExerciseWithMuscles,
  ): MatchDetailsDto {
    // Use weighted muscle similarity based on activation percentages
    const muscleSimilarity =
      MuscleSimilarityUtil.calculateWeightedMuscleSimilarity(
        exercise1.muscles,
        exercise2.muscles,
      );

    const movementPatternMatch =
      exercise1.movementPattern === exercise2.movementPattern
        ? 1.0
        : MuscleSimilarityUtil.areSimilarMovementPatterns(
              exercise1.movementPattern || '',
              exercise2.movementPattern || '',
            )
          ? 0.7
          : 0.0;

    const exerciseTypeMatch =
      exercise1.exerciseType === exercise2.exerciseType ? 1.0 : 0.5;

    const maxComplexityDiff = 2.0;
    const complexityDiff = Math.abs(
      (exercise1.complexityScore || 1.0) - (exercise2.complexityScore || 1.0),
    );
    const complexitySimilarity = Math.max(
      0,
      1.0 - complexityDiff / maxComplexityDiff,
    );

    return {
      muscleSimilarity,
      movementPatternMatch,
      exerciseTypeMatch,
      complexitySimilarity,
    };
  }

  private calculateSimilarityScore(matchDetails: MatchDetailsDto): number {
    return (
      matchDetails.muscleSimilarity * 0.5 + // Increased weight for muscle similarity
      matchDetails.movementPatternMatch * 0.25 +
      matchDetails.exerciseTypeMatch * 0.2 +
      matchDetails.complexitySimilarity * 0.05
    );
  }

  private mapToExerciseDto(exercise: ExerciseWithMuscles): ExerciseDto {
    return {
      id: exercise.id,
      name: exercise.name,
      description: exercise.description || '',
      equipment: exercise.equipment || '',
      muscles: exercise.muscles,
      injuryRiskLevel: exercise.injuryRiskLevel,
      jointStressAreas: exercise.jointStressAreas || [],
      movementPattern: exercise.movementPattern || '',
      exerciseType: exercise.exerciseType as 'compound' | 'isolation',
      complexityScore: exercise.complexityScore,
    };
  }
}
