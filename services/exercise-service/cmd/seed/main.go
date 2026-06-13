// Command seed initializes the graph schema/taxonomy and creates archetypal
// exercises from the curated vocabulary (config/exercises.json). Idempotent:
// re-running updates existing exercises in place.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/athleta/exercise-service/internal/config"
	"github.com/athleta/exercise-service/internal/graph"
	"github.com/athleta/exercise-service/internal/matcher"
	"github.com/athleta/exercise-service/internal/resolver"
	"github.com/athleta/exercise-service/internal/service"
)

func main() {
	ctx := context.Background()

	neo4jURI := getEnv("NEO4J_URI", "bolt://localhost:7687")
	neo4jUser := getEnv("NEO4J_USER", "neo4j")
	neo4jPassword := getEnv("NEO4J_PASSWORD", "password")
	configPath := getEnv("CONFIG_PATH", "./config")

	log.Println("Connecting to Neo4j...")
	repo, err := graph.NewRepository(neo4jURI, neo4jUser, neo4jPassword)
	if err != nil {
		log.Fatalf("Failed to connect to Neo4j: %v", err)
	}
	defer repo.Close(ctx)

	log.Println("Initializing graph schema and taxonomy...")
	if err := repo.InitSchema(ctx); err != nil {
		log.Fatalf("Failed to initialize graph schema: %v", err)
	}
	log.Println("✓ Schema and taxonomy ready")

	loader, err := config.NewLoader(
		fmt.Sprintf("%s/exercises.json", configPath),
		fmt.Sprintf("%s/scoring_weights.json", configPath),
	)
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}
	defer loader.Close()

	svc := service.New(repo, resolver.New(matcher.NewMatcher(loader)), loader)

	log.Println("Seeding vocabulary exercises...")
	count, err := svc.Seed(ctx)
	if err != nil {
		log.Fatalf("Seed failed: %v", err)
	}

	log.Printf("✓ Seed complete (%d exercises)", count)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
