import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { PlansController } from './plans.controller';
import { PlansService } from './plans.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { WorkoutsModule } from '../workouts/workouts.module';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';

@Module({
  imports: [HttpModule, ConfigModule, ExerciseModule, WorkoutsModule],
  controllers: [PlansController],
  providers: [PlansService, AIEngineIntegration],
  exports: [PlansService],
})
export class PlansModule {}
