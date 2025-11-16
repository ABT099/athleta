import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { ExerciseController } from './exercise.controller';
import { ExerciseSubstitutionService } from './exercise-substitution.service';
import { AIEngineClient } from '../../clients/ai-engine.client';

@Module({
  imports: [HttpModule, ConfigModule],
  controllers: [ExerciseController],
  providers: [ExerciseSubstitutionService, AIEngineClient],
  exports: [],
})
export class ExerciseModule {}

