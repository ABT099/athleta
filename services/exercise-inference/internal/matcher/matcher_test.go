package matcher

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/athleta/exercise-inference/internal/config"
)

func TestGoldenSet(t *testing.T) {
	// Load config
	configPath := "../../config"
	exercisesPath := filepath.Join(configPath, "exercises.json")
	scoringWeightsPath := filepath.Join(configPath, "scoring_weights.json")
	
	loader, err := config.NewLoader(exercisesPath, scoringWeightsPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}
	defer loader.Close()
	
	// Create matcher
	m := NewMatcher(loader)
	
	// Load golden set
	goldenSetPath := "../../testdata/golden_set.csv"
	file, err := os.Open(goldenSetPath)
	if err != nil {
		t.Fatalf("Failed to open golden set: %v", err)
	}
	defer file.Close()
	
	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		t.Fatalf("Failed to read golden set: %v", err)
	}
	
	if len(records) < 2 {
		t.Fatal("Golden set must have at least a header and one test case")
	}
	
	// Skip header
	records = records[1:]
	
	// Track results by category
	categoryResults := make(map[string]struct {
		total   int
		passed  int
		failed  []string
	})
	
	totalTests := 0
	totalPassed := 0
	
	// Run tests
	for _, record := range records {
		if len(record) < 5 {
			t.Logf("Skipping invalid record: %v", record)
			continue
		}
		
		input := record[0]
		expectedID := record[1]
		expectedTypeStr := record[2]
		minConfStr := record[3]
		category := record[4]
		
		// Parse expected result type
		var expectedType ResultType
		switch expectedTypeStr {
		case "MATCH":
			expectedType = ResultTypeMatch
		case "AMBIGUOUS":
			expectedType = ResultTypeAmbiguous
		case "LOW_CONFIDENCE":
			expectedType = ResultTypeLowConfidence
		case "NO_MATCH":
			expectedType = ResultTypeNoMatch
		default:
			t.Logf("Unknown result type: %s", expectedTypeStr)
			continue
		}
		
		// Parse min confidence
		minConf, err := strconv.ParseFloat(minConfStr, 32)
		if err != nil {
			t.Logf("Invalid min confidence: %s", minConfStr)
			continue
		}
		
		// Run matcher
		result := m.Match(input)
		
		// Initialize category tracking
		if _, exists := categoryResults[category]; !exists {
			categoryResults[category] = struct {
				total   int
				passed  int
				failed  []string
			}{failed: []string{}}
		}
		
		cat := categoryResults[category]
		cat.total++
		totalTests++
		
		// Check result type
		if result.ResultType != expectedType {
			failMsg := fmt.Sprintf("Input '%s': expected type %s, got %s", input, expectedTypeStr, resultTypeToString(result.ResultType))
			cat.failed = append(cat.failed, failMsg)
			t.Logf("FAIL: %s", failMsg)
			continue
		}
		
		// Check confidence
		if float32(minConf) > result.Confidence {
			failMsg := fmt.Sprintf("Input '%s': confidence %.2f below minimum %.2f", input, result.Confidence, minConf)
			cat.failed = append(cat.failed, failMsg)
			t.Logf("FAIL: %s", failMsg)
			continue
		}
		
		// For MATCH, check exercise ID
		if expectedType == ResultTypeMatch {
			if result.TopCandidate == nil {
				failMsg := fmt.Sprintf("Input '%s': expected MATCH but TopCandidate is nil", input)
				cat.failed = append(cat.failed, failMsg)
				t.Logf("FAIL: %s", failMsg)
				continue
			}
			
			if result.TopCandidate.ExerciseID != expectedID {
				failMsg := fmt.Sprintf("Input '%s': expected ID %s, got %s", input, expectedID, result.TopCandidate.ExerciseID)
				cat.failed = append(cat.failed, failMsg)
				t.Logf("FAIL: %s", failMsg)
				continue
			}
		}
		
		// Test passed
		cat.passed++
		totalPassed++
		categoryResults[category] = cat
	}
	
	// Print results
	t.Logf("\n=== Golden Set Test Results ===")
	t.Logf("Overall: %d/%d passed (%.2f%%)", totalPassed, totalTests, float64(totalPassed)/float64(totalTests)*100)
	t.Logf("\nPer-Category Breakdown:")
	
	for category, results := range categoryResults {
		accuracy := float64(results.passed) / float64(results.total) * 100
		t.Logf("  %s: %d/%d passed (%.2f%%)", category, results.passed, results.total, accuracy)
		if len(results.failed) > 0 {
			for _, fail := range results.failed {
				t.Logf("    - %s", fail)
			}
		}
	}
	
	// Check overall accuracy threshold (95%)
	overallAccuracy := float64(totalPassed) / float64(totalTests) * 100
	if overallAccuracy < 95.0 {
		t.Fatalf("Overall accuracy %.2f%% is below required 95%%", overallAccuracy)
	}
	
	t.Logf("\n✓ All tests passed with %.2f%% accuracy", overallAccuracy)
}

func resultTypeToString(rt ResultType) string {
	switch rt {
	case ResultTypeMatch:
		return "MATCH"
	case ResultTypeAmbiguous:
		return "AMBIGUOUS"
	case ResultTypeLowConfidence:
		return "LOW_CONFIDENCE"
	case ResultTypeNoMatch:
		return "NO_MATCH"
	default:
		return "UNKNOWN"
	}
}


