import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';

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

  getImage(builder: MuscleImageBuilder) {}
}

type MuscleGroup =
  | 'all'
  | 'all_lower'
  | 'all_upper'
  | 'abductors'
  | 'abs'
  | 'adductors'
  | 'back'
  | 'back_lower'
  | 'back_upper'
  | 'biceps'
  | 'calfs'
  | 'chest'
  | 'core'
  | 'core_lower'
  | 'core_upper'
  | 'forearms'
  | 'gluteus'
  | 'hamstring'
  | 'latissimus'
  | 'legs'
  | 'neck'
  | 'quadriceps'
  | 'shoulders'
  | 'shoulders_back'
  | 'shoulders_front'
  | 'triceps';

export class MuscleImageBuilder {
  private primaryMuscles: MuscleGroup[] = [];
  private secondaryMuscles: MuscleGroup[] = [];
  withChest(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('chest');
    } else {
      this.secondaryMuscles.push('chest');
    }
  }

  withShouldersFront(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('shoulders_front');
    } else {
      this.secondaryMuscles.push('shoulders_front');
    }
  }

  withShouldersBack(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('shoulders_back');
    } else {
      this.secondaryMuscles.push('shoulders_back');
    }
  }

  withShoulders(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('shoulders');
    } else {
      this.secondaryMuscles.push('shoulders');
    }
  }

  withBiceps(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('biceps');
    } else {
      this.secondaryMuscles.push('biceps');
    }
  }

  withTriceps(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('triceps');
    } else {
      this.secondaryMuscles.push('triceps');
    }
  }

  withForearms(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('forearms');
    } else {
      this.secondaryMuscles.push('forearms');
    }
  }

  withLats(activationPercentage: number) {
    if (this.isPrimary(activationPercentage)) {
      this.primaryMuscles.push('latissimus');
    } else {
      this.secondaryMuscles.push('latissimus');
    }
  }

  build() {
    return {
      primaryMuscles: this.primaryMuscles,
      secondaryMuscles: this.secondaryMuscles,
    };
  }

  private isPrimary(activationPercentage: number) {
    return activationPercentage > 0.7;
  }
}
