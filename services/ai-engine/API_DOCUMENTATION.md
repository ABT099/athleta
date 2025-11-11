# AthleteAI API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is required (to be implemented).

---

## What's New (November 2025)

The AI engine has been significantly enhanced with new scientific capabilities. **No API changes required** - all improvements are internal and fully backward compatible:

### Enhanced Intelligence
- **Smarter Age & Gender Adjustments**: Now considers training age alongside chronological age, with more nuanced gender-based fatigue resistance modeling
- **Volume Landmark Tracking**: MEV/MAV/MRV system prevents both under and overtraining for hypertrophy goals
- **Advanced Fatigue Detection**: ACWR and Session RPE monitoring for proactive injury prevention
- **Six Independent Deload Triggers**: Comprehensive autoregulation based on performance, recovery, workload ratios, and session load

### API Compatibility
All existing API calls work exactly as before. The AI simply makes smarter decisions using the same input data.

---

## Athlete Endpoints

### Create Athlete

Create a new athlete profile.

**Endpoint:** `POST /api/athletes`

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "age": 25,
  "gender": "male",  // "male" or "female"
  "training_experience": "intermediate",  // "beginner", "intermediate", or "advanced"
  "injury_history": "None"  // Optional
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "age": 25,
  "gender": "male",
  "training_experience": "intermediate",
  "injury_history": "None",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

---

### Get Athlete

Retrieve athlete information by ID.

**Endpoint:** `GET /api/athletes/{athlete_id}`

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "age": 25,
  "gender": "male",
  "training_experience": "intermediate",
  "injury_history": "None",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

---

### List Athletes

Get all athletes.

**Endpoint:** `GET /api/athletes`

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum records to return (default: 100)

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    ...
  }
]
```

---

### Update Athlete

Update athlete information.

**Endpoint:** `PATCH /api/athletes/{athlete_id}`

**Request Body:**
```json
{
  "age": 26,
  "training_experience": "advanced"
}
```

**Response:** `200 OK` (Updated athlete object)

---

### Get Current Plan

Get athlete's current active training plan.

**Endpoint:** `GET /api/athletes/{athlete_id}/current-plan`

**Response:** `200 OK`
```json
{
  "has_plan": true,
  "plan": {
    "id": 1,
    "name": "Hypertrophy Block",
    "training_type": "hypertrophy",
    "periodization_model": "undulating",
    "frequency": 4,
    "duration_weeks": 8
  },
  "current_context": {
    "week_number": 3,
    "training_phase": "accumulation",
    "is_deload_week": false,
    "target_volume_multiplier": 1.0,
    "target_intensity_multiplier": 1.0
  }
}
```

---

### Get Athlete Progress

Get training progress analytics.

**Endpoint:** `GET /api/athletes/{athlete_id}/progress`

**Query Parameters:**
- `days` (optional): Number of days to analyze (default: 30)

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "athlete_name": "John Doe",
  "period_days": 30,
  "total_workouts": 12,
  "total_volume_lifted": 45000.0,
  "average_rpe": 7.8,
  "weekly_breakdown": [
    {
      "week_start": "2024-01-01",
      "workouts": 3,
      "total_volume": 12000.0,
      "average_rpe": 7.5
    }
  ],
  "training_experience": "intermediate"
}
```

---

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
      "rpe": 8.0,      // Rate of Perceived Exertion (1-10)
      "rir": 2,        // Reps in Reserve
      "form_quality": "good",  // "excellent", "good", "fair", "poor"
      "tempo_adherence": "yes",  // Optional
      "notes": "Felt strong"    // Optional
    },
    {
      "exercise_id": 1,
      "set_number": 2,
      "weight": 100.0,
      "reps": 5,
      "rpe": 8.5,
      "rir": 1,
      "form_quality": "good"
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
    "sleep_quality": "good",     // "poor", "not_bad", "good", "excellent"
    "sleep_hours": 7.5,
    "overall_soreness": 3,       // 1-10 scale
    "muscle_soreness": {         // Optional
      "chest": 4,
      "legs": 2
    },
    "stress_level": 4,           // 1-10 scale
    "energy_level": 7,           // 1-10 scale
    "nutrition_adherence": "good",  // Optional
    "hydration_level": "adequate",  // Optional
    "notes": "Slept well"        // Optional
    // Note: HRV field exists but is not currently used (requires external hardware)
  },
  "overall_rpe": 8.0,
  "overall_feeling": "good",     // Optional
  "notes": "Great workout"       // Optional
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
          "adjusted_weight": 102.5,     // AI-adjusted weight
          "adjusted_sets": 3,
          "adjusted_reps_min": 4,
          "adjusted_reps_max": 6,
          "adjustment_reason": "Performance on target - progressive increase"
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

---

### Get Next Workout

Get next scheduled workout with current parameters (without submitting a completed workout).

**Endpoint:** `GET /api/athletes/{athlete_id}/next-workout`

**Response:** `200 OK`
```json
{
  "workout_day": {
    "id": 2,
    "name": "Pull Day A",
    "exercises": [
      {
        "exercise_id": 5,
        "target_sets": 4,
        "target_reps_min": 6,
        "target_reps_max": 8,
        "adjusted_weight": 90.0
      }
    ]
  },
  "adjustments_summary": {},
  "injury_warnings": [],
  "recovery_recommendations": [],
  "weekly_progress": {}
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
- `accumulation`: Volume focus
- `intensification`: Intensity focus
- `realization`: Peaking phase

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

---

## Webhooks

Not currently implemented.

---

## Versioning

**API Version**: 1.0.0  
**AI Engine Version**: 1.1.0 (Internal improvements, November 2025)

Current API does not use versioning in the URL. Future versions may use `/v1/`, `/v2/` prefixes.

### Version History

**v1.1.0 (November 2025)** - AI Engine Internal Improvements
- Enhanced gender and age-based progression logic
- Added MEV/MAV/MRV volume landmark tracking
- Implemented ACWR and Session RPE fatigue monitoring
- Improved deload autoregulation (6 independent triggers)
- *No breaking changes - fully backward compatible*

**v1.0.0 (November 2025)** - Initial Release
- Core progressive overload engine
- Hybrid ML + rule-based predictions
- RPE calibration system
- Multi-model periodization support

