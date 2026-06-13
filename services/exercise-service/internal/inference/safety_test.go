package inference

import (
	"testing"

	"github.com/athleta/exercise-service/internal/domain"
)

func TestIntensityResolver(t *testing.T) {
	p := NewParser()
	safety := NewSafetyAnalyzer()

	cases := []struct {
		input string
		want  string
	}{
		// Corrected mappings from the audit.
		{"Barbell Row", domain.IntensityCompoundHeavy},
		{"Conventional Deadlift", domain.IntensityCompoundHeavy},
		{"Barbell Back Squat", domain.IntensityCompoundHeavy},
		{"Barbell Overhead Press", domain.IntensityCompoundHeavy}, // barbell vertical push
		{"Dumbbell Bench Press", domain.IntensityCompoundModerate},
		{"Dumbbell Goblet Squat", domain.IntensityCompoundModerate},
		{"Machine Chest Press", domain.IntensityCompoundModerate},
		// curl / raise / extension / fly -> isolation.
		{"Barbell Bicep Curl", domain.IntensityIsolation},
		{"Dumbbell Lateral Raise", domain.IntensityIsolation},
		{"Tricep Extension", domain.IntensityIsolation},
		{"Cable Fly", domain.IntensityIsolation},
	}

	for _, c := range cases {
		if got := safety.IntensityCategory(p.Parse(c.input)); got != c.want {
			t.Errorf("IntensityCategory(%q) = %q, want %q", c.input, got, c.want)
		}
	}
}

func TestInjuryRiskBounds(t *testing.T) {
	p := NewParser()
	safety := NewSafetyAnalyzer()

	for _, in := range []string{
		"Conventional Deadlift", "Barbell Back Squat", "Overhead Press",
		"Dumbbell Lateral Raise", "Plank", "Machine Chest Press",
	} {
		r := safety.Analyze(p.Parse(in)).InjuryRiskLevel
		if r < 1.0 || r > 3.0 {
			t.Errorf("injury risk(%q) = %v, out of [1,3]", in, r)
		}
	}

	// Relative ordering: barbell deadlift riskier than a machine isolation.
	deadlift := safety.Analyze(p.Parse("Conventional Deadlift")).InjuryRiskLevel
	legExt := safety.Analyze(p.Parse("Leg Extension")).InjuryRiskLevel
	if deadlift <= legExt {
		t.Errorf("deadlift risk %v should exceed leg extension %v", deadlift, legExt)
	}
}

func TestComplexityBounds(t *testing.T) {
	p := NewParser()
	safety := NewSafetyAnalyzer()

	for _, in := range []string{
		"Conventional Deadlift", "Dumbbell Lateral Raise", "Machine Chest Press",
	} {
		c := safety.Analyze(p.Parse(in)).ComplexityScore
		if c < 0.0 || c > 1.0 {
			t.Errorf("complexity(%q) = %v, out of [0,1]", in, c)
		}
	}

	// Isolation must not default to maximum complexity (audit bug: PG default 1.0).
	iso := safety.Analyze(p.Parse("Dumbbell Lateral Raise")).ComplexityScore
	compound := safety.Analyze(p.Parse("Conventional Deadlift")).ComplexityScore
	if iso >= compound {
		t.Errorf("isolation complexity %v should be below compound %v", iso, compound)
	}
}

func TestJointStress(t *testing.T) {
	p := NewParser()
	safety := NewSafetyAnalyzer()

	contains := func(xs []string, target string) bool {
		for _, x := range xs {
			if x == target {
				return true
			}
		}
		return false
	}

	cases := []struct {
		input string
		joint string
	}{
		{"Barbell Back Squat", "knee"},
		{"Conventional Deadlift", "lower_back"},
		{"Overhead Press", "shoulder"},
		{"Walking Lunge", "ankle"},
	}
	for _, c := range cases {
		joints := safety.Analyze(p.Parse(c.input)).JointStressAreas
		if !contains(joints, c.joint) {
			t.Errorf("jointStress(%q) = %v, want to include %q", c.input, joints, c.joint)
		}
	}
}
