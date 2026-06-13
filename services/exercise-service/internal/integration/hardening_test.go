//go:build integration

package integration

import (
	"testing"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	exercisev1 "github.com/athleta/exercise-service/gen/exercise/v1"
)

func TestInferEmptyBatch(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	resp, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: nil})
	if err != nil {
		t.Fatalf("empty batch errored: %v", err)
	}
	if len(resp.Exercises) != 0 {
		t.Errorf("empty batch returned %d results", len(resp.Exercises))
	}
}

func TestInferBlankNamesRejected(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	for _, names := range [][]string{
		{""},
		{"   "},
		{"\t\n"},
		{"bench press", ""}, // one bad name fails the whole request
	} {
		_, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: names})
		if status.Code(err) != codes.InvalidArgument {
			t.Errorf("names %q: code = %v, want InvalidArgument", names, status.Code(err))
		}
	}

	// Blank input must not persist a junk empty-named exercise.
	muscles, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{})
	if err != nil {
		t.Fatalf("get muscles: %v", err)
	}
	if len(muscles.Muscles) != 20 {
		t.Errorf("muscle count = %d, want 20 (no junk nodes from blank input)", len(muscles.Muscles))
	}
}

func TestInferDuplicateNamesShareID(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	resp, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{
		Names: []string{"squat", "squat"},
	})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}
	if len(resp.Exercises) != 2 {
		t.Fatalf("got %d results, want 2", len(resp.Exercises))
	}
	if resp.Exercises[0].Exercise.Id != resp.Exercises[1].Exercise.Id {
		t.Errorf("duplicate names got different ids: %d vs %d",
			resp.Exercises[0].Exercise.Id, resp.Exercises[1].Exercise.Id)
	}
}

func TestInferCaseAndTypoTolerance(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	resp, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{
		Names: []string{"bench press", "BENCH PRESS", "Bench Press", "bech press"},
	})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}

	// All four (incl. the typo) resolve to the same matched exercise + id.
	want := resp.Exercises[0].Exercise.Id
	for i, r := range resp.Exercises {
		if r.Resolution != exercisev1.InferredExercise_RESOLUTION_MATCHED {
			t.Errorf("%q resolution = %v, want MATCHED", r.RequestedName, r.Resolution)
		}
		if r.Exercise.Id != want {
			t.Errorf("variant %d (%q) id = %d, want %d", i, r.RequestedName, r.Exercise.Id, want)
		}
	}
}

func TestInferInjectionNameIsInertData(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	// A Cypher-injection-shaped name must be treated as literal data (queries
	// are parameterized), not executed. Service must not corrupt the graph.
	evil := `x") DETACH DELETE (n) //`
	resp, err := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: []string{evil}})
	if err != nil {
		t.Fatalf("infer injection name: %v", err)
	}
	if resp.Exercises[0].Exercise.Id <= 0 {
		t.Error("injection-shaped name should persist as ordinary inferred exercise")
	}

	// Taxonomy intact -> nothing was deleted.
	muscles, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{})
	if err != nil {
		t.Fatalf("get muscles: %v", err)
	}
	if len(muscles.Muscles) != 20 {
		t.Errorf("muscle count = %d, want 20 (graph untouched by injection)", len(muscles.Muscles))
	}
}

func TestGetMusclesUnknownNamesOmitted(t *testing.T) {
	client, _ := startServer(t)
	ctx := ctxT(t)

	resp, err := client.GetMuscles(ctx, &exercisev1.GetMusclesRequest{
		Names: []string{"biceps", "not_a_real_muscle", "triceps"},
	})
	if err != nil {
		t.Fatalf("get muscles: %v", err)
	}
	if len(resp.Muscles) != 2 {
		t.Fatalf("got %d muscles, want 2 (unknown omitted)", len(resp.Muscles))
	}
}

func TestFindSubstitutionsZeroLimitDefaults(t *testing.T) {
	client, svc := startServer(t)
	ctx := ctxT(t)
	if _, err := svc.Seed(ctx); err != nil {
		t.Fatalf("seed: %v", err)
	}

	infer, _ := client.InferExercises(ctx, &exercisev1.InferExercisesRequest{Names: []string{"barbell bench press"}})
	id := infer.Exercises[0].Exercise.Id

	resp, err := client.FindSubstitutions(ctx, &exercisev1.FindSubstitutionsRequest{ExerciseId: id, Limit: 0})
	if err != nil {
		t.Fatalf("zero-limit substitutions: %v", err)
	}
	if len(resp.Substitutions) == 0 || len(resp.Substitutions) > 5 {
		t.Errorf("zero limit returned %d, want default-capped (1..5)", len(resp.Substitutions))
	}
}
