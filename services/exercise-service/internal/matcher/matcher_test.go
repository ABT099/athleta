package matcher

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/athleta/exercise-service/internal/config"
)

func TestGoldenSet(t *testing.T) {
	configPath := "../../config"
	loader, err := config.NewLoader(
		filepath.Join(configPath, "exercises.json"),
		filepath.Join(configPath, "scoring_weights.json"),
	)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}
	defer loader.Close()

	m := NewMatcher(loader)

	file, err := os.Open("../../testdata/golden_set.csv")
	if err != nil {
		t.Fatalf("Failed to open golden set: %v", err)
	}
	defer file.Close()

	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		t.Fatalf("Failed to read golden set: %v", err)
	}
	if len(records) < 2 {
		t.Fatal("Golden set must have at least a header and one test case")
	}
	records = records[1:]

	type categoryResult struct {
		total  int
		passed int
		failed []string
	}
	categoryResults := make(map[string]*categoryResult)

	totalTests := 0
	totalPassed := 0

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

		minConf, err := strconv.ParseFloat(minConfStr, 32)
		if err != nil {
			t.Logf("Invalid min confidence: %s", minConfStr)
			continue
		}

		result := m.Match(input)

		if categoryResults[category] == nil {
			categoryResults[category] = &categoryResult{}
		}
		cat := categoryResults[category]
		cat.total++
		totalTests++

		fail := func(format string, args ...any) {
			msg := fmt.Sprintf("Input %q: ", input) + fmt.Sprintf(format, args...)
			cat.failed = append(cat.failed, msg)
			t.Logf("FAIL: %s", msg)
		}

		if result.ResultType != expectedType {
			fail("expected type %s, got %s", expectedTypeStr, resultTypeToString(result.ResultType))
			continue
		}
		if float32(minConf) > result.Confidence {
			fail("confidence %.2f below minimum %.2f", result.Confidence, minConf)
			continue
		}
		if expectedType == ResultTypeMatch {
			if result.TopCandidate == nil {
				fail("expected MATCH but TopCandidate is nil")
				continue
			}
			if result.TopCandidate.ExerciseID != expectedID {
				fail("expected ID %s, got %s", expectedID, result.TopCandidate.ExerciseID)
				continue
			}
		}

		cat.passed++
		totalPassed++
	}

	t.Logf("\n=== Golden Set Test Results ===")
	t.Logf("Overall: %d/%d passed (%.2f%%)", totalPassed, totalTests, float64(totalPassed)/float64(totalTests)*100)
	for category, results := range categoryResults {
		t.Logf("  %s: %d/%d passed", category, results.passed, results.total)
		for _, failure := range results.failed {
			t.Logf("    - %s", failure)
		}
	}

	overallAccuracy := float64(totalPassed) / float64(totalTests) * 100
	if overallAccuracy < 95.0 {
		t.Fatalf("Overall accuracy %.2f%% is below required 95%%", overallAccuracy)
	}
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
