package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"

	exercisev1 "github.com/athleta/exercise-service/gen/exercise/v1"
	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/graph"
	grpcServer "github.com/athleta/exercise-service/internal/grpc"
	"github.com/athleta/exercise-service/internal/matcher"
	"github.com/athleta/exercise-service/internal/resolver"
	"github.com/athleta/exercise-service/internal/service"
)

func main() {
	ctx := context.Background()

	neo4jURI := getEnv("NEO4J_URI", "bolt://localhost:7687")
	neo4jUser := getEnv("NEO4J_USER", "neo4j")
	neo4jPassword := getEnv("NEO4J_PASSWORD", "password")
	grpcPort := getEnv("GRPC_PORT", "50051")
	configPath := getEnv("CONFIG_PATH", "./config")

	log.Println("Starting Exercise Service...")
	log.Printf("Neo4j URI: %s", neo4jURI)
	log.Printf("gRPC Port: %s", grpcPort)

	log.Println("Connecting to Neo4j...")
	repo, err := graph.NewRepository(neo4jURI, neo4jUser, neo4jPassword)
	if err != nil {
		log.Fatalf("Failed to connect to Neo4j: %v", err)
	}
	defer repo.Close(ctx)
	log.Println("✓ Connected to Neo4j")

	log.Println("Initializing graph schema and taxonomy...")
	if err := repo.InitSchema(ctx); err != nil {
		log.Fatalf("Failed to initialize graph schema: %v", err)
	}
	log.Println("✓ Graph schema ready")

	log.Println("Loading configuration...")
	loader, err := config.NewLoader(
		fmt.Sprintf("%s/exercises.json", configPath),
		fmt.Sprintf("%s/scoring_weights.json", configPath),
	)
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}
	defer loader.Close()
	log.Println("✓ Configuration loaded")

	exerciseResolver := resolver.New(matcher.NewMatcher(loader))
	domainService := service.New(repo, exerciseResolver, loader)

	server := grpc.NewServer()
	exercisev1.RegisterExerciseServiceServer(server, grpcServer.NewServer(domainService))

	healthServer := health.NewServer()
	grpc_health_v1.RegisterHealthServer(server, healthServer)
	healthServer.SetServingStatus("", grpc_health_v1.HealthCheckResponse_SERVING)
	healthServer.SetServingStatus("exercise.v1.ExerciseService", grpc_health_v1.HealthCheckResponse_SERVING)

	reflection.Register(server)

	listener, err := net.Listen("tcp", fmt.Sprintf(":%s", grpcPort))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan

		log.Println("\nShutting down gracefully...")
		healthServer.SetServingStatus("", grpc_health_v1.HealthCheckResponse_NOT_SERVING)
		server.GracefulStop()
		log.Println("✓ Server stopped")
	}()

	log.Printf("✓ gRPC server listening on :%s", grpcPort)
	if err := server.Serve(listener); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
