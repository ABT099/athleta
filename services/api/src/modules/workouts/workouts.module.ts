import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { WorkoutsController } from './workouts.controller';
import { WorkoutsService } from './workouts.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { MuscleImageIntegration } from '../../integrations/muscle-image.integration';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';

@Module({
  imports: [HttpModule, ConfigModule, ExerciseModule],
  controllers: [WorkoutsController],
  providers: [WorkoutsService, MuscleImageIntegration, AIEngineIntegration],
  exports: [WorkoutsService],
})
export class WorkoutsModule {}
