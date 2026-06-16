import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { WorkoutsController } from './workouts.controller';
import { MuscleImageEventsController } from './muscle-image-events.controller';
import { WorkoutsService } from './workouts.service';
import { ExerciseModule } from '../exercise/exercise.module';
import { InternalModule } from '../internal/internal.module';
import { AthletesModule } from '../athletes/athletes.module';
import { AutoRegulationServiceIntegration } from '../../integrations/auto-regulation-service.integration';

@Module({
  imports: [
    HttpModule,
    ConfigModule,
    ExerciseModule,
    InternalModule,
    AthletesModule,
  ],
  controllers: [WorkoutsController, MuscleImageEventsController],
  providers: [WorkoutsService, AutoRegulationServiceIntegration],
  exports: [WorkoutsService],
})
export class WorkoutsModule {}
