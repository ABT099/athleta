import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { WorkoutsController } from './workouts.controller';
import { WorkoutsService } from './workouts.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { InternalModule } from '../internal/internal.module';
import { MuscleImageIntegration } from '../../integrations/muscle-image.integration';
import { AutoRegulationServiceIntegration } from '../../integrations/auto-regulation-service.integration';

@Module({
  imports: [HttpModule, ConfigModule, ExerciseModule, InternalModule],
  controllers: [WorkoutsController],
  providers: [WorkoutsService, MuscleImageIntegration, AutoRegulationServiceIntegration],
  exports: [WorkoutsService],
})
export class WorkoutsModule {}
