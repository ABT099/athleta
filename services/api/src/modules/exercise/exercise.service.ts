import { Injectable, NotFoundException, Inject } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import { exercisesTable } from '../../db/schema';
import { eq, ne, lte, inArray, and } from 'drizzle-orm';
import { MuscleSimilarityUtil } from './utils/muscle-similarity.util';
import { AIEngineIntegration } from './integrations/ai-engine.integration';
import {
  SubstitutionResultDto,
  ExerciseDto,
  MatchDetailsDto,
} from './dto/substitution-result.dto';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';

type ExerciseEntity = typeof exercisesTable.$inferSelect;

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
    // Get original exercise
    const originalExercise = await this.db.query.exercisesTable.findFirst({
      where: eq(exercisesTable.id, originalExerciseId),
    });

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

  private calculateMatchDetails(
    exercise1: ExerciseEntity,
    exercise2: ExerciseEntity,
  ): MatchDetailsDto {
    const primaryMuscleOverlap =
      MuscleSimilarityUtil.calculateJaccardSimilarity(
        exercise1.primaryMuscles || [],
        exercise2.primaryMuscles || [],
      );

    const secondaryMuscleOverlap =
      MuscleSimilarityUtil.calculateJaccardSimilarity(
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

    const maxComplexityDiff = 2.0;
    const complexityDiff = Math.abs(
      (exercise1.complexityScore || 1.0) - (exercise2.complexityScore || 1.0),
    );
    const complexitySimilarity = Math.max(
      0,
      1.0 - complexityDiff / maxComplexityDiff,
    );

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

  private mapToExerciseDto(exercise: ExerciseEntity): ExerciseDto {
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
