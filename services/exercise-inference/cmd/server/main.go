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
	"google.golang.org/grpc/reflection"

	grpcService "github.com/athleta/exercise-inference/internal/grpc"
	"github.com/athleta/exercise-inference/internal/inference"
	"github.com/athleta/exercise-inference/internal/neo4j"
	pb "github.com/athleta/exercise-inference/proto"
)

func main() {
	ctx := context.Background()

	// Get configuration from environment
	neo4jURI := getEnv("NEO4J_URI", "bolt://localhost:7687")
	neo4jUser := getEnv("NEO4J_USER", "neo4j")
	neo4jPassword := getEnv("NEO4J_PASSWORD", "password")
	grpcPort := getEnv("GRPC_PORT", "50051")

	log.Println("Starting Exercise Inference Service...")
	log.Printf("Neo4j URI: %s", neo4jURI)
	log.Printf("gRPC Port: %s", grpcPort)

	// Connect to Neo4j
	log.Println("Connecting to Neo4j...")
	neo4jRepo, err := neo4j.NewRepository(neo4jURI, neo4jUser, neo4jPassword)
	if err != nil {
		log.Fatalf("Failed to connect to Neo4j: %v", err)
	}
	defer neo4jRepo.Close(ctx)
	log.Println("✓ Connected to Neo4j")

	// Initialize schema (idempotent)
	log.Println("Initializing Neo4j schema...")
	if err := neo4jRepo.InitSchema(ctx); err != nil {
		log.Printf("Warning: Failed to initialize schema (may already exist): %v", err)
	} else {
		log.Println("✓ Neo4j schema ready")
	}

	// Create inference engine
	engine := inference.NewEngine(neo4jRepo)
	log.Println("✓ Inference engine initialized")

	// Create gRPC service
	service := grpcService.NewService(engine)

	// Create gRPC server
	grpcServer := grpc.NewServer()
	pb.RegisterExerciseInferenceServiceServer(grpcServer, service)

	// Register reflection service (for debugging with grpcurl)
	reflection.Register(grpcServer)

	// Start listening
	listener, err := net.Listen("tcp", fmt.Sprintf(":%s", grpcPort))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	// Handle graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan

		log.Println("\nShutting down gracefully...")
		grpcServer.GracefulStop()
		log.Println("✓ Server stopped")
	}()

	// Start serving
	log.Printf("✓ gRPC server listening on :%s", grpcPort)
	log.Println("Service ready to accept requests")
	
	if err := grpcServer.Serve(listener); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

