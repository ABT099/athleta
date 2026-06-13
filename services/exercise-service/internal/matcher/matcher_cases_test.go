package matcher

import (
	"path/filepath"
	"testing"

	"github.com/athleta/exercise-service/internal/config"
)

func newTestMatcher(t *testing.T) *Matcher {
	t.Helper()
	cfgDir := "../../config"
	loader, err := config.NewLoader(
		filepath.Join(cfgDir, "exercises.json"),
		filepath.Join(cfgDir, "scoring_weights.json"),
	)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	t.Cleanup(func() { _ = loader.Close() })
	return NewMatcher(loader)
}

func resultName(rt ResultType) string {
	switch rt {
	case ResultTypeMatch:
		return "MATCH"
	case ResultTypeAmbiguous:
		return "AMBIGUOUS"
	case ResultTypeLowConfidence:
		return "LOW_CONFIDENCE"
	default:
		return "NO_MATCH"
	}
}

// TestMatchTable is the golden set as an explicit Go table (mirrors
// testdata/golden_set.csv) plus extra coverage.
func TestMatchTable(t *testing.T) {
	m := newTestMatcher(t)

	cases := []struct {
		input    string
		wantType ResultType
		wantID   string // checked only for MATCH
	}{
		{"bench press", ResultTypeMatch, "bench_press"},
		{"bech press", ResultTypeMatch, "bench_press"},          // typo
		{"press bench flat", ResultTypeMatch, "bench_press"},    // word order
		{"bb bench", ResultTypeMatch, "bench_press"},            // abbreviation
		{"i did some bench press", ResultTypeMatch, "bench_press"}, // conversational
		{"skull crushers", ResultTypeMatch, "lying_tricep_extension"},
		{"squat", ResultTypeMatch, "squat"},
		{"deadlift", ResultTypeMatch, "deadlift"},
		{"pull up", ResultTypeMatch, "pull_up"},
		{"overhead press", ResultTypeMatch, "overhead_press"},
		{"rdl", ResultTypeMatch, "romanian_deadlift"},
		{"lat pulldown", ResultTypeMatch, "lat_pulldown"},
		{"lateral raises", ResultTypeMatch, "lateral_raise"},
		{"leg curls", ResultTypeMatch, "leg_curl"},
		{"farmers walk", ResultTypeMatch, "farmers_carry"},
		{"chin up", ResultTypeMatch, "chin_up"},
		{"working on squats", ResultTypeMatch, "squat"},
		{"i'm doing deadlifts", ResultTypeMatch, "deadlift"},
	}

	for _, c := range cases {
		t.Run(c.input, func(t *testing.T) {
			got := m.Match(c.input)
			if got.ResultType != c.wantType {
				t.Fatalf("type = %s, want %s (conf %.2f)", resultName(got.ResultType), resultName(c.wantType), got.Confidence)
			}
			if c.wantType == ResultTypeMatch {
				if got.TopCandidate == nil {
					t.Fatal("MATCH but TopCandidate nil")
				}
				if got.TopCandidate.ExerciseID != c.wantID {
					t.Fatalf("id = %q, want %q", got.TopCandidate.ExerciseID, c.wantID)
				}
			}
		})
	}
}

func TestMatchNegatives(t *testing.T) {
	m := newTestMatcher(t)

	for _, in := range []string{"asdfghjkl", "xyzzy qwerty", "", "   "} {
		got := m.Match(in)
		if got.ResultType != ResultTypeNoMatch {
			t.Errorf("Match(%q) = %s, want NO_MATCH", in, resultName(got.ResultType))
		}
		if got.TopCandidate != nil {
			t.Errorf("Match(%q) returned a candidate on no match", in)
		}
	}
}

func TestMatchAmbiguousNeverFalseMatches(t *testing.T) {
	m := newTestMatcher(t)
	// A bare verb fragment must not resolve to a single confident exercise.
	got := m.Match("press")
	if got.ResultType == ResultTypeMatch {
		t.Fatalf("bare 'press' resolved to MATCH %q, want non-MATCH", got.TopCandidate.ExerciseID)
	}
}

// TestPopularityTieBreak: "chest press" is an alias shared by several push
// exercises that tie on score. Ranking must surface the most popular first.
func TestPopularityTieBreak(t *testing.T) {
	m := newTestMatcher(t)
	got := m.Match("chest press")

	if got.ResultType != ResultTypeAmbiguous {
		t.Fatalf("type = %s, want AMBIGUOUS", resultName(got.ResultType))
	}
	if len(got.Candidates) < 2 {
		t.Fatalf("ambiguous result needs >=2 candidates, got %d", len(got.Candidates))
	}
	// Top candidate must be the highest-popularity tied exercise (bench_press 0.95).
	if got.Candidates[0].ExerciseID != "bench_press" {
		t.Fatalf("top tie-break = %q, want bench_press", got.Candidates[0].ExerciseID)
	}
	// Candidates must be ordered by non-increasing popularity within the tie.
	for i := 1; i < len(got.Candidates); i++ {
		if got.Candidates[i-1].Score == got.Candidates[i].Score &&
			got.Candidates[i-1].Popularity < got.Candidates[i].Popularity {
			t.Errorf("tie not ordered by popularity at %d: %v", i, got.Candidates)
		}
	}
}
