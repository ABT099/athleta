import { Injectable, NotFoundException } from '@nestjs/common';
import { eq, and, ne, lte, inArray } from 'drizzle-orm';
import * as schema from '../../db/schema';
import { MuscleSimilarityUtil } from './utils/muscle-similarity.util';
import { AIEngineClient } from '../../clients/ai-engine.client';
import {
  SubstitutionResultDto,
  ExerciseDto,
  MatchDetailsDto,
} from './dto/substitution-result.dto';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';
import { DatabaseService } from '../database/database.service';

@Injectable()
export class ExerciseSubstitutionService {
  constructor(
    private readonly databaseService: DatabaseService,
    private readonly aiEngineClient: AIEngineClient,
  ) {}

  async findSubstitutions(
    originalExerciseId: number,
    filters?: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    // Get original exercise
    const originalExercise = await this.databaseService.db.query.exercisesTable.findFirst({
      where: eq(schema.exercisesTable.id, originalExerciseId),
    });

    if (!originalExercise) {
      throw new NotFoundException(
        `Exercise with ID ${originalExerciseId} not found`,
      );
    }

    // Build query conditions
    const conditions = [ne(schema.exercisesTable.id, originalExerciseId)];

    // Filter by equipment if specified
    if (filters?.availableEquipment && filters.availableEquipment.length > 0) {
      conditions.push(
        inArray(schema.exercisesTable.equipment, filters.availableEquipment),
      );
    }

    // Filter by max complexity
    if (filters?.maxComplexity !== undefined) {
      conditions.push(
        lte(schema.exercisesTable.complexityScore, filters.maxComplexity),
      );
    }

    // Filter by max injury risk
    if (filters?.maxInjuryRisk !== undefined) {
      conditions.push(
        lte(schema.exercisesTable.injuryRiskLevel, filters.maxInjuryRisk),
      );
    }

    // Exclude specific exercise IDs
    if (filters?.excludeIds && filters.excludeIds.length > 0) {
      // Add each exclusion condition separately - they will be combined with AND
      // This ensures: id != excludeId1 AND id != excludeId2 AND id != excludeId3
      filters.excludeIds.forEach((id) => {
        conditions.push(ne(schema.exercisesTable.id, id));
      });
    }

    // Exclude exercises with specific joint stress
    if (
      filters?.excludeJointStress &&
      filters.excludeJointStress.length > 0
    ) {
      // For array fields, we need to check if any of the excluded joints are in the array
      // This is a simplified approach - in production, you might want to use array overlap operators
      // For now, we'll filter in JavaScript after fetching
    }

    // Get all exercises matching basic filters
    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;
    const candidateExercises = await this.databaseService.db.query.exercisesTable.findMany({
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

    // Calculate similarity scores
    const scoredExercises = filteredExercises
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
      this.aiEngineClient.getJointStressProfile(athleteId),
      this.aiEngineClient.getProblematicExercises(athleteId),
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

  private calculateMatchDetails(
    exercise1: typeof schema.exercisesTable.$inferSelect,
    exercise2: typeof schema.exercisesTable.$inferSelect,
  ): MatchDetailsDto {
    const primaryMuscleOverlap = MuscleSimilarityUtil.calculateJaccardSimilarity(
      exercise1.primaryMuscles || [],
      exercise2.primaryMuscles || [],
    );

    const secondaryMuscleOverlap = MuscleSimilarityUtil.calculateJaccardSimilarity(
      exercise1.secondaryMuscles || [],
      exercise2.secondaryMuscles || [],
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

    // Calculate complexity similarity, normalized to [0, 1]
    // Assuming complexity scores typically range from 0 to 2
    // Using a normalized difference to ensure result stays between 0 and 1
    const maxComplexityDiff = 2.0; // Maximum expected difference
    const complexityDiff = Math.abs(
      (exercise1.complexityScore || 1.0) - (exercise2.complexityScore || 1.0),
    );
    const complexitySimilarity = Math.max(0, 1.0 - (complexityDiff / maxComplexityDiff));

    return {
      primaryMuscleOverlap,
      movementPatternMatch,
      exerciseTypeMatch,
      secondaryMuscleOverlap,
      complexitySimilarity,
    };
  }

  private calculateSimilarityScore(matchDetails: MatchDetailsDto): number {
    return (
      matchDetails.primaryMuscleOverlap * 0.4 +
      matchDetails.movementPatternMatch * 0.25 +
      matchDetails.exerciseTypeMatch * 0.2 +
      matchDetails.secondaryMuscleOverlap * 0.1 +
      matchDetails.complexitySimilarity * 0.05
    );
  }

  private mapToExerciseDto(
    exercise: typeof schema.exercisesTable.$inferSelect,
  ): ExerciseDto {
    return {
      id: exercise.id,
      name: exercise.name,
      description: exercise.description || '',
      equipment: exercise.equipment || '',
      primaryMuscles: exercise.primaryMuscles || [],
      secondaryMuscles: exercise.secondaryMuscles || [],
      injuryRiskLevel: exercise.injuryRiskLevel,
      jointStressAreas: exercise.jointStressAreas || [],
      movementPattern: exercise.movementPattern || '',
      exerciseType: exercise.exerciseType as 'compound' | 'isolation',
      complexityScore: exercise.complexityScore,
    };
  }
}

