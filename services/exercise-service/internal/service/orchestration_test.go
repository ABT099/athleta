package service_test

import (
	"context"
	"testing"

	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/domain"
	"github.com/athleta/exercise-service/internal/matcher"
	"github.com/athleta/exercise-service/internal/memgraph"
	"github.com/athleta/exercise-service/internal/resolver"
	"github.com/athleta/exercise-service/internal/service"
)

// These tests drive the service through its public seam against the in-memory
// graph adapter — the orchestration logic (resolution, idempotent persistence,
// substitution) is exercised in milliseconds, no Neo4j required. The Neo4j
// adapter is pinned to the same behaviour by the integration suite.

func newSvc(t *testing.T) *service.Service {
	t.Helper()
	loader, err := config.NewLoader("../../config/exercises.json", "../../config/scoring_weights.json")
	if err != nil {
		t.Fatalf("config: %v", err)
	}
	t.Cleanup(func() { _ = loader.Close() })
	return service.New(memgraph.New(), resolver.New(matcher.NewMatcher(loader)), loader)
}

func TestInferMatchedAndInferred(t *testing.T) {
	svc := newSvc(t)
	ctx := context.Background()

	got, err := svc.InferExercises(ctx, []string{"bench press", "mystery shrimp lift"})
	if err != nil {
		t.Fatalf("infer: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("got %d results, want 2", len(got))
	}

	if got[0].Resolution != domain.ResolutionMatched {
		t.Errorf("known name resolution = %v, want matched", got[0].Resolution)
	}
	if got[0].Exercise.ID <= 0 {
		t.Errorf("matched exercise id = %d", got[0].Exercise.ID)
	}

	if got[1].Resolution != domain.ResolutionInferred {
		t.Errorf("unknown name resolution = %v, want inferred", got[1].Resolution)
	}
	if got[1].Confidence >= 1.0 {
		t.Errorf("inferred confidence = %v, want < 1.0", got[1].Confidence)
	}
}

func TestInferIsIdempotent(t *testing.T) {
	svc := newSvc(t)
	ctx := context.Background()

	first, _ := svc.InferExercises(ctx, []string{"squat"})
	second, _ := svc.InferExercises(ctx, []string{"squat"})
	if first[0].Exercise.ID != second[0].Exercise.ID {
		t.Errorf("re-infer changed id: %d -> %d", first[0].Exercise.ID, second[0].Exercise.ID)
	}
}

func TestGetExercisesRoundTrip(t *testing.T) {
	svc := newSvc(t)
	ctx := context.Background()

	inferred, _ := svc.InferExercises(ctx, []string{"deadlift"})
	id := inferred[0].Exercise.ID

	got, err := svc.GetExercises(ctx, []int32{id})
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if len(got) != 1 || got[0].ID != id {
		t.Fatalf("round trip failed: %+v", got)
	}
	if got[0].MovementPattern != domain.PatternHinge {
		t.Errorf("deadlift pattern = %q, want hinge", got[0].MovementPattern)
	}
}

func TestFindSubstitutionsOrchestration(t *testing.T) {
	svc := newSvc(t)
	ctx := context.Background()
	if _, err := svc.Seed(ctx); err != nil {
		t.Fatalf("seed: %v", err)
	}

	bench, _ := svc.InferExercises(ctx, []string{"barbell bench press"})
	benchID := bench[0].Exercise.ID

	subs, err := svc.FindSubstitutions(ctx, benchID, domain.SubstitutionFilters{Limit: 5})
	if err != nil {
		t.Fatalf("substitutions: %v", err)
	}
	if len(subs) == 0 {
		t.Fatal("expected substitutes for bench press")
	}
	for i := 1; i < len(subs); i++ {
		if subs[i-1].Score < subs[i].Score {
			t.Errorf("not score-ordered at %d", i)
		}
	}
	for _, s := range subs {
		if s.Exercise.ID == benchID {
			t.Error("original must not be its own substitute")
		}
	}

	// Excluding shoulder stress removes shoulder-stressing candidates.
	noShoulder, err := svc.FindSubstitutions(ctx, benchID, domain.SubstitutionFilters{
		ExcludeJointStress: []string{"shoulder"},
		Limit:              20,
	})
	if err != nil {
		t.Fatalf("substitutions w/ exclusion: %v", err)
	}
	for _, s := range noShoulder {
		for _, j := range s.Exercise.Safety.JointStressAreas {
			if j == "shoulder" {
				t.Errorf("candidate %q stresses excluded shoulder", s.Exercise.Name)
			}
		}
	}
}

func TestFindSubstitutionsUnknownExercise(t *testing.T) {
	svc := newSvc(t)
	if _, err := svc.FindSubstitutions(context.Background(), 999999, domain.SubstitutionFilters{}); err == nil {
		t.Error("expected error for unknown exercise id")
	}
}

func TestGetMusclesThroughService(t *testing.T) {
	svc := newSvc(t)
	muscles, err := svc.GetMuscles(context.Background(), []string{"biceps"})
	if err != nil {
		t.Fatalf("get muscles: %v", err)
	}
	if len(muscles) != 1 || muscles[0].Size != domain.SizeSmall || muscles[0].RecoveryHours != 48 {
		t.Errorf("biceps metadata wrong: %+v", muscles)
	}
}
