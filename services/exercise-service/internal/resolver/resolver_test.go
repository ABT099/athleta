package resolver_test

import (
	"testing"

	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/matcher"
	"github.com/athleta/exercise-service/internal/resolver"
)

func newResolver(t *testing.T) *resolver.Resolver {
	t.Helper()
	loader, err := config.NewLoader("../../config/exercises.json", "../../config/scoring_weights.json")
	if err != nil {
		t.Fatalf("config: %v", err)
	}
	t.Cleanup(func() { _ = loader.Close() })
	return resolver.New(matcher.NewMatcher(loader))
}

func TestResolveMatched(t *testing.T) {
	r := newResolver(t)
	cases := []struct {
		in, wantID string
	}{
		{"bench press", "bench_press"},
		{"bech press", "bench_press"}, // typo still resolves
		{"squat", "squat"},
		{"rdl", "romanian_deadlift"},
	}
	for _, c := range cases {
		out := r.Resolve(c.in)
		if !out.Matched {
			t.Errorf("Resolve(%q) not matched", c.in)
			continue
		}
		if out.VocabularyID != c.wantID {
			t.Errorf("Resolve(%q) id = %q, want %q", c.in, out.VocabularyID, c.wantID)
		}
		if out.Confidence <= 0 {
			t.Errorf("Resolve(%q) confidence = %v, want > 0", c.in, out.Confidence)
		}
	}
}

func TestResolveAmbiguousPicksPopular(t *testing.T) {
	r := newResolver(t)
	// "chest press" is shared by several push exercises; resolution policy
	// takes the highest-popularity candidate the ranker placed first.
	out := r.Resolve("chest press")
	if !out.Matched {
		t.Fatal("ambiguous name should still resolve to the popular interpretation")
	}
	if out.VocabularyID != "bench_press" {
		t.Errorf("ambiguous resolved to %q, want bench_press", out.VocabularyID)
	}
}

func TestResolveUnmatched(t *testing.T) {
	r := newResolver(t)
	for _, in := range []string{"asdfghjkl", "xyzzy qwerty", ""} {
		out := r.Resolve(in)
		if out.Matched {
			t.Errorf("Resolve(%q) matched %q, want unmatched", in, out.VocabularyID)
		}
	}
}
