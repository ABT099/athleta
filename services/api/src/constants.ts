export enum Gender {
  MALE = 'male',
  FEMALE = 'female',
}

export enum TrainingExperience {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced',
}

export enum OAuthProvider {
  GOOGLE = 'google',
  APPLE = 'apple',
}

export enum WeightUnit {
  KG = 'kg',
  LBS = 'lbs',
}

export enum TrainingType {
  HYPERTRPHY = 'hypertrophy',
  STRENGTH = 'strength',
  HYBRID = 'hybrid',
}

export enum PeriodizationModel {
  LINEAR = 'linear',
  UNDULATING = 'undulating',
  BLOCK = 'block',
}

export enum DayOfWeek {
  MONDAY = 0,
  TUESDAY = 1,
  WEDNESDAY = 2,
  THURSDAY = 3,
  FRIDAY = 4,
  SATURDAY = 5,
  SUNDAY = 6,
}

/**
 * Converts JavaScript's Date.getDay() value to DayOfWeek enum.
 * JavaScript: 0=Sunday, 1=Monday, ..., 6=Saturday
 * DayOfWeek: 0=Monday, 1=Tuesday, ..., 6=Sunday
 */
export function jsDayToDayOfWeek(jsDay: number): DayOfWeek {
  // Convert: 0 (Sun) -> 6, 1 (Mon) -> 0, 2 (Tue) -> 1, ..., 6 (Sat) -> 5
  return jsDay === 0 ? DayOfWeek.SUNDAY : ((jsDay - 1) as DayOfWeek);
}
