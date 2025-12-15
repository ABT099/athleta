package grpc

import (
	"context"

	"github.com/athleta/exercise-inference/internal/inference"
	"github.com/athleta/exercise-inference/internal/models"
	pb "github.com/athleta/exercise-inference/proto"
)

// Service implements the ExerciseInferenceService gRPC service
type Service struct {
	pb.UnimplementedExerciseInferenceServiceServer
	engine *inference.Engine
}

// NewService creates a new gRPC service
func NewService(engine *inference.Engine) *Service {
	return &Service{
		engine: engine,
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
	// Infer the exercise
	result, err := s.engine.InferExercise(ctx, req.ExerciseName)
	if err != nil {
		return nil, err
	}

	return s.convertToProto(result), nil
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

