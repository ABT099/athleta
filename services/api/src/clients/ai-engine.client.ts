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
export class AIEngineClient {
  private readonly logger = new Logger(AIEngineClient.name);
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
}

