import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { ExerciseController } from './exercise.controller';
import { ExerciseService } from './exercise.service';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';

@Module({
  imports: [HttpModule, ConfigModule],
  controllers: [ExerciseController],
  providers: [ExerciseService, AIEngineIntegration],
  exports: [ExerciseService],
})
export class ExerciseModule {}

