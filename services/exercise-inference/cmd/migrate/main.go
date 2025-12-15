package main

import (
	"context"
	"log"
	"os"

	"github.com/athleta/exercise-inference/internal/models"
	"github.com/athleta/exercise-inference/internal/neo4j"
	"github.com/athleta/exercise-inference/internal/postgres"
)

func main() {
	ctx := context.Background()

	// Get environment variables
	neo4jURI := getEnv("NEO4J_URI", "bolt://localhost:7687")
	neo4jUser := getEnv("NEO4J_USER", "neo4j")
	neo4jPassword := getEnv("NEO4J_PASSWORD", "password")

	postgresHost := getEnv("POSTGRES_HOST", "localhost")
	postgresPort := getEnv("POSTGRES_PORT", "5432")
	postgresUser := getEnv("POSTGRES_USER", "postgres")
	postgresPassword := getEnv("POSTGRES_PASSWORD", "")
	postgresDB := getEnv("POSTGRES_DB", "athleta")

	log.Println("Starting exercise migration...")

	// Connect to Neo4j
	log.Println("Connecting to Neo4j...")
	neo4jRepo, err := neo4j.NewRepository(neo4jURI, neo4jUser, neo4jPassword)
	if err != nil {
		log.Fatalf("Failed to connect to Neo4j: %v", err)
	}
	defer neo4jRepo.Close(ctx)

	// Initialize Neo4j schema
	log.Println("Initializing Neo4j schema...")
	if err := neo4jRepo.InitSchema(ctx); err != nil {
		log.Fatalf("Failed to initialize Neo4j schema: %v", err)
	}
	log.Println("✓ Neo4j schema initialized")

	// Connect to PostgreSQL
	log.Println("Connecting to PostgreSQL...")
	pgClient, err := postgres.NewClient(postgresHost, postgresPort, postgresUser, postgresPassword, postgresDB)
	if err != nil {
		log.Fatalf("Failed to connect to PostgreSQL: %v", err)
	}
	defer pgClient.Close()
	log.Println("✓ Connected to PostgreSQL")

	// Get all exercises from PostgreSQL
	log.Println("Fetching exercises from PostgreSQL...")
	exercises, err := pgClient.GetAllExercises(ctx)
	if err != nil {
		log.Fatalf("Failed to get exercises: %v", err)
	}
	log.Printf("✓ Found %d exercises\n", len(exercises))

	// Migrate each exercise to Neo4j
	successCount := 0
	for _, ex := range exercises {
		log.Printf("Migrating: %s", ex.Name)

		// Get muscle targets
		muscles, err := pgClient.GetExerciseMuscles(ctx, ex.ID)
		if err != nil {
			log.Printf("  ✗ Failed to get muscles: %v", err)
			continue
		}

		// Convert to Neo4j format
		muscleTargets := make([]models.MuscleTarget, 0, len(muscles))
		for _, m := range muscles {
			muscleTargets = append(muscleTargets, models.MuscleTarget{
				MuscleName: m.MuscleName,
				Role:       m.Role,
			})
		}

		// Create exercise node
		exerciseNode := &models.ExerciseNode{
			Name:            ex.Name,
			PostgresID:      ex.ID,
			Equipment:       ex.Equipment,
			MovementPattern: ex.MovementPattern,
			ExerciseType:    ex.ExerciseType,
			MuscleTargets:   muscleTargets,
			Archetypal:      true, // Mark as archetypal
		}

		// Create in Neo4j
		if err := neo4jRepo.CreateArchetypalExercise(ctx, exerciseNode); err != nil {
			log.Printf("  ✗ Failed to create in Neo4j: %v", err)
			continue
		}

		log.Printf("  ✓ Migrated successfully (pattern: %s, muscles: %d)", ex.MovementPattern, len(muscleTargets))
		successCount++
	}

	log.Printf("\n=== Migration Complete ===")
	log.Printf("Total exercises: %d", len(exercises))
	log.Printf("Successfully migrated: %d", successCount)
	log.Printf("Failed: %d", len(exercises)-successCount)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}



