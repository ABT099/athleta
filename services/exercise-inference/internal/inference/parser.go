package inference

import (
	"regexp"
	"strings"

	"github.com/athleta/exercise-inference/internal/models"
)

// Parser handles exercise name parsing and keyword extraction
type Parser struct {
	implementKeywords   map[string]string
	lateralityKeywords  map[string]string
	angleKeywords       map[string]string
	gripStanceKeywords  map[string]string
	tempoKeywords       map[string]string
	movementVerbs       map[string]string
}

// NewParser creates a new exercise name parser
func NewParser() *Parser {
	return &Parser{
		implementKeywords: map[string]string{
			"barbell":         "barbell",
			"dumbbell":        "dumbbell",
			"dumbbells":       "dumbbell",
			"db":              "dumbbell",
			"kettlebell":      "kettlebell",
			"kb":              "kettlebell",
			"cable":           "cable",
			"machine":         "machine",
			"bodyweight":      "bodyweight",
			"bw":              "bodyweight",
			"landmine":        "landmine",
			"band":            "band",
			"resistance band": "band",
		},
		lateralityKeywords: map[string]string{
			"single arm":   "unilateral",
			"single-arm":   "unilateral",
			"one arm":      "unilateral",
			"one-arm":      "unilateral",
			"single leg":   "unilateral",
			"single-leg":   "unilateral",
			"one leg":      "unilateral",
			"one-leg":      "unilateral",
			"unilateral":   "unilateral",
			"alternating":  "alternating",
			"bilateral":    "bilateral",
			"isometric":    "isometric_hold",
		},
		angleKeywords: map[string]string{
			"incline":   "incline",
			"decline":   "decline",
			"flat":      "flat",
			"overhead":  "overhead",
			"floor":     "floor_level",
		},
		gripStanceKeywords: map[string]string{
			"neutral":      "neutral",
			"neutral grip": "neutral",
			"pronated":     "pronated",
			"overhand":     "pronated",
			"supinated":    "supinated",
			"underhand":    "supinated",
			"wide":         "wide",
			"wide grip":    "wide",
			"narrow":       "narrow",
			"close grip":   "narrow",
			"close-grip":   "narrow",
			"staggered":    "staggered",
			"split":        "split",
		},
		tempoKeywords: map[string]string{
			"paused":       "pause",
			"pause":        "pause",
			"tempo":        "tempo",
			"explosive":    "explosive",
			"eccentric":    "eccentric_focus",
			"chains":       "accommodating_resistance",
			"bands":        "accommodating_resistance",
		},
		movementVerbs: map[string]string{
			// Push movements
			"press":     "push",
			"bench":     "push",
			"pushup":    "push",
			"push-up":   "push",
			"push up":   "push",
			"dip":       "push",
			
			// Pull movements
			"row":       "pull",
			"pull":      "pull",
			"pullup":    "pull",
			"pull-up":   "pull",
			"pull up":   "pull",
			"pulldown":  "pull",
			"pull-down": "pull",
			"pull down": "pull",
			"lat":       "pull",
			"chin":      "pull",
			"chinup":    "pull",
			"chin-up":   "pull",
			
			// Squat movements
			"squat":     "squat",
			
			// Hinge movements
			"deadlift":  "hinge",
			"rdl":       "hinge",
			"romanian":  "hinge",
			"hip thrust": "hinge",
			"thrust":    "hinge",
			"good morning": "hinge",
			
			// Lunge movements
			"lunge":     "lunge",
			"step":      "lunge",
			"split squat": "lunge",
			
			// Isolation movements
			"curl":      "pull",
			"extension": "push",
			"fly":       "push",
			"flye":      "push",
			"raise":     "push",
			"lateral":   "push",
			"shrug":     "pull",
			
			// Carry movements
			"carry":     "carry",
			"walk":      "carry",
			"farmer":    "carry",
			
			// Core/Rotation
			"crunch":    "rotation",
			"plank":     "rotation",
			"twist":     "rotation",
			"rotation":  "rotation",
			"chop":      "rotation",
		},
	}
}

// ParseExerciseName extracts modifiers and movement pattern from exercise name
func (p *Parser) ParseExerciseName(name string) *models.ParsedExercise {
	nameLower := strings.ToLower(name)
	
	parsed := &models.ParsedExercise{
		OriginalName: name,
		Modifiers:    models.ExerciseModifiers{},
	}
	
	// Extract implement
	parsed.Modifiers.Implement = p.extractKeyword(nameLower, p.implementKeywords)
	
	// Extract laterality
	parsed.Modifiers.Laterality = p.extractKeyword(nameLower, p.lateralityKeywords)
	if parsed.Modifiers.Laterality == "" {
		parsed.Modifiers.Laterality = "bilateral" // default
	}
	
	// Extract angle
	parsed.Modifiers.Angle = p.extractKeyword(nameLower, p.angleKeywords)
	
	// Extract grip/stance
	parsed.Modifiers.GripStance = p.extractKeyword(nameLower, p.gripStanceKeywords)
	
	// Extract tempo
	parsed.Modifiers.Tempo = p.extractKeyword(nameLower, p.tempoKeywords)
	
	// Extract movement pattern from verbs
	parsed.MovementPattern = p.extractKeyword(nameLower, p.movementVerbs)
	if parsed.MovementPattern == "" {
		parsed.MovementPattern = "unknown"
	}
	
	// Extract base exercise name (simplified version)
	parsed.BaseExercise = p.extractBaseExercise(nameLower, parsed.MovementPattern)
	
	return parsed
}

// extractKeyword finds the first matching keyword in the text
func (p *Parser) extractKeyword(text string, keywords map[string]string) string {
	// Sort by length (longest first) to match "single arm" before "single"
	var sortedKeys []string
	for key := range keywords {
		sortedKeys = append(sortedKeys, key)
	}
	
	// Simple bubble sort by length (descending)
	for i := 0; i < len(sortedKeys); i++ {
		for j := i + 1; j < len(sortedKeys); j++ {
			if len(sortedKeys[i]) < len(sortedKeys[j]) {
				sortedKeys[i], sortedKeys[j] = sortedKeys[j], sortedKeys[i]
			}
		}
	}
	
	for _, key := range sortedKeys {
		if strings.Contains(text, key) {
			return keywords[key]
		}
	}
	
	return ""
}

// extractBaseExercise attempts to extract the core exercise name
func (p *Parser) extractBaseExercise(text string, pattern string) string {
	// Remove common modifiers to get base name
	cleaned := text
	
	// Remove implement keywords
	for key := range p.implementKeywords {
		cleaned = strings.ReplaceAll(cleaned, key, "")
	}
	
	// Remove laterality keywords
	for key := range p.lateralityKeywords {
		cleaned = strings.ReplaceAll(cleaned, key, "")
	}
	
	// Remove angle keywords
	for key := range p.angleKeywords {
		cleaned = strings.ReplaceAll(cleaned, key, "")
	}
	
	// Remove tempo keywords
	for key := range p.tempoKeywords {
		cleaned = strings.ReplaceAll(cleaned, key, "")
	}
	
	// Clean up whitespace
	re := regexp.MustCompile(`\s+`)
	cleaned = re.ReplaceAllString(strings.TrimSpace(cleaned), " ")
	
	return cleaned
}

// DetermineExerciseType determines if exercise is compound or isolation
func (p *Parser) DetermineExerciseType(pattern string, modifiers models.ExerciseModifiers) string {
	// Multi-joint movements are compound
	compoundPatterns := map[string]bool{
		"push":   true,
		"pull":   true,
		"squat":  true,
		"hinge":  true,
		"lunge":  true,
		"carry":  true,
	}
	
	if compoundPatterns[pattern] {
		// Check if it's a machine (machines are often more isolated)
		if modifiers.Implement == "machine" {
			return "compound" // Still compound but controlled
		}
		return "compound"
	}
	
	// Single-joint movements are isolation
	return "isolation"
}

// GenerateDescription creates a human-readable description
func (p *Parser) GenerateDescription(name string, pattern string, modifiers models.ExerciseModifiers) string {
	parts := []string{}
	
	// Add laterality
	if modifiers.Laterality == "unilateral" {
		parts = append(parts, "Unilateral")
	} else if modifiers.Laterality == "alternating" {
		parts = append(parts, "Alternating")
	}
	
	// Add angle
	if modifiers.Angle != "" && modifiers.Angle != "flat" {
		parts = append(parts, modifiers.Angle)
	}
	
	// Add pattern description
	patternDesc := map[string]string{
		"push":     "pressing movement",
		"pull":     "pulling movement",
		"squat":    "squat pattern",
		"hinge":    "hip hinge movement",
		"lunge":    "lunge pattern",
		"carry":    "loaded carry",
		"rotation": "core stability exercise",
	}
	
	if desc, ok := patternDesc[pattern]; ok {
		parts = append(parts, desc)
	}
	
	// Add implement
	if modifiers.Implement != "" && modifiers.Implement != "bodyweight" {
		parts = append(parts, "using "+modifiers.Implement)
	}
	
	if len(parts) == 0 {
		return name
	}
	
	return strings.Join(parts, " ")
}

