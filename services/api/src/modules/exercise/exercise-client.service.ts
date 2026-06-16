import {
  Inject,
  Injectable,
  NotFoundException,
  OnModuleInit,
  ServiceUnavailableException,
} from '@nestjs/common';
import type { ClientGrpc } from '@nestjs/microservices';
import { firstValueFrom, Observable } from 'rxjs';
import {
  Exercise,
  ExerciseResolution,
  InferredExercise,
  Substitution,
} from './exercise.types';

const GRPC_NOT_FOUND = 5;

// Wire shapes as produced by the gRPC loader for exercise/v1/exercise.proto.
interface RawExercise {
  id: number;
  name: string;
  movementPattern: string;
  exerciseType: string;
  intensityCategory: string;
  attributes?: Partial<Exercise['attributes']>;
  muscles?: Array<{
    name: string;
    displayName: string;
    role: string;
    activationPercent: number;
  }>;
  safety?: {
    injuryRiskLevel?: number;
    complexityScore?: number;
    jointStressAreas?: string[];
  };
}

interface ExerciseServiceGrpc {
  inferExercises(request: { names: string[] }): Observable<{
    exercises?: Array<{
      exercise: RawExercise;
      requestedName: string;
      resolution: string;
      confidence: number;
    }>;
  }>;
  getExercises(request: {
    ids: number[];
  }): Observable<{ exercises?: RawExercise[] }>;
  findSubstitutions(request: {
    exerciseId: number;
    excludeJointStress?: string[];
    excludeExerciseIds?: number[];
    limit?: number;
  }): Observable<{
    substitutions?: Array<{
      exercise: RawExercise;
      score: number;
      reason: string;
    }>;
  }>;
}

/**
 * Thin client for the exercise-service gRPC API. The exercise domain
 * (inference, persistence, substitution scoring) lives entirely in
 * exercise-service; this class only transports and reshapes.
 */
@Injectable()
export class ExerciseClientService implements OnModuleInit {
  private client: ExerciseServiceGrpc;

  constructor(@Inject('EXERCISE_PACKAGE') private readonly grpc: ClientGrpc) {}

  onModuleInit() {
    this.client = this.grpc.getService<ExerciseServiceGrpc>('ExerciseService');
  }

  /**
   * Resolve raw exercise names into structured exercises. Returns one entry
   * per name, in input order; names are persisted by the service so the
   * returned IDs are stable.
   */
  async inferExercises(names: string[]): Promise<InferredExercise[]> {
    if (names.length === 0) {
      return [];
    }

    try {
      const result = await firstValueFrom(
        this.client.inferExercises({ names }),
      );
      return (result.exercises ?? []).map((entry) => ({
        exercise: this.toExercise(entry.exercise),
        requestedName: entry.requestedName,
        resolution: this.toResolution(entry.resolution),
        confidence: entry.confidence,
      }));
    } catch (error) {
      console.error('Failed to infer exercises via gRPC:', error);
      throw new ServiceUnavailableException('Exercise service unavailable');
    }
  }

  /** Fetch exercises by ID. Unknown IDs are omitted from the result. */
  async getExercises(ids: number[]): Promise<Exercise[]> {
    if (ids.length === 0) {
      return [];
    }

    try {
      const result = await firstValueFrom(this.client.getExercises({ ids }));
      return (result.exercises ?? []).map((ex) => this.toExercise(ex));
    } catch (error) {
      console.error('Failed to fetch exercises via gRPC:', error);
      throw new ServiceUnavailableException('Exercise service unavailable');
    }
  }

  /** Fetch a single exercise, or null when it does not exist. */
  async getExercise(id: number): Promise<Exercise | null> {
    const [exercise] = await this.getExercises([id]);
    return exercise ?? null;
  }

  /** Find scored substitutes for an exercise. */
  async findSubstitutions(
    exerciseId: number,
    options: {
      excludeJointStress?: string[];
      excludeExerciseIds?: number[];
      limit?: number;
    } = {},
  ): Promise<Substitution[]> {
    try {
      const result = await firstValueFrom(
        this.client.findSubstitutions({
          exerciseId,
          excludeJointStress: options.excludeJointStress ?? [],
          excludeExerciseIds: options.excludeExerciseIds ?? [],
          limit: options.limit ?? 0,
        }),
      );
      return (result.substitutions ?? []).map((sub) => ({
        exercise: this.toExercise(sub.exercise),
        score: sub.score,
        reason: sub.reason,
      }));
    } catch (error) {
      if ((error as { code?: number })?.code === GRPC_NOT_FOUND) {
        throw new NotFoundException(`Exercise ${exerciseId} not found`);
      }
      console.error('Failed to find substitutions via gRPC:', error);
      throw new ServiceUnavailableException('Exercise service unavailable');
    }
  }

  private toExercise(raw: RawExercise): Exercise {
    return {
      id: raw.id,
      name: raw.name,
      movementPattern: raw.movementPattern ?? '',
      exerciseType: raw.exerciseType as Exercise['exerciseType'],
      intensityCategory: raw.intensityCategory as Exercise['intensityCategory'],
      attributes: {
        equipment: raw.attributes?.equipment ?? '',
        laterality: raw.attributes?.laterality ?? '',
        angle: raw.attributes?.angle ?? '',
        grip: raw.attributes?.grip ?? '',
        tempo: raw.attributes?.tempo ?? '',
        forceVector: raw.attributes?.forceVector ?? '',
      },
      muscles: (raw.muscles ?? []).map((m) => ({
        name: m.name,
        displayName: m.displayName,
        role: m.role as Exercise['muscles'][number]['role'],
        activationPercent: m.activationPercent,
      })),
      safety: {
        injuryRiskLevel: raw.safety?.injuryRiskLevel ?? 0,
        complexityScore: raw.safety?.complexityScore ?? 0,
        jointStressAreas: raw.safety?.jointStressAreas ?? [],
      },
    };
  }

  private toResolution(raw: string): ExerciseResolution {
    return raw === 'RESOLUTION_MATCHED' ? 'matched' : 'inferred';
  }
}
