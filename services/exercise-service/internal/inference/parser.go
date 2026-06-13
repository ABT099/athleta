package inference

import (
	"regexp"
	"sort"
	"strings"

	"github.com/athleta/exercise-service/internal/domain"
)

// ParsedExercise is the result of decomposing an exercise name into atomic
// attributes.
type ParsedExercise struct {
	OriginalName    string
	MovementPattern string // one of the 7 patterns, or "" when undeterminable
	ExerciseType    string // compound | isolation
	IsolationTarget string // rules key for isolation movements (e.g. "biceps")
	// Modifiers holds every atomic attribute, force vector included, so the
	// parser's output is exactly the domain attribute shape the service
	// persists — no per-field reconciliation downstream.
	Modifiers domain.Attributes
}

// movementClass describes what a movement keyword implies.
type movementClass struct {
	pattern         string
	exerciseType    string
	forceVector     string
	isolationTarget string
	// impliedEquipment is the conventional equipment for the movement when
	// the name doesn't state one (a bare "deadlift" means a barbell).
	impliedEquipment string
}

// keywordEntry is a phrase mapped to a value, matched on word boundaries.
type keywordEntry struct {
	phrase string
	value  string
}

// movementEntry is a phrase mapped to a movement classification.
type movementEntry struct {
	phrase string
	class  movementClass
}

// Parser decomposes exercise names into movement classification and modifiers.
type Parser struct {
	implements  []keywordEntry
	lateralities []keywordEntry
	angles      []keywordEntry
	grips       []keywordEntry
	tempos      []keywordEntry
	movements   []movementEntry
}

var parserSpaceRegex = regexp.MustCompile(`\s+`)

// NewParser creates a new exercise name parser. Keyword tables are sorted by
// phrase length (longest first) once, so multi-word phrases like "single arm"
// or "split squat" win over their substrings.
func NewParser() *Parser {
	p := &Parser{
		implements: entries(map[string]string{
			"barbell": "barbell", "bb": "barbell", "ez bar": "barbell", "trap bar": "barbell",
			"dumbbell": "dumbbell", "dumbbells": "dumbbell", "db": "dumbbell",
			"kettlebell": "kettlebell", "kb": "kettlebell",
			"cable": "cable",
			"machine": "machine", "smith": "machine", "pec deck": "machine",
			"bodyweight": "bodyweight", "bw": "bodyweight",
			"landmine": "landmine",
			"band": "band", "resistance band": "band", "banded": "band",
		}),
		lateralities: entries(map[string]string{
			"single arm": "unilateral", "one arm": "unilateral",
			"single leg": "unilateral", "one leg": "unilateral",
			"unilateral": "unilateral",
			"alternating": "alternating",
			"bilateral":  "bilateral",
			"isometric":  "isometric_hold",
		}),
		angles: entries(map[string]string{
			"incline": "incline", "decline": "decline", "flat": "flat",
			"overhead": "overhead", "floor": "floor_level", "seated": "",
		}),
		grips: entries(map[string]string{
			"neutral grip": "neutral", "neutral": "neutral",
			"pronated": "pronated", "overhand": "pronated",
			"supinated": "supinated", "underhand": "supinated", "reverse grip": "supinated",
			"wide grip": "wide", "wide": "wide",
			"close grip": "narrow", "narrow": "narrow",
			"staggered": "staggered", "split stance": "split",
		}),
		tempos: entries(map[string]string{
			"paused": "pause", "pause": "pause",
			"tempo": "tempo", "explosive": "explosive",
			"eccentric": "eccentric_focus", "negatives": "eccentric_focus",
			"with chains": "accommodating_resistance", "against bands": "accommodating_resistance",
		}),
	}

	compound := func(pattern, vector string) movementClass {
		return movementClass{pattern: pattern, exerciseType: domain.TypeCompound, forceVector: vector}
	}
	barbell := func(c movementClass) movementClass {
		c.impliedEquipment = "barbell"
		return c
	}
	isolation := func(pattern, target string) movementClass {
		return movementClass{pattern: pattern, exerciseType: domain.TypeIsolation, isolationTarget: target}
	}

	movementTable := map[string]movementClass{
		// Isolation movements first: these phrases must win over the bare
		// compound verbs they contain ("leg curl" vs "curl"-as-pull, "split
		// squat" vs "squat").
		"leg curl":        isolation(domain.PatternHinge, "hamstrings"),
		"hamstring curl":  isolation(domain.PatternHinge, "hamstrings"),
		"leg extension":   isolation(domain.PatternSquat, "quadriceps"),
		"back extension":  isolation(domain.PatternHinge, "erector_spinae"),
		"tricep extension": isolation(domain.PatternPush, "triceps"),
		"triceps extension": isolation(domain.PatternPush, "triceps"),
		"skull crusher":   isolation(domain.PatternPush, "triceps"),
		"pushdown":        isolation(domain.PatternPush, "triceps"),
		"pressdown":       isolation(domain.PatternPush, "triceps"),
		"kickback":        isolation(domain.PatternPush, "triceps"),
		"curl":            isolation(domain.PatternPull, "biceps"),
		"lateral raise":   isolation(domain.PatternPush, "lateral_delt"),
		"side raise":      isolation(domain.PatternPush, "lateral_delt"),
		"front raise":     isolation(domain.PatternPush, "anterior_delt"),
		"rear delt fly":   isolation(domain.PatternPull, "posterior_delt"),
		"reverse fly":     isolation(domain.PatternPull, "posterior_delt"),
		"face pull":       isolation(domain.PatternPull, "posterior_delt"),
		"fly":             isolation(domain.PatternPush, "chest"),
		"flye":            isolation(domain.PatternPush, "chest"),
		"pullover":        isolation(domain.PatternPull, "lats"),
		"shrug":           isolation(domain.PatternPull, "upper_traps"),
		"calf raise":      isolation(domain.PatternSquat, "calves"),
		"leg raise":       isolation(domain.PatternRotation, "abs"),
		"crunch":          isolation(domain.PatternRotation, "abs"),
		"sit up":          isolation(domain.PatternRotation, "abs"),
		"situp":           isolation(domain.PatternRotation, "abs"),
		"wrist curl":      isolation(domain.PatternPull, "forearms"),

		// Compound movements.
		"bench press":    barbell(compound(domain.PatternPush, domain.VectorHorizontal)),
		"floor press":    compound(domain.PatternPush, domain.VectorHorizontal),
		"push up":        compound(domain.PatternPush, domain.VectorHorizontal),
		"pushup":         compound(domain.PatternPush, domain.VectorHorizontal),
		"dip":            compound(domain.PatternPush, domain.VectorVertical),
		"overhead press": compound(domain.PatternPush, domain.VectorVertical),
		"shoulder press": compound(domain.PatternPush, domain.VectorVertical),
		"military press": compound(domain.PatternPush, domain.VectorVertical),
		"push press":     compound(domain.PatternPush, domain.VectorVertical),
		"press":          compound(domain.PatternPush, ""),
		"bench":          compound(domain.PatternPush, domain.VectorHorizontal),

		"pull up":   compound(domain.PatternPull, domain.VectorVertical),
		"pullup":    compound(domain.PatternPull, domain.VectorVertical),
		"chin up":   compound(domain.PatternPull, domain.VectorVertical),
		"chinup":    compound(domain.PatternPull, domain.VectorVertical),
		"pulldown":  compound(domain.PatternPull, domain.VectorVertical),
		"pull down": compound(domain.PatternPull, domain.VectorVertical),
		"high pull": compound(domain.PatternPull, domain.VectorVertical),
		"row":       compound(domain.PatternPull, domain.VectorHorizontal),
		"pull":      compound(domain.PatternPull, ""),

		"split squat": compound(domain.PatternLunge, ""),
		"squat":       barbell(compound(domain.PatternSquat, "")),
		"leg press":   compound(domain.PatternSquat, ""),

		"deadlift":     barbell(compound(domain.PatternHinge, "")),
		"dead lift":    barbell(compound(domain.PatternHinge, "")),
		"rdl":          barbell(compound(domain.PatternHinge, "")),
		"romanian":     barbell(compound(domain.PatternHinge, "")),
		"good morning": barbell(compound(domain.PatternHinge, "")),
		"hip thrust":   barbell(compound(domain.PatternHinge, "")),
		"glute bridge": compound(domain.PatternHinge, ""),
		"swing":        compound(domain.PatternHinge, ""),

		"lunge":   compound(domain.PatternLunge, ""),
		"step up": compound(domain.PatternLunge, ""),

		"carry":  compound(domain.PatternCarry, ""),
		"farmer": compound(domain.PatternCarry, ""),
		"walk":   compound(domain.PatternCarry, ""),

		"woodchop": compound(domain.PatternRotation, ""),
		"chop":     compound(domain.PatternRotation, ""),
		"twist":    compound(domain.PatternRotation, ""),
		"rotation": compound(domain.PatternRotation, ""),
		"plank":    compound(domain.PatternRotation, ""),
	}

	p.movements = make([]movementEntry, 0, len(movementTable))
	for phrase, class := range movementTable {
		p.movements = append(p.movements, movementEntry{phrase: phrase, class: class})
	}
	sort.Slice(p.movements, func(i, j int) bool {
		return len(p.movements[i].phrase) > len(p.movements[j].phrase)
	})

	return p
}

func entries(m map[string]string) []keywordEntry {
	out := make([]keywordEntry, 0, len(m))
	for phrase, value := range m {
		out = append(out, keywordEntry{phrase: phrase, value: value})
	}
	sort.Slice(out, func(i, j int) bool {
		return len(out[i].phrase) > len(out[j].phrase)
	})
	return out
}

// Parse extracts the movement classification and modifiers from a name.
func (p *Parser) Parse(name string) *ParsedExercise {
	text := normalizeForParsing(name)

	parsed := &ParsedExercise{
		OriginalName: name,
		Modifiers:    domain.Attributes{},
	}

	parsed.Modifiers.Equipment = matchKeyword(text, p.implements)
	parsed.Modifiers.Laterality = matchKeyword(text, p.lateralities)
	if parsed.Modifiers.Laterality == "" {
		parsed.Modifiers.Laterality = "bilateral"
	}
	parsed.Modifiers.Angle = matchKeyword(text, p.angles)
	parsed.Modifiers.Grip = matchKeyword(text, p.grips)
	parsed.Modifiers.Tempo = matchKeyword(text, p.tempos)

	var impliedEquipment string
	for _, entry := range p.movements {
		if containsPhrase(text, entry.phrase) {
			parsed.MovementPattern = entry.class.pattern
			parsed.ExerciseType = entry.class.exerciseType
			parsed.Modifiers.ForceVector = entry.class.forceVector
			parsed.IsolationTarget = entry.class.isolationTarget
			impliedEquipment = entry.class.impliedEquipment
			break
		}
	}

	if parsed.ExerciseType == "" {
		// Unknown movement: treat as isolation to avoid overstating CNS
		// demand and injury risk for something we cannot classify.
		parsed.ExerciseType = domain.TypeIsolation
	}

	// An overhead angle on a push/pull implies a vertical force vector.
	if parsed.Modifiers.ForceVector == "" && parsed.Modifiers.Angle == "overhead" {
		if parsed.MovementPattern == domain.PatternPush || parsed.MovementPattern == domain.PatternPull {
			parsed.Modifiers.ForceVector = domain.VectorVertical
		}
	}
	if parsed.Modifiers.ForceVector == "" && parsed.MovementPattern == domain.PatternPush {
		parsed.Modifiers.ForceVector = domain.VectorHorizontal
	}
	if parsed.Modifiers.ForceVector == "" && parsed.MovementPattern == domain.PatternPull {
		parsed.Modifiers.ForceVector = domain.VectorHorizontal
	}
	// A vertical force vector implies the overhead angle for pushes.
	if parsed.Modifiers.ForceVector == domain.VectorVertical && parsed.MovementPattern == domain.PatternPush && parsed.Modifiers.Angle == "" {
		parsed.Modifiers.Angle = "overhead"
	}

	if parsed.Modifiers.Equipment == "" {
		if impliedEquipment != "" {
			parsed.Modifiers.Equipment = impliedEquipment
		} else {
			parsed.Modifiers.Equipment = "bodyweight"
		}
	}

	return parsed
}

func normalizeForParsing(name string) string {
	text := strings.ToLower(name)
	text = strings.ReplaceAll(text, "-", " ")
	text = strings.ReplaceAll(text, "_", " ")
	return strings.TrimSpace(parserSpaceRegex.ReplaceAllString(text, " "))
}

// matchKeyword returns the value of the first (longest) phrase present in
// the text on word boundaries.
func matchKeyword(text string, table []keywordEntry) string {
	for _, entry := range table {
		if containsPhrase(text, entry.phrase) {
			return entry.value
		}
	}
	return ""
}

// containsPhrase reports whether phrase occurs in text on word boundaries,
// so "im" never matches inside "landmine".
func containsPhrase(text, phrase string) bool {
	return strings.Contains(" "+text+" ", " "+phrase+" ")
}
