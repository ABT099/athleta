//go:build integration

package integration

import (
	"testing"

	exercisev1 "github.com/athleta/exercise-service/gen/exercise/v1"
)

// TestJourneyPlanCreation walks the flow the api drives when a user creates a
// workout plan: batch-infer raw names, reuse the returned IDs to hydrate
// exercises, find a substitute for one, pull muscle metadata for imaging, then
// re-infer the same names and confirm IDs are stable (the "already exists"
// path in the api's batch upsert).
func TestJourneyPlanCreation(t *testing.T) {
	client, svc := startServer(t)
	ctx := ctxT(t)

	// Vocabulary seeded so substitutions have a rich candidate pool.
	if _, err := svc.Seed(ctx); err != nil {
		t.Fatalf("seed: %v", err)
	}

	names := []string{"barbell bench press", "barbell back squat", "mystery shrimp lift"}

	// Step 1: batch infer.
	infer, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: names})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}
	if len(infer.Exercises) != len(names) {
		t.Fatalf("got %d results, want %d (one per name)", len(infer.Exercises), len(names))
	}

	idByName := map[string]int32{}
	var allIDs []int32
	for i, r := range infer.Exercises {
		if r.RequestedName != names[i] {
			t.Errorf("result %d name = %q, want %q (order broken)", i, r.RequestedName, names[i])
		}
		if r.Exercise.Id <= 0 {
			t.Fatalf("%q got non-positive id", r.RequestedName)
		}
		if r.Exercise.IntensityCategory == "" {
			t.Errorf("%q missing intensity_category (drives is_primary in api)", r.RequestedName)
		}
		idByName[r.RequestedName] = r.Exercise.Id
		allIDs = append(allIDs, r.Exercise.Id)
	}

	// Known names matched, unknown inferred.
	if infer.Exercises[0].Resolution != exercisev1.InferredExercise_RESOLUTION_MATCHED {
		t.Errorf("bench resolution = %v, want MATCHED", infer.Exercises[0].Resolution)
	}
	if infer.Exercises[2].Resolution != exercisev1.InferredExercise_RESOLUTION_INFERRED {
		t.Errorf("mystery resolution = %v, want INFERRED", infer.Exercises[2].Resolution)
	}

	// Step 2: hydrate all IDs in one call (api stores IDs, reads back later).
	hydrated, err := client.GetExercises(ctx, &exercisev1.GetExercisesRequest{Ids: allIDs})
	if err != nil {
		t.Fatalf("get exercises: %v", err)
	}
	if len(hydrated.Exercises) != len(allIDs) {
		t.Fatalf("hydrated %d, want %d", len(hydrated.Exercises), len(allIDs))
	}
	gotByID := map[int32]*exercisev1.Exercise{}
	for _, e := range hydrated.Exercises {
		gotByID[e.Id] = e
	}
	for name, id := range idByName {
		if gotByID[id] == nil {
			t.Errorf("hydration dropped %q (id %d)", name, id)
		}
	}

	// Step 3: substitute the bench press.
	benchID := idByName["barbell bench press"]
	subs, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{ExerciseId: benchID, Limit: 5})
	if err != nil {
		t.Fatalf("substitutions: %v", err)
	}
	if len(subs.Substitutions) == 0 {
		t.Fatal("bench press should have substitutes")
	}
	top := subs.Substitutions[0]
	if top.Exercise.Id == benchID {
		t.Error("substitute must differ from original")
	}
	if top.Score <= 0 {
		t.Errorf("top substitute score = %v, want > 0", top.Score)
	}
	if top.Reason == "" {
		t.Error("substitute missing human reason")
	}

	// Step 4: muscle metadata for the bench press (api -> muscle-image flow).
	bench := gotByID[benchID]
	if len(bench.Muscles) == 0 {
		t.Fatal("bench has no muscle targets")
	}
	muscleNames := make([]string, 0, len(bench.Muscles))
	for _, m := range bench.Muscles {
		muscleNames = append(muscleNames, m.Name)
	}
	muscles, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{Names: muscleNames})
	if err != nil {
		t.Fatalf("get muscles: %v", err)
	}
	if len(muscles.Muscles) != len(muscleNames) {
		t.Fatalf("muscle metadata count = %d, want %d", len(muscles.Muscles), len(muscleNames))
	}
	for _, m := range muscles.Muscles {
		if m.RecoveryHours <= 0 || m.Size == exercisev1.Muscle_SIZE_UNSPECIFIED {
			t.Errorf("muscle %q missing size/recovery: %+v", m.Name, m)
		}
	}

	// Step 5: re-infer same names -> identical IDs (idempotent persistence).
	again, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: names})
	if err != nil {
		t.Fatalf("re-infer: %v", err)
	}
	for i, r := range again.Exercises {
		if r.Exercise.Id != idByName[names[i]] {
			t.Errorf("re-infer %q id %d != first %d (not idempotent)", names[i], r.Exercise.Id, idByName[names[i]])
		}
	}
}

// TestJourneyInferredExerciseLifecycle proves an exercise that never matched
// the vocabulary is still a first-class citizen: persisted, retrievable, and
// usable in substitution queries without error.
func TestJourneyInferredExerciseLifecycle(t *testing.T) {
	client, svc := startServer(t)
	ctx := ctxT(t)
	if _, err := svc.Seed(ctx); err != nil {
		t.Fatalf("seed: %v", err)
	}

	// An unknown but parseable name: "incline" + "dumbbell" + "press" attributes.
	infer, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{
		Names: []string{"weird incline dumbbell thing press"},
	})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}
	r := infer.Exercises[0]
	if r.Resolution != exercisev1.InferredExercise_RESOLUTION_INFERRED {
		t.Fatalf("resolution = %v, want INFERRED", r.Resolution)
	}
	id := r.Exercise.Id
	if id <= 0 {
		t.Fatal("inferred exercise not persisted")
	}
	// Attributes parsed out even without a vocab match.
	if r.Exercise.Attributes.Equipment != "dumbbell" || r.Exercise.Attributes.Angle != "incline" {
		t.Errorf("inferred attributes wrong: %+v", r.Exercise.Attributes)
	}

	// Retrievable by ID.
	got, err := client.GetExercises(ctx, &exercisev1.GetExercisesRequest{Ids: []int32{id}})
	if err != nil || len(got.Exercises) != 1 || got.Exercises[0].Id != id {
		t.Fatalf("inferred exercise not retrievable: %v %+v", err, got)
	}

	// Substitution query runs without error (push exercise shares chest/triceps).
	subs, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{ExerciseId: id, Limit: 5})
	if err != nil {
		t.Fatalf("substitutions on inferred exercise errored: %v", err)
	}
	if len(subs.Substitutions) == 0 {
		t.Error("inferred push exercise should find muscle-overlapping substitutes")
	}
}
