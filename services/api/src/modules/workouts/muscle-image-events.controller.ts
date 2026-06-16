import { Controller, Logger } from '@nestjs/common';
import { EventPattern, Payload } from '@nestjs/microservices';
import { WorkoutsService } from './workouts.service';
import { MUSCLE_IMAGE_GENERATED_TOPIC } from '../common/messaging/messaging.constants';
import type { MuscleImageGeneratedEvent } from '../common/messaging/events.types';

/**
 * Kafka consumer for results coming back from muscle-image. Connected as a
 * hybrid microservice in `main.ts`; persists the rendered image URL onto the
 * workout day.
 */
@Controller()
export class MuscleImageEventsController {
  private readonly logger = new Logger(MuscleImageEventsController.name);

  constructor(private readonly workoutsService: WorkoutsService) {}

  @EventPattern(MUSCLE_IMAGE_GENERATED_TOPIC)
  async handleMuscleImageGenerated(
    @Payload() event: MuscleImageGeneratedEvent,
  ): Promise<void> {
    if (!event?.workoutDayId || !event?.url) {
      this.logger.warn(
        `Ignoring malformed ${MUSCLE_IMAGE_GENERATED_TOPIC} event: ${JSON.stringify(event)}`,
      );
      return;
    }

    await this.workoutsService.setMuscleImageUrl(event.workoutDayId, event.url);
  }
}
