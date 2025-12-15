import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { ExerciseService } from './exercise.service';
import { InferenceService } from './inference.service';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import { ClientsModule, Transport } from '@nestjs/microservices';
import { join } from 'path';
import { ExerciseController } from './exercise.controller';

@Module({
  imports: [
    HttpModule,
    ConfigModule,
    ClientsModule.register([
      {
        name: 'INFERENCE_PACKAGE',
        transport: Transport.GRPC,
        options: {
          package: 'inference',
          protoPath: join(__dirname, '../../../proto/inference.proto'),
          url: process.env.INFERENCE_SERVICE_URL || 'localhost:50051',
        },
      },
    ]),
  ],
  controllers: [ExerciseController],
  providers: [ExerciseService, InferenceService, AIEngineIntegration],
  exports: [ExerciseService],
})
export class ExerciseModule {}
