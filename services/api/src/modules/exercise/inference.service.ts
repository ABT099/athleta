import { Injectable, Inject, OnModuleInit } from '@nestjs/common';
import type { ClientGrpc } from '@nestjs/microservices';
import { firstValueFrom, Observable } from 'rxjs';

interface MuscleTarget {
  muscleName: string;
  role: string;
}

interface ExerciseModifiers {
  implement: string;
  laterality: string;
  angle: string;
  gripStance: string;
  plane: string;
  tempo: string;
}

export interface ExerciseData {
  name: string;
  description: string;
  equipment: string;
  movementPattern: string;
  exerciseType: string;
  injuryRiskLevel: number;
  complexityScore: number;
  jointStressAreas: string[];
  intensityCategory: string;
  muscleTargets: MuscleTarget[];
  modifiers: ExerciseModifiers;
}

interface BatchParseRequest {
  exerciseNames: string[];
}

interface BatchExerciseData {
  exercises: ExerciseData[];
}

interface ParseRequest {
  exerciseName: string;
}

interface SimilarityRequest {
  exerciseName: string;
  sameEquipment?: boolean;
  sameLaterality?: boolean;
  sameAngle?: boolean;
  limit?: number;
}

interface SimilarityResponse {
  exerciseNames: string[];
}

interface ExerciseInferenceService {
  batchParseExercises(
    request: BatchParseRequest,
  ): Observable<BatchExerciseData>;
  parseSingleExercise(request: ParseRequest): Observable<ExerciseData>;
  findSimilarExercises(
    request: SimilarityRequest,
  ): Observable<SimilarityResponse>;
}

@Injectable()
export class InferenceService implements OnModuleInit {
  private inferenceService: ExerciseInferenceService;

  constructor(@Inject('INFERENCE_PACKAGE') private client: ClientGrpc) {}

  onModuleInit() {
    this.inferenceService = this.client.getService<ExerciseInferenceService>(
      'ExerciseInferenceService',
    );
  }

  /**
   * Parse multiple exercise names and return their biomechanical profiles
   */
  async batchParseExercises(exerciseNames: string[]): Promise<ExerciseData[]> {
    try {
      const result = await firstValueFrom(
        this.inferenceService.batchParseExercises({ exerciseNames }),
      );
      return result.exercises;
    } catch (error) {
      console.error('Failed to parse exercises via gRPC:', error);
      throw new Error('Exercise inference service unavailable');
    }
  }

  /**
   * Parse a single exercise name
   */
  async parseSingleExercise(exerciseName: string): Promise<ExerciseData> {
    try {
      return await firstValueFrom(
        this.inferenceService.parseSingleExercise({ exerciseName }),
      );
    } catch (error) {
      console.error('Failed to parse exercise via gRPC:', error);
      throw new Error('Exercise inference service unavailable');
    }
  }

  /**
   * Find exercises with similar movement patterns and modifiers
   * Automatically uses Neo4j pattern-based matching
   */
  async findSimilarExercisesByPattern(
    exerciseName: string,
    filters?: {
      sameEquipment?: boolean;
      sameLaterality?: boolean;
      sameAngle?: boolean;
      limit?: number;
    },
  ): Promise<string[]> {
    try {
      const result = await firstValueFrom(
        this.inferenceService.findSimilarExercises({
          exerciseName,
          sameEquipment: filters?.sameEquipment || false,
          sameLaterality: filters?.sameLaterality || false,
          sameAngle: filters?.sameAngle || false,
          limit: filters?.limit || 20,
        }),
      );
      return result.exerciseNames;
    } catch (error) {
      console.warn(
        'Failed to find similar exercises via gRPC, falling back to muscle-only:',
        error,
      );
      // Return empty array to signal fallback to muscle-only scoring
      return [];
    }
  }
}
