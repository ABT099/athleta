package graph

import "testing"

// Taxonomy invariants are pure-data checks: they guard the static graph seed
// without a Neo4j instance.

func muscleNames() map[string]MuscleSeed {
	m := make(map[string]MuscleSeed, len(Muscles))
	for _, s := range Muscles {
		m[s.Name] = s
	}
	return m
}

func TestMuscleTaxonomyValid(t *testing.T) {
	muscles := muscleNames()

	if len(muscles) != len(Muscles) {
		t.Fatal("duplicate muscle names in taxonomy")
	}

	validSize := map[string]bool{"small": true, "medium": true, "large": true}
	for _, m := range Muscles {
		if !validSize[m.Size] {
			t.Errorf("muscle %q has invalid size %q", m.Name, m.Size)
		}
		if m.RecoveryHours <= 0 {
			t.Errorf("muscle %q has non-positive recovery hours", m.Name)
		}
		if m.Antagonist != "" {
			if _, ok := muscles[m.Antagonist]; !ok {
				t.Errorf("muscle %q antagonist %q is not a known muscle", m.Name, m.Antagonist)
			}
		}
	}
}

// Single-muscle antagonist pairs (biceps/triceps, quads/hamstrings, etc.)
// must be symmetric. The chest->back mapping is intentionally many-to-one
// (three chest regions, one mid_back) and is excluded.
func TestAntagonistSymmetry(t *testing.T) {
	muscles := muscleNames()
	chestRegions := map[string]bool{"upper_chest": true, "mid_chest": true, "lower_chest": true, "lats": true, "mid_back": true}

	for _, m := range Muscles {
		if m.Antagonist == "" || chestRegions[m.Name] {
			continue
		}
		other := muscles[m.Antagonist]
		if other.Antagonist != m.Name {
			t.Errorf("asymmetric antagonist: %q->%q but %q->%q", m.Name, m.Antagonist, other.Name, other.Antagonist)
		}
	}
}

func TestPatternRelationsReferenceRealPatterns(t *testing.T) {
	patterns := make(map[string]bool, len(Patterns))
	for _, p := range Patterns {
		patterns[p.Name] = true
	}
	for _, rel := range PatternRelations {
		if !patterns[rel.From] {
			t.Errorf("pattern relation from unknown pattern %q", rel.From)
		}
		if !patterns[rel.To] {
			t.Errorf("pattern relation to unknown pattern %q", rel.To)
		}
		if rel.Weight <= 0 || rel.Weight > 1 {
			t.Errorf("pattern relation %s->%s weight %v out of (0,1]", rel.From, rel.To, rel.Weight)
		}
	}
}

func TestEquipmentRelationsReferenceRealEquipment(t *testing.T) {
	equip := make(map[string]bool, len(Equipment))
	for _, e := range Equipment {
		equip[e.Name] = true
	}
	for _, rel := range EquipmentRelations {
		if !equip[rel.From] || !equip[rel.To] {
			t.Errorf("equipment relation %s->%s references unknown equipment", rel.From, rel.To)
		}
	}
}
