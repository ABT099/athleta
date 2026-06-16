package matcher

import (
	"strings"

	"github.com/athleta/exercise-service/internal/config"
)

// CandidateSignal represents a match signal from a strategy.
type CandidateSignal struct {
	ExerciseID string
	Score      float32
	Strategy   string
}

// StrategyRunner runs all matching strategies.
type StrategyRunner struct {
	exercises *config.ExercisesConfig
}

// NewStrategyRunner creates a new strategy runner.
func NewStrategyRunner(exercises *config.ExercisesConfig) *StrategyRunner {
	return &StrategyRunner{exercises: exercises}
}

// RunAllStrategies runs all matching strategies and returns signals.
func (sr *StrategyRunner) RunAllStrategies(inputTokens []string, inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	signals = append(signals, sr.exactMatch(inputNormalized)...)
	signals = append(signals, sr.aliasMatch(inputNormalized)...)
	signals = append(signals, sr.tokenSetMatch(inputTokens)...)
	signals = append(signals, sr.jaccardMatch(inputTokens)...)
	signals = append(signals, sr.phoneticMatch(inputTokens)...)

	return signals
}

// exactMatch matches the canonical name exactly.
func (sr *StrategyRunner) exactMatch(inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	for _, ex := range sr.exercises.Exercises {
		if normalizeName(ex.CanonicalName) == inputNormalized {
			signals = append(signals, CandidateSignal{ExerciseID: ex.ID, Score: 1.0, Strategy: "exact"})
		}
	}

	return signals
}

// aliasMatch matches aliases, slang (with plural tolerance), and known typos.
func (sr *StrategyRunner) aliasMatch(inputNormalized string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	for _, ex := range sr.exercises.Exercises {
		best := float32(0)

		for _, alias := range ex.Aliases {
			if normalizeName(alias) == inputNormalized {
				best = maxf(best, 1.0)
				break
			}
		}

		for _, slang := range ex.Slang {
			s := normalizeName(slang)
			if s == inputNormalized || s+"s" == inputNormalized || depluralize(s) == inputNormalized {
				best = maxf(best, 0.95)
				break
			}
		}

		for _, typo := range ex.CommonTypos {
			if normalizeName(typo) == inputNormalized {
				best = maxf(best, 0.90)
				break
			}
		}

		if best > 0 {
			signals = append(signals, CandidateSignal{ExerciseID: ex.ID, Score: best, Strategy: "alias"})
		}
	}

	return signals
}

// tokenSetMatch performs token set matching that tolerates word order.
// Direction matters: an input containing every token of a name (user typed
// extra words) is strong evidence; an input that is only a fragment of a
// name (e.g. just "press") is weak and scaled by coverage, so a single
// shared token cannot masquerade as a near-match.
func (sr *StrategyRunner) tokenSetMatch(inputTokens []string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	if len(inputTokens) == 0 {
		return signals
	}

	inputSet := makeTokenSet(inputTokens)

	for _, ex := range sr.exercises.Exercises {
		bestScore := float32(0.0)

		for _, name := range matchableNames(ex) {
			nameTokens := strings.Fields(normalizeName(name))
			nameSet := makeTokenSet(nameTokens)

			intersection := countIntersection(inputSet, nameSet)
			if intersection == 0 {
				continue
			}

			union := len(inputSet) + len(nameSet) - intersection

			var score float32
			switch {
			case intersection == len(nameSet):
				// Full name covered by the input; extra input words only
				// dilute slightly. Exact reordered match converges to 0.9.
				score = 0.85 + 0.05*float32(intersection)/float32(len(inputSet))
			case intersection == len(inputSet):
				// Input is a fragment of the name; scale by name coverage.
				score = 0.6 + 0.3*float32(intersection)/float32(len(nameSet))
			default:
				score = float32(intersection) / float32(union)
			}

			if score > bestScore {
				bestScore = score
			}
		}

		if bestScore > 0.0 {
			signals = append(signals, CandidateSignal{ExerciseID: ex.ID, Score: bestScore, Strategy: "token_set"})
		}
	}

	return signals
}

// jaccardMatch performs Jaccard similarity matching on token sets.
func (sr *StrategyRunner) jaccardMatch(inputTokens []string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	if len(inputTokens) == 0 {
		return signals
	}

	inputSet := makeTokenSet(inputTokens)

	for _, ex := range sr.exercises.Exercises {
		bestScore := float32(0.0)

		for _, name := range matchableNames(ex) {
			nameSet := makeTokenSet(strings.Fields(normalizeName(name)))

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
			signals = append(signals, CandidateSignal{ExerciseID: ex.ID, Score: bestScore, Strategy: "jaccard"})
		}
	}

	return signals
}

// phoneticMatch compares names token-by-token using Soundex. Whole-string
// Soundex only encodes the first few consonants, which collides wildly on
// multi-word names, so each token must match its positional counterpart.
func (sr *StrategyRunner) phoneticMatch(inputTokens []string) []CandidateSignal {
	signals := make([]CandidateSignal, 0)

	if len(inputTokens) == 0 {
		return signals
	}

	inputCodes := soundexTokens(inputTokens)

	for _, ex := range sr.exercises.Exercises {
		matched := false

		for _, name := range matchableNames(ex) {
			nameCodes := soundexTokens(strings.Fields(normalizeName(name)))
			if tokenCodesEqual(inputCodes, nameCodes) {
				matched = true
				break
			}
		}

		if matched {
			signals = append(signals, CandidateSignal{ExerciseID: ex.ID, Score: 0.85, Strategy: "phonetic"})
		}
	}

	return signals
}

// matchableNames returns all names an exercise can be matched against.
func matchableNames(ex config.ExerciseConfig) []string {
	names := make([]string, 0, 1+len(ex.Aliases))
	names = append(names, ex.CanonicalName)
	names = append(names, ex.Aliases...)
	return names
}

func normalizeName(s string) string {
	return strings.ToLower(strings.TrimSpace(s))
}

func maxf(a, b float32) float32 {
	if a > b {
		return a
	}
	return b
}

func makeTokenSet(tokens []string) map[string]bool {
	set := make(map[string]bool, len(tokens))
	for _, token := range tokens {
		set[token] = true
	}
	return set
}

func countIntersection(set1, set2 map[string]bool) int {
	count := 0
	for token := range set1 {
		if set2[token] {
			count++
		}
	}
	return count
}

func soundexTokens(tokens []string) []string {
	codes := make([]string, 0, len(tokens))
	for _, t := range tokens {
		codes = append(codes, soundex(t))
	}
	return codes
}

func tokenCodesEqual(a, b []string) bool {
	if len(a) != len(b) || len(a) == 0 {
		return false
	}
	for i := range a {
		if a[i] == "" || a[i] != b[i] {
			return false
		}
	}
	return true
}

// soundex implements a simplified Soundex algorithm for a single token.
func soundex(s string) string {
	var cleaned strings.Builder
	for _, r := range s {
		if r >= 'a' && r <= 'z' {
			cleaned.WriteRune(r - 32)
		} else if r >= 'A' && r <= 'Z' {
			cleaned.WriteRune(r)
		}
	}

	if cleaned.Len() == 0 {
		return ""
	}

	str := cleaned.String()
	code := make([]byte, 0, 4)
	code = append(code, str[0])

	prevCode := soundexDigit(str[0])
	for i := 1; i < len(str) && len(code) < 4; i++ {
		digit := soundexDigit(str[i])
		if digit != 0 && digit != prevCode {
			code = append(code, digit)
		}
		prevCode = digit
	}

	for len(code) < 4 {
		code = append(code, '0')
	}

	return string(code)
}

func soundexDigit(char byte) byte {
	switch char {
	case 'B', 'F', 'P', 'V':
		return '1'
	case 'C', 'G', 'J', 'K', 'Q', 'S', 'X', 'Z':
		return '2'
	case 'D', 'T':
		return '3'
	case 'L':
		return '4'
	case 'M', 'N':
		return '5'
	case 'R':
		return '6'
	default:
		return 0
	}
}
