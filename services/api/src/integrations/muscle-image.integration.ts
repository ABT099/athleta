import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import { MuscleImageResponse } from './integrations.types';

@Injectable()
export class MuscleImageIntegration {
  private readonly logger = new Logger(MuscleImageIntegration.name);
  private readonly baseURL: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.baseURL =
      this.configService.get<string>('MUSCLE_IMAGE_URL') ||
      'http://localhost:8081';
  }

  /**
   * Map database muscle names to muscle-image service names
   */
  private mapMuscleNameToImageService(dbMuscleName: string): string | null {
    const mapping: Record<string, string> = {
      // Chest - map all chest variations to generic 'chest'
      upper_chest: 'chest',
      mid_chest: 'chest',
      lower_chest: 'chest',

      // Back
      lats: 'latissimus',
      upper_traps: 'back_upper',
      mid_back: 'back',
      lower_traps: 'back_lower',

      // Shoulders
      anterior_delt: 'shoulders_front',
      lateral_delt: 'shoulders',
      posterior_delt: 'shoulders_back',

      // Arms
      biceps: 'biceps',
      triceps: 'triceps',
      forearms: 'forearms',

      // Legs
      quadriceps: 'quadriceps',
      hamstrings: 'hamstring',
      glutes: 'gluteus',
      hip_flexors: 'core_lower', // No direct match, use core_lower
      calves: 'calfs',

      // Core
      abs: 'abs',
      erector_spinae: 'back_lower', // Lower back muscles
    };

    const mapped = mapping[dbMuscleName];
    if (!mapped) {
      this.logger.warn(
        `Unknown muscle name: ${dbMuscleName}, skipping in image generation`,
      );
      return null;
    }
    return mapped;
  }

  async generateAndSaveImage(
    workoutDayId: number,
    musclesWithRoles: Array<{ name: string; role: string }>,
  ): Promise<string> {
    try {
      // Map database muscle names to muscle-image service names
      const mappedMuscles = musclesWithRoles.map((m) => ({
        name: this.mapMuscleNameToImageService(m.name),
        role: m.role,
      }));

      // Separate muscles by role and remove duplicates
      const primaryMuscles = [
        ...new Set(
          mappedMuscles
            .filter((m) => m.role === 'prime_mover' && m.name !== null)
            .map((m) => m.name as string),
        ),
      ];
      const secondaryMuscles = [
        ...new Set(
          mappedMuscles
            .filter(
              (m) =>
                (m.role === 'synergist' || m.role === 'stabilizer') &&
                m.name !== null,
            )
            .map((m) => m.name as string),
        ),
      ];

      // Check if we have any valid muscles
      const allMuscles = [...primaryMuscles, ...secondaryMuscles];
      if (allMuscles.length === 0) {
        this.logger.warn(
          `No valid muscles found for workout day ${workoutDayId}, skipping image generation`,
        );
        throw new Error(
          `No valid muscles found for workout day ${workoutDayId}`,
        );
      }

      // Call PHP service - it handles generation and R2 upload
      this.logger.log(
        `Requesting muscle image generation for workout day ${workoutDayId}`,
      );
      const response = await firstValueFrom(
        this.httpService.post<MuscleImageResponse>(
          `${this.baseURL}/generateAndStore`,
          {
            workoutDayId,
            primaryMuscleGroups: primaryMuscles.join(','),
            secondaryMuscleGroups: secondaryMuscles.join(','),
            primaryColor: '255,89,94',
            secondaryColor: '138,201,38',
          },
          {
            headers: {
              'Content-Type': 'application/json',
            },
          },
        ),
      );

      if (!response.data || !response.data.url) {
        throw new Error('Invalid response from muscle image service');
      }

      this.logger.log(
        `Successfully generated muscle image: ${response.data.url}`,
      );
      return response.data.url;
    } catch (error) {
      this.logger.error(
        `Failed to generate muscle image for workout day ${workoutDayId}:`,
        error,
      );
      throw error;
    }
  }
}
