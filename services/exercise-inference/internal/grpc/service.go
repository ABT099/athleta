package grpc

import (
	"context"
	"fmt"

	inferencev1 "github.com/athleta/exercise-inference/inference/v1"
	"github.com/athleta/exercise-inference/internal/inference"
	"github.com/athleta/exercise-inference/internal/matcher"
	"github.com/athleta/exercise-inference/internal/models"
)

// Service implements the ExerciseInferenceService gRPC service
type Service struct {
	inferencev1.UnimplementedExerciseInferenceServiceServer
	engine  *inference.Engine
	matcher *matcher.Matcher
}

// NewService creates a new gRPC service
func NewService(engine *inference.Engine, matcher *matcher.Matcher) *Service {
	return &Service{
		engine:  engine,
		matcher: matcher,
	}
}

// BatchParseExercises implements the BatchParseExercises RPC
func (s *Service) BatchParseExercises(ctx context.Context, req *inferencev1.BatchParseExercisesRequest) (*inferencev1.BatchParseExercisesResponse, error) {
	// Infer all exercises
	results, err := s.engine.BatchInferExercises(ctx, req.ExerciseNames)
	if err != nil {
		return nil, err
	}

	// Convert to protobuf format
	exercises := make([]*inferencev1.ExerciseData, 0, len(results))
	for _, result := range results {
		exercises = append(exercises, s.convertToProto(result))
	}

	return &inferencev1.BatchParseExercisesResponse{
		Exercises: exercises,
	}, nil
}

// ParseSingleExercise implements the ParseSingleExercise RPC
func (s *Service) ParseSingleExercise(ctx context.Context, req *inferencev1.ParseSingleExerciseRequest) (*inferencev1.ParseSingleExerciseResponse, error) {
	// Use new matcher to find exercise
	matchResult := s.matcher.Match(req.ExerciseName)

	// If we have a clear match, proceed with muscle inference
	if matchResult.ResultType == matcher.ResultTypeMatch && matchResult.TopCandidate != nil {
		// Use the canonical name for muscle inference
		exerciseData, err := s.engine.InferExercise(ctx, matchResult.TopCandidate.CanonicalName)
		if err != nil {
			return nil, err
		}
		return &inferencev1.ParseSingleExerciseResponse{
			ExerciseData: s.convertToProto(exerciseData),
		}, nil
	}

	// For ambiguous, low confidence, or no match, return an error with details
	// In a real implementation, you might want to return a ParseResponse instead
	// For now, we'll return an error that can be handled by the client
	if matchResult.ResultType == matcher.ResultTypeAmbiguous {
		return nil, fmt.Errorf("ambiguous match: multiple candidates found for '%s'", req.ExerciseName)
	}
	if matchResult.ResultType == matcher.ResultTypeLowConfidence {
		return nil, fmt.Errorf("low confidence match for '%s'", req.ExerciseName)
	}

	return nil, fmt.Errorf("no match found for '%s'", req.ExerciseName)
}

// ParseExerciseWithMatching implements a new RPC that returns ParseResponse with matching details
func (s *Service) ParseExerciseWithMatching(ctx context.Context, req *inferencev1.ParseExerciseWithMatchingRequest) (*inferencev1.ParseExerciseWithMatchingResponse, error) {
	// Use matcher to find exercise
	matchResult := s.matcher.Match(req.ExerciseName)

	// Convert to protobuf
	response := &inferencev1.ParseExerciseWithMatchingResponse{
		ResultType:      s.convertResultType(matchResult.ResultType),
		NormalizedInput: req.ExerciseName, // Could be enhanced with actual normalized input
	}

	// Add top match if available
	if matchResult.TopCandidate != nil {
		response.TopMatch = &inferencev1.MatchCandidate{
			ExerciseId:    matchResult.TopCandidate.ExerciseID,
			CanonicalName: matchResult.TopCandidate.CanonicalName,
			Confidence:    matchResult.TopCandidate.Score,
			MatchMethod:   matchResult.TopCandidate.MatchMethod,
			MuscleGroups:  matchResult.TopCandidate.MuscleGroups,
		}
	}

	// Add candidates if available
	if len(matchResult.Candidates) > 0 {
		response.Candidates = make([]*inferencev1.MatchCandidate, 0, len(matchResult.Candidates))
		for _, cand := range matchResult.Candidates {
			response.Candidates = append(response.Candidates, &inferencev1.MatchCandidate{
				ExerciseId:    cand.ExerciseID,
				CanonicalName: cand.CanonicalName,
				Confidence:    cand.Score,
				MatchMethod:   cand.MatchMethod,
				MuscleGroups:  cand.MuscleGroups,
			})
		}
	}

	return response, nil
}

// convertResultType converts matcher ResultType to proto ResultType
func (s *Service) convertResultType(rt matcher.ResultType) inferencev1.ResultType {
	switch rt {
	case matcher.ResultTypeMatch:
		return inferencev1.ResultType_RESULT_TYPE_MATCH
	case matcher.ResultTypeAmbiguous:
		return inferencev1.ResultType_RESULT_TYPE_AMBIGUOUS
	case matcher.ResultTypeLowConfidence:
		return inferencev1.ResultType_RESULT_TYPE_LOW_CONFIDENCE
	case matcher.ResultTypeNoMatch:
		return inferencev1.ResultType_RESULT_TYPE_NO_MATCH
	default:
		return inferencev1.ResultType_RESULT_TYPE_NO_MATCH
	}
}

// FindSimilarExercises implements the FindSimilarExercises RPC
func (s *Service) FindSimilarExercises(ctx context.Context, req *inferencev1.FindSimilarExercisesRequest) (*inferencev1.FindSimilarExercisesResponse, error) {
	// Find similar exercises using the inference engine
	similarExercises, err := s.engine.FindSimilarExercises(ctx, req.ExerciseName, inference.SimilarityFilters{
		SameEquipment:  req.SameEquipment,
		SameLaterality: req.SameLaterality,
		SameAngle:      req.SameAngle,
		Limit:          req.Limit,
	})
	if err != nil {
		return nil, err
	}

	return &inferencev1.FindSimilarExercisesResponse{
		ExerciseNames: similarExercises,
	}, nil
}

// convertToProto converts internal ExerciseData to protobuf ExerciseData
func (s *Service) convertToProto(data *models.ExerciseData) *inferencev1.ExerciseData {
	// Convert muscle targets
	muscles := make([]*inferencev1.MuscleTarget, 0, len(data.MuscleTargets))
	for _, m := range data.MuscleTargets {
		muscles = append(muscles, &inferencev1.MuscleTarget{
			MuscleName: m.MuscleName,
			Role:       m.Role,
		})
	}

	// Convert modifiers
	modifiers := &inferencev1.ExerciseModifiers{
		Implement:  data.Modifiers.Implement,
		Laterality: data.Modifiers.Laterality,
		Angle:      data.Modifiers.Angle,
		GripStance: data.Modifiers.GripStance,
		Plane:      data.Modifiers.Plane,
		Tempo:      data.Modifiers.Tempo,
	}

	return &inferencev1.ExerciseData{
		Name:              data.Name,
		Equipment:         data.Equipment,
		MovementPattern:   data.MovementPattern,
		ExerciseType:      data.ExerciseType,
		InjuryRiskLevel:   data.InjuryRiskLevel,
		ComplexityScore:   data.ComplexityScore,
		JointStressAreas:  data.JointStressAreas,
		IntensityCategory: data.IntensityCategory,
		MuscleTargets:     muscles,
		Modifiers:         modifiers,
	}
}
