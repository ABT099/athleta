# AthleteAI API Documentation

## Workout Endpoints

### Complete Workout (Main AI Endpoint)

Submit completed workout and receive AI-generated next workout with progressive overload adjustments.

**Endpoint:** `POST /api/workouts/complete`

**Request Body:**

```json
{
  "athlete_id": 1,
  "workout_day_id": 1,
  "session_date": "2024-01-15T10:00:00",
  "duration_minutes": 60,
  "exercise_sets": [
    {
      "exercise_id": 1,
      "set_number": 1,
      "weight": 100.0,
      "reps": 5,
      "rpe": 8.0, // Rate of Perceived Exertion (1-10)
      "rir": 2, // Reps in Reserve
      "form_quality": "good", // "excellent", "good", "fair", "poor"
      "set_type_used": "straight", // Optional: what technique was used
      "rep_style_used": "normal", // Optional: what rep style was used
      "technique_details": null, // Optional: execution details for ML
      "notes": "Felt strong" // Optional
    },
    {
      "exercise_id": 1,
      "set_number": 2,
      "weight": 100.0,
      "reps": 5,
      "rpe": 8.5,
      "rir": 1,
      "form_quality": "good",
      "set_type_used": "drop_set", // Example: drop set was performed
      "rep_style_used": "normal",
      "technique_details": { "drop_percentage": 0.2, "drops_count": 1 }
    },
    {
      "exercise_id": 2,
      "set_number": 1,
      "weight": 80.0,
      "reps": 8,
      "rpe": 7.5,
      "rir": 2,
      "form_quality": "excellent"
    }
  ],
  "recovery_metrics": {
    "sleep_quality": "good", // "poor", "not_bad", "good", "excellent"
    "sleep_hours": 7.5,
    "overall_soreness": 3, // 1-10 scale
    "muscle_soreness": {
      // Optional
      "chest": 4,
      "legs": 2
    },
    "stress_level": 4, // 1-10 scale
    "energy_level": 7, // 1-10 scale
    "nutrition_adherence": "good", // Optional
    "hydration_level": "adequate", // Optional
    "notes": "Slept well" // Optional
    // Note: HRV field exists but is not currently used (requires external hardware)
  },
  "overall_rpe": 8.0,
  "overall_feeling": "good", // Optional
  "notes": "Great workout" // Optional
}
```

**Response:** `200 OK`

```json
{
  "workout_session": {
    "id": 1,
    "athlete_id": 1,
    "workout_day_id": 1,
    "session_date": "2024-01-15T10:00:00",
    "duration_minutes": 60,
    "overall_rpe": 8.0,
    "total_volume": 1540.0,
    "estimated_fatigue": 0.45,
    "created_at": "2024-01-15T11:00:00"
  },
  "recovery_metrics": {
    "id": 1,
    "athlete_id": 1,
    "date": "2024-01-15T10:00:00",
    "sleep_quality": "good",
    "readiness_score": 0.82
  },
  "next_workout": {
    "workout_day": {
      "id": 1,
      "name": "Push Day A",
      "exercises": [
        {
          "id": 1,
          "exercise_id": 1,
          "order_in_workout": 1,
          "target_sets": 3,
          "target_reps_min": 4,
          "target_reps_max": 6,
          "target_rpe": 8.5,
          "adjusted_weight": 102.5, // AI-adjusted weight
          "adjusted_sets": 3,
          "adjusted_reps_min": 4,
          "adjusted_reps_max": 6,
          "adjustment_reason": "Performance on target - progressive increase",
          "set_type": "straight", // AI-recommended set type
          "rep_style": "normal", // AI-recommended rep style
          "set_type_params": {}, // Technique-specific parameters
          "rep_style_params": {} // Rep style parameters
        }
      ]
    },
    "adjustments_summary": {
      "volume_change": "+2.5%",
      "intensity_change": "+2.5%",
      "reasoning": "Performance on target - progressive increase | Recovery optimal",
      "exercises_adjusted": 5
    },
    "injury_warnings": [],
    "recovery_recommendations": [
      "Recovery status is good - maintain current practices",
      "Continue monitoring sleep, nutrition, and stress"
    ],
    "weekly_progress": {
      "workouts_this_week": 3,
      "total_volume": 15000.0,
      "average_rpe": 7.8,
      "trend": "increasing"
    }
  },
  "performance_analysis": {
    "workout_day_id": 1,
    "total_volume": 1540.0,
    "average_rpe": 8.0,
    "performance_level": "on_target",
    "exercises_completed": 5,
    "exercise_analyses": [
      {
        "exercise_id": 1,
        "prescribed_sets": 3,
        "actual_sets": 3,
        "average_rpe": 8.25,
        "target_rpe": 8.5,
        "rpe_difference": -0.25,
        "estimated_1rm": 115.0
      }
    ]
  },
  "ai_insights": [
    "✅ Recovery is excellent. Your body is adapting well to training.",
    "📈 Progressive overload applied. Continue pushing forward!"
  ]
}
```

**Example with Intensity Technique Recommendation:**

When the AI detects a trigger (e.g., plateau), it recommends an intensity technique:

```json
{
  "next_workout": {
    "workout_day": {
      "exercises": [
        {
          "exercise_id": 5,
          "adjusted_weight": 80.0,
          "set_type": "drop_set",
          "rep_style": "normal",
          "set_type_params": {
            "drop_percentage": 0.2,
            "drops_count": 1
          },
          "rep_style_params": {},
          "adjustment_reason": "Plateau detected - adding intensity technique to break through | Drop Set recommended"
        }
      ]
    }
  },
  "ai_insights": [
    "🔄 Plateau detected on Lateral Raises - Drop Sets recommended to break through",
    "💪 Volume ceiling reached for shoulders - using intensity technique to maximize stimulus"
  ]
}
```

---

### Get Workout Session

Retrieve details of a specific completed workout.

**Endpoint:** `GET /api/workouts/sessions/{session_id}`

**Response:** `200 OK`

```json
{
  "session": {
    "id": 1,
    "athlete_id": 1,
    "workout_day_id": 1,
    "session_date": "2024-01-15T10:00:00",
    "duration_minutes": 60,
    "total_volume": 1540.0
  },
  "exercise_sets": [
    {
      "id": 1,
      "exercise_id": 1,
      "set_number": 1,
      "weight": 100.0,
      "reps": 5,
      "rpe": 8.0,
      "rir": 2
    }
  ]
}
```

---

## Machine Learning Endpoints

### Train ML Model (Async)

Queue async ML model training for a specific athlete.

**Endpoint:** `POST /api/ml/train/{athlete_id}`

**Path Parameters:**

- `athlete_id` (int): Athlete ID

**Query Parameters:**

- `trigger_reason` (str, optional): Reason for training (default: "manual")

**Response:** `200 OK`

```json
{
  "athlete_id": 1,
  "status": "queued",
  "job_id": 123,
  "trigger_reason": "manual",
  "created_at": "2024-01-15T10:00:00"
}
```

---

### Get Training Job Status

Get status of a specific ML training job.

**Endpoint:** `GET /api/ml/jobs/{job_id}`

**Path Parameters:**

- `job_id` (int): Training job ID

**Response:** `200 OK`

```json
{
  "job_id": 123,
  "athlete_id": 1,
  "status": "completed",
  "trigger_reason": "manual",
  "created_at": "2024-01-15T10:00:00",
  "started_at": "2024-01-15T10:01:00",
  "completed_at": "2024-01-15T10:05:00",
  "training_metrics": {
    "model_type": "lightgbm",
    "n_ensemble_models": 5,
    "training_samples": 25,
    "r2_score": 0.78
  }
}
```

---

### List Training Jobs

List ML training jobs with optional filters.

**Endpoint:** `GET /api/ml/jobs`

**Query Parameters:**

- `athlete_id` (int, optional): Filter by athlete ID
- `status` (str, optional): Filter by status (pending, running, completed, failed)
- `limit` (int, optional): Maximum number of jobs to return (default: 50)

**Response:** `200 OK`

```json
{
  "jobs": [
    {
      "job_id": 123,
      "athlete_id": 1,
      "status": "completed",
      "trigger_reason": "manual",
      "created_at": "2024-01-15T10:00:00",
      "completed_at": "2024-01-15T10:05:00",
      "has_metrics": true
    }
  ],
  "count": 1
}
```

---

## Prescription Generation Endpoints

### Generate Prescription

Generate scientifically-validated target RPE, RIR, and rest period for a single exercise.

**Endpoint:** `POST /api/prescriptions/generate`

**Request Body:**

```json
{
  "intensity_category": "compound_heavy", // "compound_heavy", "compound_moderate", or "isolation"
  "training_type": "hybrid", // "strength", "hypertrophy", or "hybrid"
  "training_phase": "accumulation", // "accumulation", "intensification", "realization", or "deload"
  "week_in_phase": 2, // Week number within phase (1-4 typically)
  "is_primary": true // Whether this is a primary exercise (affects rest period)
}
```

**Response:** `200 OK`

```json
{
  "target_rpe": 7.5, // Target Rate of Perceived Exertion (5.0-10.0)
  "target_rir": 2, // Target Reps in Reserve (0-5)
  "rest_period_seconds": 180 // Rest period between sets in seconds
}
```

**Scientific Rules Applied:**

- **CNS Tax Rule**: Compound exercises capped at RPE 9.0 maximum
- **Inverse RPE/RIR Law**: Strictly enforced as RIR = 10 - RPE
- **Deload Safety**: Aggressive intensity reduction (-2.0 RPE modifier, floor at 5.0)
- **Hybrid Logic**: Compounds follow strength rules, isolations follow hypertrophy rules
- **Microcycle Progression**: Week 1-4 progressive overload within each phase

**Example Prescriptions:**

| Exercise Category | Training Type | Phase           | Week | RPE  | RIR | Rest (s) |
| ----------------- | ------------- | --------------- | ---- | ---- | --- | -------- |
| Compound Heavy    | Strength      | Accumulation    | 2    | 7.5  | 2   | 270      |
| Compound Moderate | Hypertrophy   | Intensification | 3    | 8.75 | 1   | 135      |
| Isolation         | Hybrid        | Realization     | 4    | 9.5  | 0   | 68       |
| Compound Heavy    | Strength      | Deload          | 1    | 6.0  | 4   | 202      |

---

### Generate Batch Prescriptions

Generate prescriptions for multiple exercises at once. Useful for initial workout plan creation.

**Endpoint:** `POST /api/prescriptions/generate-batch`

**Request Body:**

```json
{
  "prescriptions": [
    {
      "intensity_category": "compound_heavy",
      "training_type": "hybrid",
      "training_phase": "accumulation",
      "week_in_phase": 2,
      "is_primary": true
    },
    {
      "intensity_category": "isolation",
      "training_type": "hybrid",
      "training_phase": "accumulation",
      "week_in_phase": 2,
      "is_primary": false
    }
  ]
}
```

**Response:** `200 OK`

```json
{
  "prescriptions": [
    {
      "target_rpe": 7.5,
      "target_rir": 2,
      "rest_period_seconds": 270
    },
    {
      "target_rpe": 8.5,
      "target_rir": 1,
      "rest_period_seconds": 68
    }
  ]
}
```

**Notes:**

- Maximum 50 prescriptions per batch request
- All prescriptions use the same training phase and week_in_phase
- Each exercise can have different intensity_category and is_primary status

---

### Get Athlete Analytics

Get comprehensive analytics for an athlete including performance trends, recovery patterns, and injury risk indicators.

**Endpoint:** `GET /api/athletes/{athlete_id}/analytics`

**Path Parameters:**

- `athlete_id` (int): Athlete ID

**Query Parameters:**

- `days` (int, optional): Number of days to analyze (default: 30)

**Response:** `200 OK`

```json
{
  "athlete_id": 1,
  "period_days": 30,
  "session_count": 12,
  "averages": {
    "performance_score": 0.782,
    "readiness_score": 0.745,
    "volume": 1540.0,
    "rpe": 7.8
  },
  "deload_count": 1,
  "current_acwr": 1.15,
  "injury_risk_status": "low",
  "trends": [
    {
      "date": "2024-01-15T10:00:00",
      "performance_score": 0.82,
      "readiness_score": 0.78,
      "total_volume": 1600.0,
      "average_rpe": 8.0,
      "acwr": 1.15,
      "deload_triggered": false
    }
  ]
}
```

---

## Error Responses

All endpoints may return error responses:

**400 Bad Request**

```json
{
  "detail": "Validation error message"
}
```

**404 Not Found**

```json
{
  "detail": "Resource not found"
}
```

**500 Internal Server Error**

```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limits

Currently no rate limits (to be implemented).

---

## Enums and Constants

### Gender

- `male`
- `female`

### Training Experience

- `beginner`: < 1 year consistent training
- `intermediate`: 1-3 years consistent training
- `advanced`: 3+ years consistent training

### Training Type

- `hypertrophy`: Muscle growth focus
- `strength`: Maximal strength focus
- `hybrid`: Combination approach

### Periodization Model

- `linear`: Progressive increase in intensity
- `undulating`: DUP - Daily Undulating Periodization
- `block`: Block periodization with distinct phases

### Training Phase

- `accumulation`: Volume focus (RPE modifier: -0.5)
- `intensification`: Intensity focus (RPE modifier: +0.5)
- `realization`: Peaking phase (RPE modifier: +1.0, capped at 9.0 for compounds)
- `deload`: Active recovery (RPE modifier: -2.0, floor at 5.0)

### Exercise Intensity Category

- `compound_heavy`: High CNS demand exercises (Squats, Deadlifts, Bench Press)
- `compound_moderate`: Moderate CNS demand (Rows, Lunges, OHP)
- `isolation`: Low CNS demand (Curls, Extensions, Raises)

### Sleep Quality

- `poor`
- `not_bad`
- `good`
- `excellent`

### Form Quality

- `excellent`
- `good`
- `fair`
- `poor`

### Set Type (Intensity Techniques)

- `straight` - Standard sets (default)
- `drop_set` - Reduce weight, continue reps
- `rest_pause` - Brief rest (10-20s), continue to failure
- `myo_reps` - Activation set + mini-sets
- `cluster_set` - Intra-set rest between rep clusters
- `superset_antagonist` - Paired with antagonist exercise
- `pre_exhaust` - Isolation before compound

### Rep Style (Intensity Techniques)

- `normal` - Standard full ROM reps (default)
- `lengthened_partials` - Partials in stretched position
- `tempo_eccentric` - Slow eccentric (3-5 sec)
- `tempo_paused` - 1-2 sec pause at stretched position
- `eccentric_overload` - Supramaximal eccentric loading

---

**Model Requirements:**

- **LightGBM**: Minimum 10 sessions, requires `lightgbm` package
- **Sequential CNN**: Minimum 20 sessions, requires `tensorflow` and Python ≤3.12
- If Sequential CNN dependencies unavailable, system automatically falls back to LightGBM
