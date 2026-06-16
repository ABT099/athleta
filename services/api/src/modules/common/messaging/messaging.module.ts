import { Global, Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { ClientsModule, Transport } from '@nestjs/microservices';
import { EVENTS_KAFKA_CLIENT } from './messaging.constants';
import { EventPublisher } from './event-publisher.service';

/**
 * Kafka producer wiring. Registers the `EVENTS_KAFKA` client used to publish
 * domain events (mirrors the gRPC `ClientsModule.register` pattern in
 * exercise.module.ts). Marked global so any module can publish without
 * re-importing. The matching consumer side is connected in `main.ts` as a
 * hybrid microservice.
 */
@Global()
@Module({
  imports: [
    ClientsModule.registerAsync([
      {
        name: EVENTS_KAFKA_CLIENT,
        imports: [ConfigModule],
        inject: [ConfigService],
        useFactory: (config: ConfigService) => ({
          transport: Transport.KAFKA,
          options: {
            client: {
              clientId: 'athleta-api',
              brokers: (
                config.get<string>('KAFKA_BROKERS') || 'localhost:9092'
              ).split(','),
            },
            producer: {
              allowAutoTopicCreation: true,
            },
            // ClientKafka always spins up a consumer; this group is only used
            // for the producer client's internal bookkeeping (we emit events).
            consumer: {
              groupId: 'api-producer',
            },
          },
        }),
      },
    ]),
  ],
  providers: [EventPublisher],
  exports: [EventPublisher],
})
export class MessagingModule {}
