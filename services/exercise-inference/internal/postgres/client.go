package postgres

import (
	"context"
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
)

// Client handles PostgreSQL operations
type Client struct {
	db *sql.DB
}

// NewClient creates a new PostgreSQL client
func NewClient(host, port, user, password, dbname string) (*Client, error) {
	connStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)
	
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}
	
	return &Client{db: db}, nil
}

// Close closes the database connection
func (c *Client) Close() error {
	return c.db.Close()
}

// Exercise represents an exercise from PostgreSQL
type Exercise struct {
	ID                int
	Name              string
	Equipment         string
	InjuryRiskLevel   float32
	JointStressAreas  []string
	MovementPattern   string
	ExerciseType      string
	ComplexityScore   float32
	IntensityCategory string
}

// ExerciseMuscle represents the exercise-muscle relationship
type ExerciseMuscle struct {
	ExerciseID    int
	MuscleGroupID int
	MuscleName    string
	Role          string
}

// GetAllExercises retrieves all exercises from PostgreSQL
func (c *Client) GetAllExercises(ctx context.Context) ([]Exercise, error) {
	query := `
		SELECT id, name, equipment, injury_risk_level, 
		       joint_stress_areas, movement_pattern, exercise_type,
		       complexity_score, intensity_category
		FROM exercises
		ORDER BY id
	`
	
	rows, err := c.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query exercises: %w", err)
	}
	defer rows.Close()
	
	var exercises []Exercise
	for rows.Next() {
		var ex Exercise
		var jointStress sql.NullString
		
		err := rows.Scan(
			&ex.ID,
			&ex.Name,
			&ex.Equipment,
			&ex.InjuryRiskLevel,
			&jointStress,
			&ex.MovementPattern,
			&ex.ExerciseType,
			&ex.ComplexityScore,
			&ex.IntensityCategory,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan exercise: %w", err)
		}
		
		// Parse joint stress areas (PostgreSQL array)
		// This is simplified - in production, use proper array parsing
		if jointStress.Valid {
			// TODO: Parse PostgreSQL array properly
			ex.JointStressAreas = []string{}
		}
		
		exercises = append(exercises, ex)
	}
	
	return exercises, nil
}

// GetExerciseMuscles retrieves muscle targets for an exercise
func (c *Client) GetExerciseMuscles(ctx context.Context, exerciseID int) ([]ExerciseMuscle, error) {
	query := `
		SELECT em.exercise_id, em.muscle_group_id, mg.name, em.role
		FROM exercise_muscles em
		JOIN muscle_groups mg ON em.muscle_group_id = mg.id
		WHERE em.exercise_id = $1
	`
	
	rows, err := c.db.QueryContext(ctx, query, exerciseID)
	if err != nil {
		return nil, fmt.Errorf("failed to query exercise muscles: %w", err)
	}
	defer rows.Close()
	
	var muscles []ExerciseMuscle
	for rows.Next() {
		var em ExerciseMuscle
		err := rows.Scan(&em.ExerciseID, &em.MuscleGroupID, &em.MuscleName, &em.Role)
		if err != nil {
			return nil, fmt.Errorf("failed to scan exercise muscle: %w", err)
		}
		muscles = append(muscles, em)
	}
	
	return muscles, nil
}

// GetMuscleGroups retrieves all muscle groups
func (c *Client) GetMuscleGroups(ctx context.Context) (map[int]string, error) {
	query := `SELECT id, name FROM muscle_groups`
	
	rows, err := c.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query muscle groups: %w", err)
	}
	defer rows.Close()
	
	muscles := make(map[int]string)
	for rows.Next() {
		var id int
		var name string
		if err := rows.Scan(&id, &name); err != nil {
			return nil, fmt.Errorf("failed to scan muscle group: %w", err)
		}
		muscles[id] = name
	}
	
	return muscles, nil
}

