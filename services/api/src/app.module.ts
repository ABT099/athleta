import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { DatabaseModule } from './modules/database/database.module';
import { ExerciseModule } from './modules/exercise/exercise.module';
import { WorkoutsModule } from './modules/workouts/workouts.module';
import { AuthModule } from './modules/auth/auth.module';
import { PlansModule } from './modules/plans/plans.module';
import { APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core';
import { JwtAuthGuard } from './modules/auth/guards/jwt-auth.guard';
import { EmailModule } from './modules/common/email/email.module';
import { AppController } from './app.controller';
import { ClsModule } from 'nestjs-cls';
import { AIEngineAuthInterceptor } from './integrations/ai-engine.interceptor';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    ClsModule.forRoot({
      global: true,
      middleware: { mount: true },
    }),
    DatabaseModule,
    ExerciseModule,
    WorkoutsModule,
    AuthModule,
    EmailModule,
    PlansModule,
  ],
  controllers: [AppController],
  providers: [
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: AIEngineAuthInterceptor,
    },
  ],
})
export class AppModule {}
