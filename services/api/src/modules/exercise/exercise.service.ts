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
import { InferenceService, type ExerciseData } from './inference.service';

type ExerciseEntity = typeof exercisesTable.$inferSelect;

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
    const exercise = await this.db.query.exercisesTable.findFirst({
      where: eq(exercisesTable.id, exerciseId),
    });

    if (!exercise) {
      return null;
    }

    // Get muscle activations for this exercise
    const musclesRaw = await this.db
      .select({
        id: muscleGroupsTable.id,
        name: muscleGroupsTable.name,
        displayName: muscleGroupsTable.displayName,
        role: exerciseMusclesTable.role,
      })
      .from(exerciseMusclesTable)
      .innerJoin(
        muscleGroupsTable,
        eq(exerciseMusclesTable.muscleGroupId, muscleGroupsTable.id),
      )
      .where(eq(exerciseMusclesTable.exerciseId, exerciseId));

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
    const exercises = await this.db.query.exercisesTable.findMany({
      where: inArray(exercisesTable.id, exerciseIds),
    });

    // Get all muscle activations for these exercises
    const allMusclesRaw = await this.db
      .select({
        exerciseId: exerciseMusclesTable.exerciseId,
        id: muscleGroupsTable.id,
        name: muscleGroupsTable.name,
        displayName: muscleGroupsTable.displayName,
        role: exerciseMusclesTable.role,
      })
      .from(exerciseMusclesTable)
      .innerJoin(
        muscleGroupsTable,
        eq(exerciseMusclesTable.muscleGroupId, muscleGroupsTable.id),
      )
      .where(inArray(exerciseMusclesTable.exerciseId, exerciseIds));

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
   * Batch upsert exercises from exercise names
   * This is called internally when creating workouts with custom exercise names
   */
  async batchUpsertExercises(exerciseNames: string[]): Promise<void> {
    if (exerciseNames.length === 0) {
      return;
    }

    // Get unique exercise names
    const uniqueNames = [...new Set(exerciseNames)];

    // Check which exercises already exist
    const existingExercises = await this.db
      .select({ name: exercisesTable.name })
      .from(exercisesTable)
      .where(inArray(exercisesTable.name, uniqueNames));

    const existingNames = new Set(
      existingExercises.map((ex) => ex.name.toLowerCase()),
    );

    // Filter out exercises that already exist
    const missingNames = uniqueNames.filter(
      (name) => !existingNames.has(name.toLowerCase()),
    );

    if (missingNames.length === 0) {
      console.log('All exercises already exist in database');
      return;
    }

    console.log(`Inferring ${missingNames.length} new exercises...`);

    // Call gRPC inference service
    const inferredExercises =
      await this.inferenceService.batchParseExercises(missingNames);

    // Get all muscle groups for mapping
    const muscleGroups = await this.db
      .select({ id: muscleGroupsTable.id, name: muscleGroupsTable.name })
      .from(muscleGroupsTable);

    const muscleMap = new Map(muscleGroups.map((mg) => [mg.name, mg.id]));

    // Insert exercises and their muscle relationships
    for (const exerciseData of inferredExercises) {
      await this.upsertSingleExercise(exerciseData, muscleMap);
    }

    console.log(
      `✓ Successfully upserted ${inferredExercises.length} exercises`,
    );
  }

  /**
   * Upsert a single exercise with its muscle relationships
   */
  private async upsertSingleExercise(
    exerciseData: ExerciseData,
    muscleMap: Map<string, number>,
  ): Promise<void> {
    // Insert or update exercise
    const [exercise] = await this.db
      .insert(exercisesTable)
      .values({
        name: exerciseData.name,
        equipment: exerciseData.equipment,
        injuryRiskLevel: exerciseData.injuryRiskLevel,
        jointStressAreas: exerciseData.jointStressAreas,
        movementPattern: exerciseData.movementPattern,
        exerciseType: exerciseData.exerciseType as 'compound' | 'isolation',
        complexityScore: exerciseData.complexityScore,
        intensityCategory: exerciseData.intensityCategory as
          | 'compound_heavy'
          | 'compound_moderate'
          | 'isolation',
      })
      .onConflictDoUpdate({
        target: exercisesTable.name,
        set: {
          equipment: exerciseData.equipment,
          injuryRiskLevel: exerciseData.injuryRiskLevel,
          jointStressAreas: exerciseData.jointStressAreas,
          movementPattern: exerciseData.movementPattern,
          exerciseType: exerciseData.exerciseType as 'compound' | 'isolation',
          complexityScore: exerciseData.complexityScore,
          intensityCategory: exerciseData.intensityCategory as
            | 'compound_heavy'
            | 'compound_moderate'
            | 'isolation',
        },
      })
      .returning();

    // Delete existing muscle relationships
    await this.db
      .delete(exerciseMusclesTable)
      .where(eq(exerciseMusclesTable.exerciseId, exercise.id));

    // Insert new muscle relationships
    const muscleInserts = exerciseData.muscleTargets
      .map((target) => {
        const muscleId = muscleMap.get(target.muscleName);
        if (!muscleId) {
          console.warn(
            `Muscle not found: ${target.muscleName} for exercise ${exerciseData.name}`,
          );
          return null;
        }
        return {
          exerciseId: exercise.id,
          muscleGroupId: muscleId,
          role: target.role as 'prime_mover' | 'synergist' | 'stabilizer',
        };
      })
      .filter((insert) => insert !== null);

    if (muscleInserts.length > 0) {
      await this.db.insert(exerciseMusclesTable).values(muscleInserts);
    }
  }
}
