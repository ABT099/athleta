/** DI token for the Kafka producer client (see {@link MessagingModule}). */
export const EVENTS_KAFKA_CLIENT = 'EVENTS_KAFKA';

/** Consumer group the api uses when reading events back off Kafka. */
export const API_CONSUMER_GROUP = 'api-muscle-image';

// --- Topics -----------------------------------------------------------------

/** Emitted by the api after a workout day is committed; consumed by muscle-image. */
export const WORKOUT_DAY_CREATED_TOPIC = 'athleta.workout-day.created';

/** Emitted by muscle-image once an image is rendered/located; consumed by the api. */
export const MUSCLE_IMAGE_GENERATED_TOPIC = 'athleta.muscle-image.generated';
