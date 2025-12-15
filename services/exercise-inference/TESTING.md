# Exercise Inference System - Testing Guide

## Overview

This guide covers testing the exercise inference system, including parser accuracy, safety metrics generation, and end-to-end integration.

## Prerequisites

- Docker and Docker Compose installed
- All services running (`docker-compose up`)
- PostgreSQL seeded with muscle groups
- Neo4j initialized with schema

## Test Categories

### 1. Parser Accuracy Tests

Test the NLP parser's ability to extract modifiers from exercise names.

#### Test Cases

| Exercise Name               | Expected Pattern | Expected Implement | Expected Laterality | Expected Angle |
| --------------------------- | ---------------- | ------------------ | ------------------- | -------------- |
| "Barbell Bench Press"       | push             | barbell            | bilateral           | flat           |
| "Incline Dumbbell Press"    | push             | dumbbell           | bilateral           | incline        |
| "Single Arm Cable Row"      | pull             | cable              | unilateral          | -              |
| "Paused Barbell Back Squat" | squat            | barbell            | bilateral           | -              |
| "Single Arm Landmine Press" | push             | landmine           | unilateral          | -              |
| "Cable Gorilla Row"         | pull             | cable              | alternating         | -              |
| "Overhead Press"            | push             | -                  | bilateral           | overhead       |
| "Romanian Deadlift"         | hinge            | -                  | bilateral           | -              |

### 2. Muscle Inference Tests

Verify that muscle targets are correctly inferred based on movement patterns.

#### Test Cases

**Horizontal Push (Bench Press)**

- Expected Prime Movers: mid_chest
- Expected Synergists: anterior_delt, triceps
- Expected Stabilizers: abs

**Vertical Push (Overhead Press)**

- Expected Prime Movers: anterior_delt, lateral_delt
- Expected Synergists: triceps, upper_chest

**Horizontal Pull (Row)**

- Expected Prime Movers: mid_back, lats
- Expected Synergists: posterior_delt, biceps
- Expected Stabilizers: erector_spinae, abs

**Squat Pattern**

- Expected Prime Movers: quadriceps, glutes
- Expected Synergists: hamstrings
- Expected Stabilizers: erector_spinae, abs, calves

### 3. Safety Metrics Tests

Verify auto-generated safety and difficulty metrics.

#### Test Cases

| Exercise               | Expected Injury Risk | Expected Complexity | Expected Intensity |
| ---------------------- | -------------------- | ------------------- | ------------------ |
| "Barbell Deadlift"     | 3.0 (high)           | 0.8                 | compound_heavy     |
| "Dumbbell Bench Press" | 2.0 (medium)         | 0.6                 | compound_moderate  |
| "Machine Chest Press"  | 1.5 (low)            | 0.4                 | compound_moderate  |
| "Cable Fly"            | 1.0 (low)            | 0.3                 | isolation          |
| "Overhead Press"       | 2.5 (medium-high)    | 0.7                 | compound_heavy     |

### 4. Joint Stress Inference Tests

Verify correct joint stress area identification.

#### Test Cases

| Exercise Pattern  | Expected Joint Stress |
| ----------------- | --------------------- |
| Push (horizontal) | shoulder, elbow       |
| Push (overhead)   | shoulder, elbow       |
| Pull              | shoulder, elbow       |
| Squat             | knee, hip, lower_back |
| Hinge             | lower_back, hip, knee |
| Lunge             | knee, hip, ankle      |

## Running Tests

### Manual Testing with gRPCurl

```bash
# Test single exercise parsing
grpcurl -plaintext -d '{"exercise_name": "Barbell Bench Press"}' \
  localhost:50051 inference.ExerciseInferenceService/ParseSingleExercise

# Test batch parsing
grpcurl -plaintext -d '{"exercise_names": ["Barbell Bench Press", "Single Arm Cable Row", "Paused Squat"]}' \
  localhost:50051 inference.ExerciseInferenceService/BatchParseExercises
```

### Integration Testing

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait for services to be healthy
docker-compose ps

# 3. Run migration to populate Neo4j
docker-compose exec exercise-inference ./bin/migrate

# 4. Test inference via NestJS (when workout is created)
curl -X POST http://localhost:3000/api/workouts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "exercises": [
      {"name": "Single Arm Landmine Press", "sets": 3, "reps": 10},
      {"name": "Cable Gorilla Row", "sets": 3, "reps": 12}
    ]
  }'
```

## Validation Checklist

### ✅ Parser Validation

- [ ] Correctly extracts implement keywords (barbell, dumbbell, etc.)
- [ ] Correctly identifies laterality (unilateral, bilateral, alternating)
- [ ] Correctly identifies angles (incline, decline, overhead)
- [ ] Correctly identifies tempo modifiers (paused, explosive)
- [ ] Correctly identifies movement pattern from verbs

### ✅ Inference Validation

- [ ] Push exercises target chest/shoulders/triceps
- [ ] Pull exercises target back/biceps
- [ ] Squat exercises target quads/glutes
- [ ] Hinge exercises target glutes/hamstrings/erector_spinae
- [ ] Unilateral exercises add core stabilizers

### ✅ Safety Metrics Validation

- [ ] Heavy barbell compounds have high injury risk (2.5-3.0)
- [ ] Machines have lower injury risk (1.0-1.5)
- [ ] Complex movements have high complexity score (0.7-1.0)
- [ ] Isolation movements have low complexity (0.3-0.5)
- [ ] Correct intensity categories assigned

### ✅ Integration Validation

- [ ] gRPC service responds to requests
- [ ] NestJS successfully calls gRPC service
- [ ] Exercises are correctly upserted to PostgreSQL
- [ ] Muscle relationships are correctly created
- [ ] No duplicate exercises created

## Known Limitations

1. **Parser Limitations:**

   - May not recognize very obscure exercise variations
   - Relies on keyword matching (not true NLP)
   - May misclassify exercises with ambiguous names

2. **Inference Limitations:**

   - Uses rule-based inference (not ML)
   - May not capture individual biomechanical variations
   - Muscle roles are generalized

3. **Safety Metrics Limitations:**
   - Based on general patterns, not individual risk
   - Does not account for user experience level
   - Joint stress is pattern-based, not load-based

## Future Improvements

1. Add machine learning model for exercise classification
2. Implement user-specific risk adjustment
3. Add exercise similarity scoring
4. Implement custom exercise templates
5. Add video/image analysis for form validation

## Troubleshooting

### gRPC Service Not Responding

```bash
# Check if service is running
docker-compose ps exercise-inference

# Check logs
docker-compose logs exercise-inference

# Verify Neo4j connection
docker-compose logs neo4j
```

### Inference Errors

```bash
# Check Go service logs
docker-compose logs -f exercise-inference

# Verify Neo4j schema
docker-compose exec neo4j cypher-shell -u neo4j -p password "MATCH (p:Pattern) RETURN p"
```

### Database Issues

```bash
# Check PostgreSQL connection
docker-compose exec db psql -U postgres -d athleta -c "SELECT COUNT(*) FROM exercises"

# Check muscle groups exist
docker-compose exec db psql -U postgres -d athleta -c "SELECT COUNT(*) FROM muscle_groups"
```

## Success Criteria

The system is considered working correctly if:

1. ✅ Parser correctly identifies modifiers in 90%+ of test cases
2. ✅ Muscle inference matches expected targets for all major patterns
3. ✅ Safety metrics fall within expected ranges
4. ✅ gRPC service responds within 10ms for single exercise
5. ✅ Batch parsing handles 50+ exercises without errors
6. ✅ NestJS integration successfully upserts exercises
7. ✅ No duplicate exercises created in database
8. ✅ All muscle relationships correctly established
