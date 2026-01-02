import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import { exercises, muscleGroups, exerciseMuscles } from 'src/db/schema';
import { eq, ne, lte, inArray, and, sql } from 'drizzle-orm';
import { MuscleSimilarityUtil } from './utils/muscle-similarity.util';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import {
  SubstitutionResultDto,
  ExerciseDto,
  MatchDetailsDto,
  MuscleActivationDto,
} from './dto/substitution-result.dto';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';
import { InferenceService, type ExerciseData } from './inference.service';

type ExerciseEntity = typeof exercises.$inferSelect;

interface ExerciseWithMuscles extends ExerciseEntity {
  muscles: MuscleActivationDto[];
}

@Injectable()
export class ExerciseService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly aiEngineIntegration: AIEngineIntegration,
    private readonly inferenceService: InferenceService,
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
    const conditions = [ne(exercises.id, originalExerciseId)];

    if (filters?.availableEquipment && filters.availableEquipment.length > 0) {
      conditions.push(inArray(exercises.equipment, filters.availableEquipment));
    }

    if (filters?.maxComplexity !== undefined) {
      conditions.push(lte(exercises.complexityScore, filters.maxComplexity));
    }

    if (filters?.maxInjuryRisk !== undefined) {
      conditions.push(lte(exercises.injuryRiskLevel, filters.maxInjuryRisk));
    }

    if (filters?.excludeIds && filters.excludeIds.length > 0) {
      filters.excludeIds.forEach((id) => {
        conditions.push(ne(exercises.id, id));
      });
    }

    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;
    const candidateExercises = await this.db.query.exercises.findMany({
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

    // NEW: Get pattern-based similar exercises from Neo4j (automatic)
    let patternScores = new Map<string, number>();
    try {
      const similarByPattern =
        await this.inferenceService.findSimilarExercisesByPattern(
          originalExercise.name,
          { limit: 20 },
        );
      patternScores = MuscleSimilarityUtil.mapPatternMatchesToScores(
        similarByPattern,
        20,
      );
    } catch (error) {
      console.warn(
        'Pattern matching unavailable, using muscle-only scoring:',
        error,
      );
      // Empty map = fallback to muscle-only scoring
    }

    // Calculate similarity scores with hybrid approach
    const scoredExercises = exercisesWithMuscles
      .map((exercise) => {
        const matchDetails = this.calculateMatchDetails(
          originalExercise,
          exercise,
        );

        // Get muscle-based similarity score
        const muscleScore = this.calculateSimilarityScore(matchDetails);

        // Get pattern-based similarity score from Neo4j results
        const patternScore = patternScores.get(exercise.name) || 0;

        // NEW: Calculate hybrid score (60% muscle + 40% pattern)
        const hybridScore = muscleScore * 0.6 + patternScore * 0.4;

        // NEW: Calculate pattern similarity for match details
        const patternSimilarity =
          MuscleSimilarityUtil.calculatePatternSimilarity(
            {
              movementPattern: originalExercise.movementPattern || '',
              equipment: originalExercise.equipment || '',
              exerciseType: originalExercise.exerciseType || '',
            },
            {
              movementPattern: exercise.movementPattern || '',
              equipment: exercise.equipment || '',
              exerciseType: exercise.exerciseType || '',
            },
          );

        // Enhanced match details with pattern information
        const enhancedMatchDetails = {
          ...matchDetails,
          patternSimilarity,
          modifierMatch: patternScore, // Neo4j score includes modifier matching
        };

        return {
          exercise: this.mapToExerciseDto(exercise),
          similarityScore: hybridScore, // Use hybrid score
          reason:
            MuscleSimilarityUtil.generateSubstitutionReason(
              enhancedMatchDetails,
            ),
          matchDetails: enhancedMatchDetails,
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
    const exercise = await this.db.query.exercises.findFirst({
      where: eq(exercises.id, exerciseId),
    });

    if (!exercise) {
      return null;
    }

    // Get muscle activations for this exercise
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

    // Convert role to activation percent for similarity calculations
    const muscles = musclesRaw.map((m) => ({
      ...m,
      activationPercent: this.roleToActivationPercent(m.role),
    }));

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
    const exercisesData = await this.db.query.exercises.findMany({
      where: inArray(exercises.id, exerciseIds),
    });

    // Get all muscle activations for these exercises
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

    // Group muscles by exercise ID and convert role to activation percent
    const musclesByExercise = new Map<number, MuscleActivationDto[]>();
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

    // Combine exercises with their muscles
    return exercisesData.map((exercise) => ({
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
      equipment: exercise.equipment || '',
      muscles: exercise.muscles,
      injuryRiskLevel: exercise.injuryRiskLevel,
      jointStressAreas: exercise.jointStressAreas || [],
      movementPattern: exercise.movementPattern || '',
      exerciseType: exercise.exerciseType as 'compound' | 'isolation',
      complexityScore: exercise.complexityScore,
    };
  }

  /**
   * Convert muscle role to activation percent for similarity calculations
   */
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
    intensityCategory: 'compound_heavy' | 'compound_moderate' | 'isolation',
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
   * Batch upsert exercises from exercise names
   * This is called internally when creating workouts with custom exercise names
   */
  async batchUpsertExercises(exerciseNames: string[]): Promise<
    Array<{
      id: number;
      name: string;
      intensityCategory: 'compound_heavy' | 'compound_moderate' | 'isolation';
      exerciseType: 'compound' | 'isolation';
      muscles: Array<{ name: string; role: string }>;
    }>
  > {
    if (exerciseNames.length === 0) {
      return [];
    }

    // Get unique exercise names
    const uniqueNames = [...new Set(exerciseNames)];

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
              exerciseType: exercise.exerciseType as 'compound' | 'isolation',
              complexityScore: exercise.complexityScore,
              intensityCategory: exercise.intensityCategory as
                | 'compound_heavy'
                | 'compound_moderate'
                | 'isolation',
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
          role: 'prime_mover' | 'synergist' | 'stabilizer';
        }[] = [];
        for (const exerciseData of inferredExercises) {
          const exerciseId = exerciseIdMap.get(exerciseData.name.toLowerCase());
          if (!exerciseId) continue;

          for (const target of exerciseData.muscleTargets) {
            const muscleId = muscleMap.get(target.muscleName);
            if (!muscleId) {
              console.warn(
                `Muscle not found: ${target.muscleName} for exercise ${exerciseData.name}`,
              );
              continue;
            }
            allMuscleInserts.push({
              exerciseId,
              muscleGroupId: muscleId,
              role: target.role as 'prime_mover' | 'synergist' | 'stabilizer',
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
    const exerciseMusclesMap = new Map<
      number,
      Array<{ name: string; role: string }>
    >();
    for (const row of muscleData) {
      if (!exerciseMusclesMap.has(row.exerciseId)) {
        exerciseMusclesMap.set(row.exerciseId, []);
      }
      exerciseMusclesMap.get(row.exerciseId)!.push({
        name: row.muscleName,
        role: row.role,
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
        intensityCategory: metadata.intensityCategory as
          | 'compound_heavy'
          | 'compound_moderate'
          | 'isolation',
        exerciseType: metadata.exerciseType as 'compound' | 'isolation',
        muscles: exerciseMusclesMap.get(id) || [],
      };
    });
  }
}
