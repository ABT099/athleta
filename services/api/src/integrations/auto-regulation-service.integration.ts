import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import { ClsService } from 'nestjs-cls';
import { AxiosRequestHeaders } from 'axios';
import {
  AnalyzeSessionPayload,
  AnalyzeSessionResponse,
  JointStressProfileDto,
  PrescriptionRequestDto,
  PrescriptionResponseDto,
} from './integrations.types';

@Injectable()
export class AutoRegulationServiceIntegration {
  private readonly logger = new Logger(AutoRegulationServiceIntegration.name);
  private readonly baseURL: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    private readonly cls: ClsService,
  ) {
    this.baseURL =
      this.configService.get<string>('AUTO_REGULATION_SERVICE_URL') ||
      'http://localhost:8000';

    this.httpService.axiosRef.interceptors.request.use((config) => {
      const authToken = this.cls.get<string>('authToken');
      if (authToken && config.url?.includes(this.baseURL)) {
        if (!config.headers) {
          config.headers = {} as AxiosRequestHeaders;
        }
        config.headers.Authorization = authToken;
      }
      return config;
    });
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
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to fetch joint stress profile for athlete ${athleteId}: ${errorMessage}`,
      );
      // Handle gracefully - return empty profile if auto-regulation service unavailable
      return { avoidJoints: [], reason: 'Auto-regulation service unavailable' };
    }
  }

  async generatePrescription(
    intensityCategory: PrescriptionRequestDto['intensityCategory'],
    trainingType: PrescriptionRequestDto['trainingType'],
    trainingPhase: PrescriptionRequestDto['trainingPhase'],
    weekInPhase: number,
    isPrimary: boolean = true,
  ): Promise<PrescriptionResponseDto> {
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
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      this.logger.warn(`Failed to generate prescription: ${errorMessage}`);
      throw error;
    }
  }

  async generateBatchPrescriptions(
    prescriptions: PrescriptionRequestDto[],
  ): Promise<PrescriptionResponseDto[]> {
    try {
      const { data } = await firstValueFrom(
        this.httpService.post<{
          prescriptions: Array<{
            target_rpe: number;
            target_rir: number;
            rest_period_seconds: number;
          }>;
        }>(`${this.baseURL}/api/prescriptions/generate-batch`, {
          prescriptions: prescriptions.map((p) => ({
            intensity_category: p.intensityCategory,
            training_type: p.trainingType,
            training_phase: p.trainingPhase,
            week_in_phase: p.weekInPhase,
            is_primary: p.isPrimary,
          })),
        }),
      );
      return data.prescriptions;
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to generate batch prescriptions: ${errorMessage}`,
      );
      throw error;
    }
  }

  /**
   * Push a just-logged session (athlete + plan + session + sets + recovery) to
   * auto-regulation for analysis. auto-regulation computes over the pushed
   * context — making zero calls back to api on this path — and returns the
   * adjustments + write-backs (PRs to persist, current calibration factor).
   */
  async analyzeSession(
    payload: AnalyzeSessionPayload,
  ): Promise<AnalyzeSessionResponse> {
    const { data } = await firstValueFrom(
      this.httpService.post<AnalyzeSessionResponse>(
        `${this.baseURL}/api/analysis/sessions`,
        payload,
      ),
    );
    return data;
  }
}
