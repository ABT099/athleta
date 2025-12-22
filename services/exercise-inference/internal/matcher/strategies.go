package matcher

import (
	"strings"

	"github.com/athleta/exercise-inference/internal/config"
)

// CandidateSignal represents a match signal from a strategy
type CandidateSignal struct {
	ExerciseID  string
	Score       float32
	Strategy    string
}

// StrategyRunner runs all matching strategies in parallel
type StrategyRunner struct {
	exercises *config.ExercisesConfig
}

// NewStrategyRunner creates a new strategy runner
func NewStrategyRunner(exercises *config.ExercisesConfig) *StrategyRunner {
	return &StrategyRunner{
		exercises: exercises,
	}
}

// RunAllStrategies runs all matching strategies and returns signals
func (sr *StrategyRunner) RunAllStrategies(inputTokens []string, inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	
	// Run all strategies (can be parallelized with goroutines if needed)
	signals = append(signals, sr.exactMatch(inputTokens, inputNormalized)...)
	signals = append(signals, sr.aliasMatch(inputTokens, inputNormalized)...)
	signals = append(signals, sr.tokenSetMatch(inputTokens)...)
	signals = append(signals, sr.jaccardMatch(inputTokens)...)
	signals = append(signals, sr.phoneticMatch(inputNormalized)...)
	
	return signals
}

// exactMatch performs exact string matching
func (sr *StrategyRunner) exactMatch(inputTokens []string, inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	inputLower := strings.ToLower(strings.TrimSpace(inputNormalized))
	inputTokenStr := strings.Join(inputTokens, " ")
	
	for _, ex := range sr.exercises.Exercises {
		// Check canonical name (both normalized and tokenized)
		canonicalLower := strings.ToLower(strings.TrimSpace(ex.CanonicalName))
		if canonicalLower == inputLower || canonicalLower == inputTokenStr {
			signals = append(signals, CandidateSignal{
				ExerciseID: ex.ID,
				Score:      1.0,
				Strategy:   "exact",
			})
			continue
		}
		
		// Check aliases (both normalized and tokenized)
		for _, alias := range ex.Aliases {
			aliasLower := strings.ToLower(strings.TrimSpace(alias))
			if aliasLower == inputLower || aliasLower == inputTokenStr {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      1.0,
					Strategy:   "exact",
				})
				break
			}
		}
	}
	
	return signals
}

// aliasMatch performs alias/slang/typo matching
func (sr *StrategyRunner) aliasMatch(inputTokens []string, inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	inputLower := strings.ToLower(strings.TrimSpace(inputNormalized))
	inputTokenStr := strings.Join(inputTokens, " ")
	
	for _, ex := range sr.exercises.Exercises {
		// Check aliases (both normalized string and tokenized version)
		for _, alias := range ex.Aliases {
			aliasLower := strings.ToLower(strings.TrimSpace(alias))
			if aliasLower == inputLower || aliasLower == inputTokenStr {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      1.0,
					Strategy:   "alias",
				})
				break
			}
		}
		
		// Check slang (try both singular and plural versions)
		for _, slang := range ex.Slang {
			slangLower := strings.ToLower(strings.TrimSpace(slang))
			slangLowerPlural := slangLower + "s"
			if slangLower == inputLower || slangLower == inputTokenStr ||
				slangLowerPlural == inputLower || slangLowerPlural == inputTokenStr {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      0.95,
					Strategy:   "alias",
				})
				break
			}
		}
		
		// Check common typos
		for _, typo := range ex.CommonTypos {
			typoLower := strings.ToLower(strings.TrimSpace(typo))
			if typoLower == inputLower || typoLower == inputTokenStr {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      0.90,
					Strategy:   "alias",
				})
				break
			}
		}
	}
	
	return signals
}

// tokenSetMatch performs token set ratio matching (handles word order)
// Uses sorted token intersection ratio for better word order handling
func (sr *StrategyRunner) tokenSetMatch(inputTokens []string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	
	if len(inputTokens) == 0 {
		return signals
	}
	
	inputSet := makeTokenSet(inputTokens)
	inputLen := len(inputTokens)
	
	for _, ex := range sr.exercises.Exercises {
		// Build all possible name variations
		allNames := []string{ex.CanonicalName}
		allNames = append(allNames, ex.Aliases...)
		
		bestScore := float32(0.0)
		
		for _, name := range allNames {
			nameTokens := strings.Fields(strings.ToLower(name))
			nameSet := makeTokenSet(nameTokens)
			nameLen := len(nameTokens)
			
			// Calculate intersection
			intersection := countIntersection(inputSet, nameSet)
			
			if intersection == 0 {
				continue
			}
			
			// Token set ratio: intersection / max(inputLen, nameLen)
			// This gives higher scores when all tokens match, regardless of order
			maxLen := inputLen
			if nameLen > maxLen {
				maxLen = nameLen
			}
			
			// Calculate token set ratio: intersection / union
			// This handles word order variations
			union := inputLen + nameLen - intersection
			
			if union == 0 {
				continue
			}
			
			// If all tokens from shorter set are in longer set, boost score
			// This handles "press bench flat" -> "bench press" (flat is extra)
			if intersection == inputLen || intersection == nameLen {
				// Perfect subset match - high score
				score := float32(0.9) // High score for subset matches
				if score > bestScore {
					bestScore = score
				}
			} else {
				// Partial match: intersection / union (Jaccard)
				score := float32(intersection) / float32(union)
				if score > bestScore {
					bestScore = score
				}
			}
		}
		
		if bestScore > 0.0 {
			signals = append(signals, CandidateSignal{
				ExerciseID: ex.ID,
				Score:      bestScore,
				Strategy:   "token_set",
			})
		}
	}
	
	return signals
}

// jaccardMatch performs Jaccard similarity matching
func (sr *StrategyRunner) jaccardMatch(inputTokens []string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	
	if len(inputTokens) == 0 {
		return signals
	}
	
	inputSet := makeTokenSet(inputTokens)
	
	for _, ex := range sr.exercises.Exercises {
		allNames := []string{ex.CanonicalName}
		allNames = append(allNames, ex.Aliases...)
		
		bestScore := float32(0.0)
		
		for _, name := range allNames {
			nameTokens := strings.Fields(strings.ToLower(name))
			nameSet := makeTokenSet(nameTokens)
			
			// Jaccard: intersection / union
			intersection := countIntersection(inputSet, nameSet)
			union := len(inputSet) + len(nameSet) - intersection
			
			if union == 0 {
				continue
			}
			
			score := float32(intersection) / float32(union)
			if score > bestScore {
				bestScore = score
			}
		}
		
		if bestScore > 0.0 {
			signals = append(signals, CandidateSignal{
				ExerciseID: ex.ID,
				Score:      bestScore,
				Strategy:   "jaccard",
			})
		}
	}
	
	return signals
}

// phoneticMatch performs phonetic matching using Soundex-like algorithm
func (sr *StrategyRunner) phoneticMatch(inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)
	
	inputPhonetic := soundex(inputNormalized)
	if inputPhonetic == "" {
		return signals
	}
	
	for _, ex := range sr.exercises.Exercises {
		// Check canonical name
		canonicalPhonetic := soundex(strings.ToLower(ex.CanonicalName))
		if canonicalPhonetic == inputPhonetic {
			signals = append(signals, CandidateSignal{
				ExerciseID: ex.ID,
				Score:      0.85,
				Strategy:   "phonetic",
			})
			continue
		}
		
		// Check aliases
		for _, alias := range ex.Aliases {
			aliasPhonetic := soundex(strings.ToLower(alias))
			if aliasPhonetic == inputPhonetic {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      0.85,
					Strategy:   "phonetic",
				})
				break
			}
		}
		
		// Check phonetic_key if available
		if ex.PhoneticKey != "" {
			keyPhonetic := soundex(strings.ToLower(ex.PhoneticKey))
			if keyPhonetic == inputPhonetic {
				signals = append(signals, CandidateSignal{
					ExerciseID: ex.ID,
					Score:      0.80,
					Strategy:   "phonetic",
				})
			}
		}
	}
	
	return signals
}

// Helper functions

// max returns the maximum of two integers
func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// makeTokenSet creates a set of tokens (map for O(1) lookup)
func makeTokenSet(tokens []string) map[string]bool {
	set := make(map[string]bool)
	for _, token := range tokens {
		set[token] = true
	}
	return set
}

// countIntersection counts the intersection of two token sets
func countIntersection(set1, set2 map[string]bool) int {
	count := 0
	for token := range set1 {
		if set2[token] {
			count++
		}
	}
	return count
}

// soundex implements a simplified Soundex algorithm
func soundex(s string) string {
	if len(s) == 0 {
		return ""
	}
	
	// Remove non-letters and convert to uppercase
	var cleaned strings.Builder
	for _, r := range s {
		if r >= 'a' && r <= 'z' {
			cleaned.WriteRune(r - 32) // Convert to uppercase
		} else if r >= 'A' && r <= 'Z' {
			cleaned.WriteRune(r)
		}
	}
	
	if cleaned.Len() == 0 {
		return ""
	}
	
	// Soundex mapping
	code := make([]byte, 0, 4)
	code = append(code, cleaned.String()[0])
	
	prevCode := byte(0)
	for i := 1; i < cleaned.Len() && len(code) < 4; i++ {
		char := cleaned.String()[i]
		var digit byte
		
		switch char {
		case 'B', 'F', 'P', 'V':
			digit = '1'
		case 'C', 'G', 'J', 'K', 'Q', 'S', 'X', 'Z':
			digit = '2'
		case 'D', 'T':
			digit = '3'
		case 'L':
			digit = '4'
		case 'M', 'N':
			digit = '5'
		case 'R':
			digit = '6'
		default:
			digit = 0
		}
		
		if digit != 0 && digit != prevCode {
			code = append(code, digit)
		}
		prevCode = digit
	}
	
	// Pad with zeros
	for len(code) < 4 {
		code = append(code, '0')
	}
	
	return string(code)
}

