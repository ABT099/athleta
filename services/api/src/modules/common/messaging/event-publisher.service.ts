import { Inject, Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ClientKafka } from '@nestjs/microservices';
import {
  EVENTS_KAFKA_CLIENT,
  WORKOUT_DAY_CREATED_TOPIC,
} from './messaging.constants';
import { WorkoutDayCreatedEvent } from './events.types';

/**
 * Thin publisher over the Kafka producer client. Keyed by workoutDayId so all
 * events for a given day land on the same partition (ordered per day).
 */
@Injectable()
export class EventPublisher implements OnModuleInit {
  private readonly logger = new Logger(EventPublisher.name);

  constructor(
    @Inject(EVENTS_KAFKA_CLIENT) private readonly client: ClientKafka,
  ) {}

  async onModuleInit(): Promise<void> {
    await this.client.connect();
  }

  publishWorkoutDayCreated(event: WorkoutDayCreatedEvent): void {
    this.client.emit(WORKOUT_DAY_CREATED_TOPIC, {
      key: String(event.workoutDayId),
      value: event,
    });
    this.logger.log(
      `Published ${WORKOUT_DAY_CREATED_TOPIC} for workout day ${event.workoutDayId}`,
    );
  }
}
