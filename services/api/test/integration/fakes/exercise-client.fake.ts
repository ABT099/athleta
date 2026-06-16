import type {
  Exercise,
  InferredExercise,
  IntensityCategory,
  Substitution,
} from 'src/modules/exercise/exercise.types';

/**
 * Deterministic in-memory stand-in for {@link ExerciseClientService} (the gRPC
 * exercise-service client). Names map to stable ids within a process so that
 * inference → persistence → hydration round-trips line up like the real service.
 */
const nameToId = new Map<string, number>();
let nextId = 1000;

function idForName(name: string): number {
  const key = name.toLowerCase();
  if (!nameToId.has(key)) {
    nameToId.set(key, nextId++);
  }
  return nameToId.get(key)!;
}

function intensityForName(name: string): IntensityCategory {
  const n = name.toLowerCase();
  if (/(curl|raise|fly|lateral|extension|pushdown)/.test(n)) return 'isolation';
  if (/(squat|deadlift|bench|overhead press)/.test(n)) return 'compound_heavy';
  return 'compound_moderate';
}

function makeExercise(id: number, name: string): Exercise {
  return {
    id,
    name,
    movementPattern: 'push',
    exerciseType: 'compound',
    intensityCategory: intensityForName(name),
    attributes: {
      equipment: 'barbell',
      laterality: 'bilateral',
      angle: '',
      grip: '',
      tempo: '',
      forceVector: '',
    },
    muscles: [
      {
        name: 'chest',
        displayName: 'Chest',
        role: 'prime_mover',
        activationPercent: 80,
      },
    ],
    safety: { injuryRiskLevel: 1, complexityScore: 1, jointStressAreas: [] },
  };
}

export class FakeExerciseClient {
  async inferExercises(names: string[]): Promise<InferredExercise[]> {
    return names.map((name) => ({
      exercise: makeExercise(idForName(name), name),
      requestedName: name,
      resolution: 'matched' as const,
      confidence: 1,
    }));
  }

  async getExercises(ids: number[]): Promise<Exercise[]> {
    return ids.map((id) => makeExercise(id, `exercise-${id}`));
  }

  async getExercise(id: number): Promise<Exercise | null> {
    return makeExercise(id, `exercise-${id}`);
  }

  async findSubstitutions(): Promise<Substitution[]> {
    return [];
  }
}
