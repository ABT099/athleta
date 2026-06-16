/**
 * Event payloads exchanged with muscle-image over Kafka. Muscle names are the
 * raw api-domain names + roles; muscle-image owns the mapping to its own image
 * vocabulary and the rendering/colour concerns.
 */
export interface WorkoutDayCreatedEvent {
  workoutDayId: number;
  muscles: Array<{ name: string; role: string }>;
}

export interface MuscleImageGeneratedEvent {
  workoutDayId: number;
  url: string;
}
