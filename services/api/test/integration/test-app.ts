import { Test } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { MicroserviceOptions, Transport } from '@nestjs/microservices';
import { AppModule } from 'src/app.module';
import { AllExceptionsFilter } from 'src/filters/http-exception.filter';
import { API_CONSUMER_GROUP } from 'src/modules/common/messaging/messaging.constants';
import { ExerciseClientService } from 'src/modules/exercise/exercise-client.service';
import { AutoRegulationServiceIntegration } from 'src/integrations/auto-regulation-service.integration';
import {
  DRIZZLE,
  type DrizzleDB,
} from 'src/modules/common/database/database.provider';
import { FakeExerciseClient } from './fakes/exercise-client.fake';
import { FakeAutoReg } from './fakes/auto-reg.fake';

export interface IntegrationTestApp {
  app: INestApplication;
  db: DrizzleDB;
  autoReg: FakeAutoReg;
}

/**
 * Boot the full AppModule against the Testcontainers Postgres + Kafka, mirroring
 * `main.ts` (global pipe/filter + hybrid Kafka consumer) so the real guards,
 * Drizzle layer and Kafka publish/consume paths are exercised. Only the gRPC and
 * auto-regulation collaborators are replaced with deterministic fakes.
 */
export async function createTestApp(): Promise<IntegrationTestApp> {
  const autoReg = new FakeAutoReg();

  const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
    .overrideProvider(ExerciseClientService)
    .useValue(new FakeExerciseClient())
    .overrideProvider(AutoRegulationServiceIntegration)
    .useValue(autoReg)
    .compile();

  const app = moduleRef.createNestApplication();
  app.useGlobalFilters(new AllExceptionsFilter());
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: { enableImplicitConversion: true },
    }),
  );

  app.connectMicroservice<MicroserviceOptions>({
    transport: Transport.KAFKA,
    options: {
      client: {
        clientId: 'athleta-api-test',
        brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
      },
      consumer: { groupId: API_CONSUMER_GROUP },
    },
  });

  await app.startAllMicroservices();
  await app.init();

  const db = app.get<DrizzleDB>(DRIZZLE);
  return { app, db, autoReg };
}

/**
 * Close the app and end the underlying pg pool. The Drizzle provider owns the
 * pool directly (no Nest lifecycle hook), so without this the idle connections
 * outlive the app and error when the Postgres container is torn down.
 */
export async function closeTestApp(testApp: {
  app: INestApplication;
  db: DrizzleDB;
}): Promise<void> {
  await testApp.app.close();
  const pool = (testApp.db as unknown as { $client?: { end(): Promise<void> } })
    .$client;
  await pool?.end();
}
