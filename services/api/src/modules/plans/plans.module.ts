import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { PlansController } from './plans.controller';
import { PlansService } from './plans.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { WorkoutsModule } from '../workouts/workouts.module';
import { AthletesModule } from '../athletes/athletes.module';
import { AutoRegulationServiceIntegration } from '../../integrations/auto-regulation-service.integration';

@Module({
  imports: [
    HttpModule,
    ConfigModule,
    ExerciseModule,
    WorkoutsModule,
    AthletesModule,
  ],
  controllers: [PlansController],
  providers: [PlansService, AutoRegulationServiceIntegration],
  exports: [PlansService],
})
export class PlansModule {}
