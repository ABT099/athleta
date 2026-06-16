package config

// MuscleTargetConfig is a curated muscle target for a vocabulary exercise.
type MuscleTargetConfig struct {
	Name string `json:"name"`
	Role string `json:"role"` // prime_mover | synergist | stabilizer
}

// ExerciseConfig is a curated exercise in the vocabulary. Besides the
// matching surface (aliases, slang, typos) it carries the full attribute
// composition so the seed command can create archetypal graph nodes from it.
type ExerciseConfig struct {
	ID              string               `json:"id"`
	CanonicalName   string               `json:"canonical_name"`
	Aliases         []string             `json:"aliases"`
	Slang           []string             `json:"slang"`
	CommonTypos     []string             `json:"common_typos"`
	MovementPattern string               `json:"movement_pattern"`
	ExerciseType    string               `json:"exercise_type"` // compound | isolation
	Equipment       string               `json:"equipment"`
	Laterality      string               `json:"laterality,omitempty"`
	Angle           string               `json:"angle,omitempty"`
	Grip            string               `json:"grip,omitempty"`
	ForceVector     string               `json:"force_vector,omitempty"` // horizontal | vertical
	MuscleTargets   []MuscleTargetConfig `json:"muscle_targets"`
	PopularityScore float64              `json:"popularity_score"`
}

// ExercisesConfig is the root structure for exercises.json.
type ExercisesConfig struct {
	Exercises []ExerciseConfig `json:"exercises"`
}

// ScoringWeightsConfig contains match weights and thresholds.
type ScoringWeightsConfig struct {
	MatchWeights struct {
		Exact    float64 `json:"exact"`
		Alias    float64 `json:"alias"`
		TokenSet float64 `json:"token_set"`
		Jaccard  float64 `json:"jaccard"`
		Phonetic float64 `json:"phonetic"`
	} `json:"match_weights"`
	Thresholds struct {
		MatchMin         float64 `json:"match_min"`
		AmbiguousGap     float64 `json:"ambiguous_gap"`
		LowConfidenceMin float64 `json:"low_confidence_min"`
	} `json:"thresholds"`
	StopWords              []string `json:"stop_words"`
	ConversationalPatterns []string `json:"conversational_patterns"`
}
