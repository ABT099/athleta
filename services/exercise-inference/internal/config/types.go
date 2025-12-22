package config

// ExerciseConfig represents a single exercise in the vocabulary
type ExerciseConfig struct {
	ID            string   `json:"id"`
	CanonicalName string   `json:"canonical_name"`
	Aliases       []string `json:"aliases"`
	Slang         []string `json:"slang"`
	CommonTypos   []string `json:"common_typos"`
	Equipment     string   `json:"equipment"`
	MuscleGroups  []string `json:"muscle_groups"`
	MovementPattern string `json:"movement_pattern"`
	PhoneticKey   string   `json:"phonetic_key"`
	PopularityScore float64 `json:"popularity_score"`
}

// ExercisesConfig is the root structure for exercises.json
type ExercisesConfig struct {
	Exercises []ExerciseConfig `json:"exercises"`
}

// ScoringWeightsConfig contains match weights and thresholds
type ScoringWeightsConfig struct {
	MatchWeights struct {
		Exact     float64 `json:"exact"`
		Alias     float64 `json:"alias"`
		TokenSet  float64 `json:"token_set"`
		Jaccard   float64 `json:"jaccard"`
		Phonetic  float64 `json:"phonetic"`
	} `json:"match_weights"`
	Thresholds struct {
		MatchMin        float64 `json:"match_min"`
		AmbiguousGap   float64 `json:"ambiguous_gap"`
		LowConfidenceMin float64 `json:"low_confidence_min"`
	} `json:"thresholds"`
	StopWords            []string `json:"stop_words"`
	ConversationalPatterns []string `json:"conversational_patterns"`
}


