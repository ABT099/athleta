# Exercise Inference Service

A high-performance Go microservice that provides intelligent exercise parsing and biomechanical inference using Neo4j graph database.

## Architecture

- **gRPC API**: Internal service communication
- **Neo4j**: Stores movement pattern hierarchy and exercise DNA
- **PostgreSQL**: Reads muscle group data for inference

## Features

- **Automatic Exercise Parsing**: Extracts modifiers from exercise names (e.g., "Single Arm Dumbbell Press")
- **Biomechanical Inference**: Automatically determines muscle targets with roles (prime_mover, synergist, stabilizer)
- **Safety Metadata Generation**: Auto-generates injury_risk_level, complexity_score, joint_stress_areas, intensity_category
- **Hierarchical Knowledge**: Exercises inherit properties from archetypal parents

## Project Structure

```
cmd/
  server/       - gRPC server entry point
  migrate/      - Data migration tool
internal/
  grpc/         - gRPC service handlers
  inference/    - Parsing and inference logic
  neo4j/        - Neo4j repository layer
  postgres/     - PostgreSQL client
  models/       - Domain models
proto/          - Protocol buffer definitions
```

## Development

### Prerequisites

- Go 1.21+
- Docker & Docker Compose
- Protocol Buffer Compiler (protoc)

### Build

```bash
go mod download
go build -o bin/server ./cmd/server
```

### Run with Docker

```bash
docker-compose up exercise-inference
```

## Environment Variables

- `NEO4J_URI`: Neo4j connection URI (default: bolt://neo4j:7687)
- `NEO4J_USER`: Neo4j username (default: neo4j)
- `NEO4J_PASSWORD`: Neo4j password
- `POSTGRES_HOST`: PostgreSQL host
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `POSTGRES_USER`: PostgreSQL username
- `POSTGRES_PASSWORD`: PostgreSQL password
- `POSTGRES_DB`: PostgreSQL database name
- `GRPC_PORT`: gRPC server port (default: 50051)

## gRPC API

### BatchParseExercises

Parses multiple exercise names and returns complete biomechanical profiles.

**Request:**

```protobuf
message BatchParseRequest {
  repeated string exercise_names = 1;
}
```

**Response:**

```protobuf
message BatchExerciseData {
  repeated ExerciseData exercises = 1;
}
```

### ParseSingleExercise

Parses a single exercise name.

## Movement Patterns

The system organizes exercises into 7 primal movement patterns:

1. **Squat** - Knee-dominant lower body
2. **Hinge** - Hip-dominant lower body
3. **Push** - Horizontal/Vertical pressing
4. **Pull** - Horizontal/Vertical pulling
5. **Lunge** - Unilateral leg movements
6. **Carry** - Locomotion and loaded carries
7. **Rotation** - Core stability and rotation

## Modifier System

Exercises are tagged with modifiers that affect inference:

- **Implement**: barbell, dumbbell, kettlebell, cable, machine, bodyweight, landmine, band
- **Laterality**: bilateral, unilateral, alternating, isometric_hold
- **Angle**: flat, incline, decline, overhead, floor_level
- **Grip/Stance**: neutral, pronated, supinated, wide, narrow
- **Plane**: sagittal, frontal, transverse
- **Tempo**: eccentric_focus, explosive, tempo, pause

## License

Proprietary - Athleta
