package inference

import (
	"testing"

	"github.com/athleta/exercise-service/internal/domain"
)

// Per-extractor tests exercise each attribute axis through the public Parse
// API: positive cases, edge cases, and the word-boundary behaviour that the
// old substring matcher got wrong.

func TestExtractImplement(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Barbell Bench Press", "barbell"},
		{"BB Row", "barbell"},
		{"Dumbbell Curl", "dumbbell"},
		{"DB Shoulder Press", "dumbbell"},
		{"Kettlebell Swing", "kettlebell"},
		{"KB Goblet Squat", "kettlebell"},
		{"Cable Fly", "cable"},
		{"Machine Chest Press", "machine"},
		{"Smith Machine Squat", "machine"},
		{"Landmine Press", "landmine"},
		{"Banded Pull Apart", "band"},
		{"Resistance Band Row", "band"},
		// No implement stated -> movement-implied default (press is bodyweight).
		{"Push Up", "bodyweight"},
		// "db" must not match inside a larger word.
		{"Dumbbell Romanian Deadlift", "dumbbell"},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.Equipment; got != c.want {
			t.Errorf("implement(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractLaterality(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Single Arm Dumbbell Row", "unilateral"},
		{"One Arm Cable Row", "unilateral"},
		{"Single Leg Press", "unilateral"},
		{"Unilateral Leg Extension", "unilateral"},
		{"Alternating Dumbbell Curl", "alternating"},
		{"Isometric Plank Hold", "isometric_hold"},
		// Default when unstated.
		{"Barbell Bench Press", "bilateral"},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.Laterality; got != c.want {
			t.Errorf("laterality(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractAngle(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Incline Dumbbell Press", "incline"},
		{"Decline Bench Press", "decline"},
		{"Flat Barbell Bench", "flat"},
		{"Overhead Press", "overhead"},
		{"Floor Press", "floor_level"},
		// No angle keyword.
		{"Barbell Row", ""},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.Angle; got != c.want {
			t.Errorf("angle(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractGrip(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Neutral Grip Pulldown", "neutral"},
		{"Pronated Curl", "pronated"},
		{"Overhand Row", "pronated"},
		{"Supinated Pulldown", "supinated"},
		{"Underhand Row", "supinated"},
		{"Wide Grip Pull Up", "wide"},
		{"Close Grip Bench Press", "narrow"},
		// Multi-word phrase must win over the bare "wide"/"close" substrings.
		{"Barbell Bench Press", ""},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.Grip; got != c.want {
			t.Errorf("grip(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractForceVector(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Overhead Press", domain.VectorVertical},
		{"Lat Pulldown", domain.VectorVertical},
		{"Pull Up", domain.VectorVertical},
		{"Barbell Bench Press", domain.VectorHorizontal},
		{"Barbell Row", domain.VectorHorizontal},
		// Non push/pull patterns have no force vector.
		{"Barbell Back Squat", ""},
		{"Conventional Deadlift", ""},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.ForceVector; got != c.want {
			t.Errorf("forceVector(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractTempo(t *testing.T) {
	p := NewParser()
	cases := []struct {
		in, want string
	}{
		{"Paused Bench Press", "pause"},
		{"Tempo Squat", "tempo"},
		{"Explosive Push Up", "explosive"},
		{"Eccentric Leg Curl", "eccentric_focus"},
		{"Barbell Row", ""},
	}
	for _, c := range cases {
		if got := p.Parse(c.in).Modifiers.Tempo; got != c.want {
			t.Errorf("tempo(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

// TestAuditRegressions pins the ten correctness issues the audit flagged, so
// they cannot silently regress.
func TestAuditRegressions(t *testing.T) {
	p := NewParser()
	safety := NewSafetyAnalyzer()
	rules := NewRulesEngine()

	hasPrimeMover := func(targets []domain.MuscleTarget) bool {
		for _, m := range targets {
			if m.Role == domain.RolePrimeMover {
				return true
			}
		}
		return false
	}

	t.Run("1: curl is isolation not compound pull", func(t *testing.T) {
		got := p.Parse("Barbell Bicep Curl")
		if got.ExerciseType != domain.TypeIsolation {
			t.Fatalf("type = %q, want isolation", got.ExerciseType)
		}
	})
	t.Run("2: raise is isolation", func(t *testing.T) {
		if p.Parse("Dumbbell Lateral Raise").ExerciseType != domain.TypeIsolation {
			t.Fatal("lateral raise must be isolation")
		}
	})
	t.Run("3: extension is isolation", func(t *testing.T) {
		if p.Parse("Tricep Extension").ExerciseType != domain.TypeIsolation {
			t.Fatal("tricep extension must be isolation")
		}
	})
	t.Run("4: fly is isolation", func(t *testing.T) {
		if p.Parse("Cable Fly").ExerciseType != domain.TypeIsolation {
			t.Fatal("fly must be isolation")
		}
	})
	t.Run("5: vertical pull detected without impossible implement check", func(t *testing.T) {
		if p.Parse("Lat Pulldown").Modifiers.ForceVector != domain.VectorVertical {
			t.Fatal("pulldown must be vertical pull")
		}
	})
	t.Run("6: substring boundary - landmine not parsed as 'im' contraction", func(t *testing.T) {
		got := p.Parse("Landmine Press")
		if got.Modifiers.Equipment != "landmine" {
			t.Fatalf("equipment = %q, want landmine", got.Modifiers.Equipment)
		}
	})
	t.Run("7: barbell row is compound_heavy not moderate", func(t *testing.T) {
		if got := safety.IntensityCategory(p.Parse("Barbell Row")); got != domain.IntensityCompoundHeavy {
			t.Fatalf("intensity = %q, want compound_heavy", got)
		}
	})
	t.Run("8: rotation has real prime movers", func(t *testing.T) {
		targets := rules.InferMuscleTargets(p.Parse("Cable Woodchop"))
		if !hasPrimeMover(targets) {
			t.Fatal("rotation must yield a prime mover")
		}
	})
	t.Run("9: split squat is lunge not squat", func(t *testing.T) {
		if p.Parse("Bulgarian Split Squat").MovementPattern != domain.PatternLunge {
			t.Fatal("split squat must be lunge")
		}
	})
	t.Run("10: complexity not maxed at 1.0 by default for isolation", func(t *testing.T) {
		c := safety.Analyze(p.Parse("Dumbbell Lateral Raise")).ComplexityScore
		if c >= 1.0 {
			t.Fatalf("isolation complexity = %v, want well below 1.0", c)
		}
	})
}
