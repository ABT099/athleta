import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { and, eq, inArray, not, sql } from 'drizzle-orm';
import { exerciseMuscles, exercises, muscleGroups } from 'src/db/schema';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import { DRIZZLE, type DrizzleDB } from '../common/database/database.provider';
import { InferenceService } from './inference.service';
import { MuscleSimilarityUtil } from './utils/muscle-similarity.util';
import {
  ExerciseType,
  IntensityCategory,
  MatchDetails,
  MuscleActivation,
  MuscleRole,
  MuscleTarget,
  SubstitutionResult,
} from './exercise.types';

type SubstitutionFilters = {
  excludeJointStress?: string[];
  excludeIds?: number[];
  limit?: number;
};

type SubstitutionContext = {
  filters: SubstitutionFilters;
  athleteId?: number;
};

type ExerciseEntity = typeof exercises.$inferSelect;

interface ExerciseWithMuscles extends ExerciseEntity {
  muscles: MuscleActivation[];
}

@Injectable()
export class ExerciseService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly aiEngineIntegration: AIEngineIntegration,
    private readonly inferenceService: InferenceService,
  ) {}

  /**
   * Find exercise substitutions with optional athlete personalization.
   * When athleteId is provided, automatically enriches filters with AI insights.
   *
   * @param originalExerciseId - The exercise to find substitutions for
   * @param context - Optional filters and athlete ID for personalization
   */
  async findSubstitutions(
    originalExerciseId: number,
    context: SubstitutionContext = { filters: {} },
  ): Promise<SubstitutionResult[]> {
    const originalExercise =
      await this.getExerciseWithMuscles(originalExerciseId);

    if (!originalExercise) {
      throw new NotFoundException(
        `Exercise with ID ${originalExerciseId} not found`,
      );
    }

    // Apply personalization if athlete context provided
    const enrichedFilters = await this.enrichFiltersWithPersonalization(
      context.filters,
      context.athleteId,
    );

    const candidateExercises = await this.fetchCandidateExercises(
      originalExerciseId,
      enrichedFilters,
    );

    const patternScores = await this.fetchPatternSimilarities(
      originalExercise.name,
    );

    return this.scoreAndRankCandidates(
      originalExercise,
      candidateExercises,
      patternScores,
      enrichedFilters.limit || 5,
    );
  }

  private async enrichFiltersWithPersonalization(
    baseFilters: SubstitutionFilters,
    athleteId?: number,
  ): Promise<SubstitutionFilters> {
    if (!athleteId) {
      return baseFilters;
    }

    try {
      const [jointProfile, problematicExercises] = await Promise.all([
        this.aiEngineIntegration.getJointStressProfile(athleteId),
        this.aiEngineIntegration.getProblematicExercises(athleteId),
      ]);

      return {
        ...baseFilters,
        excludeJointStress: this.mergeUniqueValues(
          baseFilters.excludeJointStress,
          jointProfile.avoidJoints,
        ),
        excludeIds: this.mergeUniqueValues(
          baseFilters.excludeIds,
          problematicExercises.map(
            (pe: { exerciseId: number }) => pe.exerciseId,
          ),
        ),
      };
    } catch (error) {
      console.warn(
        'Failed to fetch athlete personalization, using base filters:',
        error,
      );
      return baseFilters;
    }
  }

  private async fetchCandidateExercises(
    originalExerciseId: number,
    filters: SubstitutionFilters,
  ): Promise<ExerciseWithMuscles[]> {
    const conditions = [not(eq(exercises.id, originalExerciseId))];

    if (filters.excludeIds && filters.excludeIds.length > 0) {
      conditions.push(not(inArray(exercises.id, filters.excludeIds)));
    }

    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;
    const rawCandidates = await this.db.query.exercises.findMany({
      where: whereClause,
    });

    const filteredByJointStress = this.filterByJointStress(
      rawCandidates,
      filters.excludeJointStress,
    );

    const candidateIds = filteredByJointStress.map((e) => e.id);
    return this.getMultipleExercisesWithMuscles(candidateIds);
  }

  private filterByJointStress(
    exercises: ExerciseEntity[],
    excludeJointStress?: string[],
  ): ExerciseEntity[] {
    if (!excludeJointStress || excludeJointStress.length === 0) {
      return exercises;
    }

    return exercises.filter((exercise) => {
      const hasExcludedJoint = excludeJointStress.some((joint) =>
        exercise.jointStressAreas?.includes(joint),
      );
      return !hasExcludedJoint;
    });
  }

  private async fetchPatternSimilarities(
    exerciseName: string,
  ): Promise<Map<string, number>> {
    try {
      const similarByPattern =
        await this.inferenceService.findSimilarExercisesByPattern(
          exerciseName,
          { limit: 20 },
        );
      return MuscleSimilarityUtil.mapPatternMatchesToScores(
        similarByPattern,
        20,
      );
    } catch (error) {
      console.warn(
        'Pattern matching unavailable, using muscle-only scoring:',
        error,
      );
      return new Map();
    }
  }

  private scoreAndRankCandidates(
    originalExercise: ExerciseWithMuscles,
    candidates: ExerciseWithMuscles[],
    patternScores: Map<string, number>,
    limit: number,
  ): SubstitutionResult[] {
    return candidates
      .map((candidate) =>
        this.createSubstitutionResult(
          originalExercise,
          candidate,
          patternScores,
        ),
      )
      .sort((a, b) => b.similarityScore - a.similarityScore)
      .slice(0, limit);
  }

  private createSubstitutionResult(
    original: ExerciseWithMuscles,
    candidate: ExerciseWithMuscles,
    patternScores: Map<string, number>,
  ): SubstitutionResult {
    const matchDetails = this.calculateMatchDetails(original, candidate);
    const muscleScore = this.calculateMuscleSimilarityScore(matchDetails);
    const patternScore = patternScores.get(candidate.name) || 0;

    // Hybrid scoring: 60% muscle-based + 40% pattern-based
    const hybridScore = muscleScore * 0.6 + patternScore * 0.4;

    const patternSimilarity = MuscleSimilarityUtil.calculatePatternSimilarity(
      {
        movementPattern: original.movementPattern || '',
        equipment: original.equipment || '',
        exerciseType: original.exerciseType || '',
      },
      {
        movementPattern: candidate.movementPattern || '',
        equipment: candidate.equipment || '',
        exerciseType: candidate.exerciseType || '',
      },
    );

    const enhancedMatchDetails: MatchDetails = {
      ...matchDetails,
      patternSimilarity,
      modifierMatch: patternScore,
    };

    return {
      exercise: {
        id: candidate.id,
        name: candidate.name,
        equipment: candidate.equipment || '',
        muscles: candidate.muscles,
        injuryRiskLevel: candidate.injuryRiskLevel,
        jointStressAreas: candidate.jointStressAreas || [],
        movementPattern: candidate.movementPattern || '',
        exerciseType: candidate.exerciseType,
        complexityScore: candidate.complexityScore,
      },
      similarityScore: hybridScore,
      reason:
        MuscleSimilarityUtil.generateSubstitutionReason(enhancedMatchDetails),
      matchDetails: enhancedMatchDetails,
    };
  }

  private async getExerciseWithMuscles(
    exerciseId: number,
  ): Promise<ExerciseWithMuscles | null> {
    const exercise = await this.db.query.exercises.findFirst({
      where: eq(exercises.id, exerciseId),
    });

    if (!exercise) {
      return null;
    }

    const musclesRaw = await this.db
      .select({
        id: muscleGroups.id,
        name: muscleGroups.name,
        displayName: muscleGroups.displayName,
        role: exerciseMuscles.role,
      })
      .from(exerciseMuscles)
      .innerJoin(
        muscleGroups,
        eq(exerciseMuscles.muscleGroupId, muscleGroups.id),
      )
      .where(eq(exerciseMuscles.exerciseId, exerciseId));

    const muscles = musclesRaw.map((m) => ({
      ...m,
      activationPercent: this.roleToActivationPercent(m.role),
    }));

    return {
      ...exercise,
      muscles,
    };
  }

  private async getMultipleExercisesWithMuscles(
    exerciseIds: number[],
  ): Promise<ExerciseWithMuscles[]> {
    if (exerciseIds.length === 0) {
      return [];
    }

    const exercisesData = await this.db.query.exercises.findMany({
      where: inArray(exercises.id, exerciseIds),
    });

    const allMusclesRaw = await this.db
      .select({
        exerciseId: exerciseMuscles.exerciseId,
        id: muscleGroups.id,
        name: muscleGroups.name,
        displayName: muscleGroups.displayName,
        role: exerciseMuscles.role,
      })
      .from(exerciseMuscles)
      .innerJoin(
        muscleGroups,
        eq(exerciseMuscles.muscleGroupId, muscleGroups.id),
      )
      .where(inArray(exerciseMuscles.exerciseId, exerciseIds));

    const musclesByExercise = new Map<number, MuscleActivation[]>();
    allMusclesRaw.forEach((muscle) => {
      if (!musclesByExercise.has(muscle.exerciseId)) {
        musclesByExercise.set(muscle.exerciseId, []);
      }
      musclesByExercise.get(muscle.exerciseId)!.push({
        id: muscle.id,
        name: muscle.name,
        displayName: muscle.displayName,
        activationPercent: this.roleToActivationPercent(muscle.role),
      });
    });

    return exercisesData.map((exercise) => ({
      ...exercise,
      muscles: musclesByExercise.get(exercise.id) || [],
    }));
  }

  private calculateMatchDetails(
    exercise1: ExerciseWithMuscles,
    exercise2: ExerciseWithMuscles,
  ): MatchDetails {
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
      patternSimilarity: 0, // Filled in by caller
      modifierMatch: 0, // Filled in by caller
      hierarchyDistance: 0, // Placeholder for future use
    };
  }

  private calculateMuscleSimilarityScore(matchDetails: MatchDetails): number {
    return (
      matchDetails.muscleSimilarity * 0.5 +
      matchDetails.movementPatternMatch * 0.25 +
      matchDetails.exerciseTypeMatch * 0.2 +
      matchDetails.complexitySimilarity * 0.05
    );
  }

  private roleToActivationPercent(role: string): number {
    switch (role) {
      case 'prime_mover':
        return 85;
      case 'synergist':
        return 55;
      case 'stabilizer':
        return 25;
      default:
        return 0;
    }
  }

  /**
   * Determine if an exercise should be primary or accessory based on training science
   *
   * Scientific basis:
   * - Compound Heavy exercises have very high CNS demand → Primary when performed early
   * - Compound Moderate exercises have moderate CNS demand → Primary in first half
   * - Isolation exercises have low CNS demand → Typically accessory
   * - First 2-3 exercises should be primary (neurological freshness critical)
   *
   * @param intensityCategory - Exercise intensity category (compound_heavy/moderate/isolation)
   * @param orderInWorkout - Position in workout (1-indexed)
   * @param totalExercises - Total number of exercises in the workout
   * @returns true if exercise should be primary, false if accessory
   */
  static determineIsPrimary(
    intensityCategory: IntensityCategory,
    orderInWorkout: number,
    totalExercises: number,
  ): boolean {
    // Handle edge cases
    if (totalExercises <= 2) {
      // With 1-2 exercises, all are primary
      return true;
    }

    // First 3 exercises are always primary (CNS freshness critical)
    if (orderInWorkout <= 3) {
      return true;
    }

    // Calculate relative position (0-1 scale)
    const relativePosition = orderInWorkout / totalExercises;

    // Apply hybrid algorithm
    switch (intensityCategory) {
      case 'compound_heavy':
        // Compound heavy in first 60% → Primary
        return relativePosition <= 0.6;

      case 'compound_moderate':
        // Compound moderate in first 40% → Primary
        return relativePosition <= 0.4;

      case 'isolation':
        // Isolation exercises are typically accessory
        return false;

      default:
        // Conservative default: treat as accessory
        return false;
    }
  }

  /**
   * Merges two arrays removing duplicates.
   */
  private mergeUniqueValues<T>(arr1?: T[], arr2?: T[]): T[] {
    const combined = [...(arr1 || []), ...(arr2 || [])];
    return [...new Set(combined)];
  }

  /**
   * Batch upsert exercises from exercise names
   * This is called internally when creating workouts with custom exercise names
   */
  async batchUpsertExercises(exerciseNames: string[]): Promise<
    Array<{
      id: number;
      name: string;
      intensityCategory: IntensityCategory;
      exerciseType: ExerciseType;
      muscles: Array<MuscleTarget>;
    }>
  > {
    if (exerciseNames.length === 0) {
      return [];
    }

    // Get unique exercise names
    const uniqueNames = this.mergeUniqueValues(exerciseNames);

    // Check which exercises already exist and get their IDs
    const existingExercises = await this.db
      .select({ id: exercises.id, name: exercises.name })
      .from(exercises)
      .where(inArray(exercises.name, uniqueNames));

    const existingNames = new Set(
      existingExercises.map((ex) => ex.name.toLowerCase()),
    );

    // Filter out exercises that already exist
    const missingNames = uniqueNames.filter(
      (name) => !existingNames.has(name.toLowerCase()),
    );

    // Build a map to store exercise IDs (name -> id)
    const exerciseIdMap = new Map<string, number>(
      existingExercises.map((ex) => [ex.name.toLowerCase(), ex.id]),
    );

    // Insert new exercises if needed
    if (missingNames.length > 0) {
      console.log(`Inferring ${missingNames.length} new exercises...`);

      // Call gRPC inference service
      const inferredExercises =
        await this.inferenceService.batchParseExercises(missingNames);

      // Get all muscle groups for mapping
      const muscleGroupsData = await this.db
        .select({ id: muscleGroups.id, name: muscleGroups.name })
        .from(muscleGroups);

      const muscleMap = new Map(muscleGroupsData.map((mg) => [mg.name, mg.id]));

      await this.db.transaction(async (tx) => {
        const insertedExercises = await tx
          .insert(exercises)
          .values(
            inferredExercises.map((exercise) => ({
              name: exercise.name,
              equipment: exercise.equipment,
              injuryRiskLevel: exercise.injuryRiskLevel,
              jointStressAreas: exercise.jointStressAreas,
              movementPattern: exercise.movementPattern,
              exerciseType: exercise.exerciseType,
              complexityScore: exercise.complexityScore,
              intensityCategory: exercise.intensityCategory,
            })),
          )
          .onConflictDoUpdate({
            target: exercises.name,
            set: {
              equipment: sql`excluded.equipment`,
              injuryRiskLevel: sql`excluded.injury_risk_level`,
              jointStressAreas: sql`excluded.joint_stress_areas`,
              movementPattern: sql`excluded.movement_pattern`,
              exerciseType: sql`excluded.exercise_type`,
              complexityScore: sql`excluded.complexity_score`,
              intensityCategory: sql`excluded.intensity_category`,
            },
          })
          .returning({ id: exercises.id, name: exercises.name });

        for (const exercise of insertedExercises) {
          exerciseIdMap.set(exercise.name.toLowerCase(), exercise.id);
        }

        const exerciseIds = insertedExercises.map((ex) => ex.id);
        if (exerciseIds.length > 0) {
          await tx
            .delete(exerciseMuscles)
            .where(inArray(exerciseMuscles.exerciseId, exerciseIds));
        }

        // Build all muscle inserts
        const allMuscleInserts: {
          exerciseId: number;
          muscleGroupId: number;
          role: MuscleRole;
        }[] = [];
        for (const exerciseData of inferredExercises) {
          const exerciseId = exerciseIdMap.get(exerciseData.name.toLowerCase());
          if (!exerciseId) continue;

          for (const target of exerciseData.muscleTargets) {
            const muscleId = muscleMap.get(target.name);
            if (!muscleId) {
              console.warn(
                `Muscle not found: ${target.name} for exercise ${exerciseData.name}`,
              );
              continue;
            }
            allMuscleInserts.push({
              exerciseId,
              muscleGroupId: muscleId,
              role: target.role,
            });
          }
        }

        // Batch insert all muscle relationships
        if (allMuscleInserts.length > 0) {
          await tx.insert(exerciseMuscles).values(allMuscleInserts);
        }
      });

      console.log(
        `✓ Successfully upserted ${inferredExercises.length} exercises`,
      );
    } else {
      console.log('All exercises already exist in database');
    }

    // Get all exercise IDs
    const allExerciseIds = Array.from(exerciseIdMap.values());

    // Fetch exercise metadata
    const exerciseMetadata = await this.db
      .select({
        id: exercises.id,
        name: exercises.name,
        intensityCategory: exercises.intensityCategory,
        exerciseType: exercises.exerciseType,
      })
      .from(exercises)
      .where(inArray(exercises.id, allExerciseIds));

    const exerciseMetadataMap = new Map(
      exerciseMetadata.map((ex) => [ex.id, ex]),
    );

    // Fetch muscle data for all exercises
    const muscleData = await this.db
      .select({
        exerciseId: exerciseMuscles.exerciseId,
        muscleName: muscleGroups.name,
        role: exerciseMuscles.role,
      })
      .from(exerciseMuscles)
      .innerJoin(
        muscleGroups,
        eq(exerciseMuscles.muscleGroupId, muscleGroups.id),
      )
      .where(inArray(exerciseMuscles.exerciseId, allExerciseIds));

    // Build a map of exercise ID to muscles
    const exerciseMusclesMap = new Map<number, Array<MuscleTarget>>();
    for (const row of muscleData) {
      if (!exerciseMusclesMap.has(row.exerciseId)) {
        exerciseMusclesMap.set(row.exerciseId, []);
      }
      exerciseMusclesMap.get(row.exerciseId)!.push({
        name: row.muscleName,
        role: row.role as MuscleRole,
      });
    }

    // Return data in same order as input
    return exerciseNames.map((name) => {
      const id = exerciseIdMap.get(name.toLowerCase());
      if (!id) {
        throw new Error(`Exercise not found after upsert: ${name}`);
      }
      const metadata = exerciseMetadataMap.get(id);
      if (!metadata) {
        throw new Error(`Exercise metadata not found: ${name}`);
      }
      return {
        id,
        name: metadata.name,
        intensityCategory: metadata.intensityCategory,
        exerciseType: metadata.exerciseType,
        muscles: exerciseMusclesMap.get(id) || [],
      };
    });
  }
}
