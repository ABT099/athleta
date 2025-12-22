package grpc

import (
	"context"
	"fmt"

	"github.com/athleta/exercise-inference/internal/inference"
	"github.com/athleta/exercise-inference/internal/matcher"
	"github.com/athleta/exercise-inference/internal/models"
	pb "github.com/athleta/exercise-inference/proto"
)

// Service implements the ExerciseInferenceService gRPC service
type Service struct {
	pb.UnimplementedExerciseInferenceServiceServer
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
func (s *Service) BatchParseExercises(ctx context.Context, req *pb.BatchParseRequest) (*pb.BatchExerciseData, error) {
	// Infer all exercises
	results, err := s.engine.BatchInferExercises(ctx, req.ExerciseNames)
	if err != nil {
		return nil, err
	}

	// Convert to protobuf format
	exercises := make([]*pb.ExerciseData, 0, len(results))
	for _, result := range results {
		exercises = append(exercises, s.convertToProto(result))
	}

	return &pb.BatchExerciseData{
		Exercises: exercises,
	}, nil
}

// ParseSingleExercise implements the ParseSingleExercise RPC
func (s *Service) ParseSingleExercise(ctx context.Context, req *pb.ParseRequest) (*pb.ExerciseData, error) {
	// Use new matcher to find exercise
	matchResult := s.matcher.Match(req.ExerciseName)
	
	// If we have a clear match, proceed with muscle inference
	if matchResult.ResultType == matcher.ResultTypeMatch && matchResult.TopCandidate != nil {
		// Use the canonical name for muscle inference
		exerciseData, err := s.engine.InferExercise(ctx, matchResult.TopCandidate.CanonicalName)
		if err != nil {
			return nil, err
		}
		return s.convertToProto(exerciseData), nil
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
func (s *Service) ParseExerciseWithMatching(ctx context.Context, req *pb.ParseRequest) (*pb.ParseResponse, error) {
	// Use matcher to find exercise
	matchResult := s.matcher.Match(req.ExerciseName)
	
	// Convert to protobuf
	response := &pb.ParseResponse{
		ResultType:     s.convertResultType(matchResult.ResultType),
		NormalizedInput: req.ExerciseName, // Could be enhanced with actual normalized input
	}
	
	// Add top match if available
	if matchResult.TopCandidate != nil {
		response.TopMatch = &pb.MatchCandidate{
			ExerciseId:    matchResult.TopCandidate.ExerciseID,
			CanonicalName: matchResult.TopCandidate.CanonicalName,
			Confidence:    matchResult.TopCandidate.Score,
			MatchMethod:   matchResult.TopCandidate.MatchMethod,
			MuscleGroups:  matchResult.TopCandidate.MuscleGroups,
		}
	}
	
	// Add candidates if available
	if len(matchResult.Candidates) > 0 {
		response.Candidates = make([]*pb.MatchCandidate, 0, len(matchResult.Candidates))
		for _, cand := range matchResult.Candidates {
			response.Candidates = append(response.Candidates, &pb.MatchCandidate{
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
func (s *Service) convertResultType(rt matcher.ResultType) pb.ResultType {
	switch rt {
	case matcher.ResultTypeMatch:
		return pb.ResultType_MATCH
	case matcher.ResultTypeAmbiguous:
		return pb.ResultType_AMBIGUOUS
	case matcher.ResultTypeLowConfidence:
		return pb.ResultType_LOW_CONFIDENCE
	case matcher.ResultTypeNoMatch:
		return pb.ResultType_NO_MATCH
	default:
		return pb.ResultType_NO_MATCH
	}
}

// FindSimilarExercises implements the FindSimilarExercises RPC
func (s *Service) FindSimilarExercises(ctx context.Context, req *pb.SimilarityRequest) (*pb.SimilarityResponse, error) {
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

	return &pb.SimilarityResponse{
		ExerciseNames: similarExercises,
	}, nil
}

// convertToProto converts internal ExerciseData to protobuf ExerciseData
func (s *Service) convertToProto(data *models.ExerciseData) *pb.ExerciseData {
	// Convert muscle targets
	muscles := make([]*pb.MuscleTarget, 0, len(data.MuscleTargets))
	for _, m := range data.MuscleTargets {
		muscles = append(muscles, &pb.MuscleTarget{
			MuscleName: m.MuscleName,
			Role:       m.Role,
		})
	}

	// Convert modifiers
	modifiers := &pb.ExerciseModifiers{
		Implement:  data.Modifiers.Implement,
		Laterality: data.Modifiers.Laterality,
		Angle:      data.Modifiers.Angle,
		GripStance: data.Modifiers.GripStance,
		Plane:      data.Modifiers.Plane,
		Tempo:      data.Modifiers.Tempo,
	}

	return &pb.ExerciseData{
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

