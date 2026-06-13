import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { ClientsModule, Transport } from '@nestjs/microservices';
import { join } from 'path';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import { ExerciseClientService } from './exercise-client.service';
import { ExerciseController } from './exercise.controller';

@Module({
  imports: [
    HttpModule,
    ConfigModule,
    ClientsModule.register([
      {
        name: 'EXERCISE_PACKAGE',
        transport: Transport.GRPC,
        options: {
          package: 'exercise.v1',
          protoPath: join(process.cwd(), 'proto/exercise/v1/exercise.proto'),
          url: process.env.EXERCISE_SERVICE_URL || 'localhost:50051',
          loader: {
            keepCase: false,
            enums: String,
            defaults: true,
            arrays: true,
            objects: true,
          },
        },
      },
    ]),
  ],
  controllers: [ExerciseController],
  providers: [ExerciseClientService, AIEngineIntegration],
  exports: [ExerciseClientService],
})
export class ExerciseModule {}
