import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { PlansController } from './plans.controller';
import { PlansService } from './plans.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { MuscleImageIntegration } from '../../integrations/muscle-image.integration';

@Module({
  imports: [HttpModule, ConfigModule, ExerciseModule],
  controllers: [PlansController],
  providers: [PlansService, MuscleImageIntegration],
  exports: [PlansService],
})
export class PlansModule {}
