import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { DatabaseModule } from './modules/database/database.module';
import { ExerciseModule } from './modules/exercise/exercise.module';
import { WorkoutsModule } from './modules/workouts/workouts.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    DatabaseModule,
    ExerciseModule,
    WorkoutsModule,
  ],
})
export class AppModule {}
