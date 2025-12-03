import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

export interface JointStressProfileDto {
  avoidJoints: string[];
  reason: string;
}

export interface ProblematicExerciseDto {
  exerciseId: number;
  reason: string;
}

@Injectable()
export class AIEngineIntegration {
  private readonly logger = new Logger(AIEngineIntegration.name);
  private readonly baseURL: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.baseURL =
      this.configService.get<string>('AI_ENGINE_URL') ||
      'http://localhost:8000';
  }

  async getJointStressProfile(
    athleteId: number,
  ): Promise<JointStressProfileDto> {
    try {
      const { data } = await firstValueFrom(
        this.httpService.get<JointStressProfileDto>(
          `${this.baseURL}/api/injury-prevention/athlete/${athleteId}/joint-stress-profile`,
        ),
      );
      return data;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to fetch joint stress profile for athlete ${athleteId}: ${errorMessage}`,
      );
      // Handle gracefully - return empty profile if AI engine unavailable
      return { avoidJoints: [], reason: 'AI engine unavailable' };
    }
  }

  async getProblematicExercises(
    athleteId: number,
  ): Promise<ProblematicExerciseDto[]> {
    try {
      const { data } = await firstValueFrom(
        this.httpService.get<ProblematicExerciseDto[]>(
          `${this.baseURL}/api/form-quality/athlete/${athleteId}/problematic-exercises`,
        ),
      );
      return data;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to fetch problematic exercises for athlete ${athleteId}: ${errorMessage}`,
      );
      return [];
    }
  }

  async generatePrescription(
    intensityCategory: 'compound_heavy' | 'compound_moderate' | 'isolation',
    trainingType: 'strength' | 'hypertrophy' | 'hybrid',
    trainingPhase: 'accumulation' | 'intensification' | 'realization' | 'deload',
    weekInPhase: number,
    isPrimary: boolean = true,
  ): Promise<{
    target_rpe: number;
    target_rir: number;
    rest_period_seconds: number;
  }> {
    try {
      const { data } = await firstValueFrom(
        this.httpService.post<{
          target_rpe: number;
          target_rir: number;
          rest_period_seconds: number;
        }>(`${this.baseURL}/api/prescriptions/generate`, {
          intensity_category: intensityCategory,
          training_type: trainingType,
          training_phase: trainingPhase,
          week_in_phase: weekInPhase,
          is_primary: isPrimary,
        }),
      );
      return data;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to generate prescription: ${errorMessage}`,
      );
      throw error;
    }
  }
}

