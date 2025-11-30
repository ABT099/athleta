# AthleteAI API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is required (to be implemented).

---

## What's New (November 2025)

The AI engine has been significantly enhanced with new scientific capabilities.

### Automatic Intensity Techniques (NEW)
- **Set Types**: Drop Set, Rest-Pause, Myo-Reps, Cluster Set, Superset, Pre-Exhaust
- **Rep Styles**: Lengthened Partials, Tempo Eccentric, Tempo Paused, Eccentric Overload
- **Trigger-Based**: AI defaults to straight sets and only adds techniques when needed:
  - Plateau detected (stalled progress)
  - Struggling performance (high RPE, no gains)
  - Volume ceiling (at MRV)
  - Late accumulation phase
- **Composable**: Set types and rep styles can be combined
- **Tracked**: Execution details stored for ML analytics

### Enhanced Intelligence
- **Smarter Age & Gender Adjustments**: Now considers training age alongside chronological age, with more nuanced gender-based fatigue resistance modeling
- **Volume Landmark Tracking**: MEV/MAV/MRV system prevents both under and overtraining for hypertrophy goals
- **Advanced Fatigue Detection**: ACWR and Session RPE monitoring for proactive injury prevention
- **Six Independent Deload Triggers**: Comprehensive autoregulation based on performance, recovery, workload ratios, and session load

### API Changes
- **New optional fields** in workout completion request for tracking intensity techniques
- **New fields** in next workout response with AI-recommended techniques
- All changes are backward compatible - existing clients work without modification

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
      "set_type_used": "straight",  // Optional: what technique was used
      "rep_style_used": "normal",   // Optional: what rep style was used
      "technique_details": null,    // Optional: execution details for ML
      "notes": "Felt strong"        // Optional
    },
    {
      "exercise_id": 1,
      "set_number": 2,
      "weight": 100.0,
      "reps": 5,
      "rpe": 8.5,
      "rir": 1,
      "form_quality": "good",
      "set_type_used": "drop_set",  // Example: drop set was performed
      "rep_style_used": "normal",
      "technique_details": {"drop_percentage": 0.20, "drops_count": 1}
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
          "adjustment_reason": "Performance on target - progressive increase",
          "set_type": "straight",       // AI-recommended set type
          "rep_style": "normal",        // AI-recommended rep style
          "set_type_params": {},        // Technique-specific parameters
          "rep_style_params": {}        // Rep style parameters
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
            "drop_percentage": 0.20,
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

## Machine Learning Endpoints

### Train ML Model

Train ML model for workout parameter prediction for a specific athlete.

**Endpoint:** `POST /api/ml/train/{athlete_id}`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Requirements:**
- Minimum 10 completed workout sessions
- LightGBM must be installed

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "status": "success",
  "session_count": 25,
  "training_metrics": {
    "model_type": "lightgbm",
    "n_ensemble_models": 5,
    "training_samples": 25,
    "r2_score": 0.78,
    "mse": 0.012
  },
  "trained_at": "2024-01-15T10:00:00"
}
```

**Error Responses:**
- `400 Bad Request`: Insufficient sessions (< 10)
- `404 Not Found`: Athlete not found
- `503 Service Unavailable`: ML services not available (lightgbm not installed)

---

### Get ML Model Status

Get ML model status and information for an athlete.

**Endpoint:** `GET /api/ml/status/{athlete_id}`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "ml_available": true,
  "session_count": 25,
  "model_config": {
    "model_type": "lightgbm",
    "n_ensemble_models": 5,
    "min_sessions": 10
  },
  "model_trained": true,
  "can_train": true,
  "model_metadata": {
    "training_date": "2024-01-15T10:00:00",
    "training_samples": 25,
    "model_type": "lightgbm",
    "version": "1.0"
  },
  "current_predictions": {
    "volume_multiplier": 1.05,
    "intensity_multiplier": 1.02,
    "confidence": 0.75,
    "uncertainty": 0.08,
    "model_type": "lightgbm"
  },
  "feature_importance": {
    "recent_readiness": 0.35,
    "volume_trend": 0.20,
    "age_experience": 0.15
  }
}
```

---

### Retrain ML Model

Force retrain ML model for an athlete.

**Endpoint:** `POST /api/ml/retrain/{athlete_id}`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Query Parameters:**
- `force` (bool, optional): If true, retrain even if model is recent (default: false)

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "status": "success",
  "message": "Model retrained successfully",
  "training_metrics": {
    "model_type": "lightgbm",
    "n_ensemble_models": 5,
    "training_samples": 30,
    "r2_score": 0.82
  },
  "retrained_at": "2024-01-20T10:00:00"
}
```

**Response (Skipped):** `200 OK`
```json
{
  "athlete_id": 1,
  "status": "skipped",
  "message": "Model is up to date. Use force=true to retrain anyway."
}
```

---

### Get Prediction Breakdown

Get detailed prediction breakdown with uncertainty and feature importance.

**Endpoint:** `GET /api/ml/predictions/{athlete_id}`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "ml_predictions": {
    "volume_multiplier": 1.05,
    "intensity_multiplier": 1.02,
    "confidence": 0.75,
    "uncertainty": 0.08
  },
  "ml_source": "ml",
  "rule_based_predictions": {
    "volume_multiplier": 1.03,
    "intensity_multiplier": 1.01,
    "reasoning": "Performance on target - progressive increase"
  },
  "comparison": {
    "volume_difference": 0.02,
    "intensity_difference": 0.01
  }
}
```

---

### List All Models

List all trained ML models across all athletes.

**Endpoint:** `GET /api/ml/models`

**Query Parameters:**
- `athlete_id` (int, optional): Filter by athlete ID

**Response:** `200 OK`
```json
{
  "models": [
    {
      "athlete_id": 1,
      "model_type": "workout_predictor",
      "training_date": "2024-01-15T10:00:00",
      "training_samples": 25,
      "version": "1.0"
    }
  ],
  "count": 1
}
```

---

### Delete Old Model Versions

Delete old model versions for an athlete, keeping only the latest N versions.

**Endpoint:** `DELETE /api/ml/models/{athlete_id}`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Query Parameters:**
- `keep_latest` (int, optional): Number of latest versions to keep (default: 1)

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "deleted_count": 3,
  "kept_latest": 1
}
```

---

### Generate Synthetic Data

Generate synthetic workout data for testing and validation.

**WARNING:** This will create new athletes and sessions in the database. Use only in development/testing environments.

**Endpoint:** `POST /api/ml/generate-synthetic-data`

**Query Parameters:**
- `n_athletes` (int, optional): Number of athletes to generate (default: 50)
- `sessions_per_athlete` (int, optional): Sessions per athlete (default: 50)

**Response:** `200 OK`
```json
{
  "status": "success",
  "summary": {
    "athletes_created": 50,
    "sessions_created": 2500,
    "recovery_metrics_created": 2500
  },
  "message": "Generated 50 athletes with 2500 total sessions"
}
```

---

## Additional Athlete Endpoints

### Get RPE Calibration Status

Get RPE calibration status and accuracy for an athlete.

**Endpoint:** `GET /api/athletes/{athlete_id}/rpe-calibration`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "calibration": {
    "total_samples": 45,
    "average_accuracy": 0.85,
    "calibration_factor": 1.02,
    "bias": "slight_underestimate"
  },
  "ml_model": {
    "trained": true,
    "samples_used": 45,
    "ml_weight": 0.70
  }
}
```

---

### Train RPE ML Model

Train ML model for RPE calibration.

**Endpoint:** `POST /api/athletes/{athlete_id}/rpe-calibration/train-ml`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Requirements:**
- Minimum 30 calibration samples with actual RIR data

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "status": "success",
  "message": "RPE ML model trained successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Insufficient samples (< 30)

---

### Get Workout ML Model Status

Get ML model status for workout parameter prediction.

**Endpoint:** `GET /api/athletes/{athlete_id}/ml-models`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "ml_available": true,
  "model_trained": true,
  "model_metadata": {
    "training_date": "2024-01-15T10:00:00",
    "training_samples": 25,
    "model_type": "lightgbm"
  },
  "should_retrain": false,
  "min_sessions_needed": 10
}
```

---

### Train Workout ML Model

Train ML model for workout parameter prediction.

**Endpoint:** `POST /api/athletes/{athlete_id}/ml-models/train`

**Path Parameters:**
- `athlete_id` (int): Athlete ID

**Requirements:**
- Minimum 10 completed workout sessions (for LightGBM)
- Minimum 20 sessions (for Sequential CNN, if available)

**Response:** `200 OK`
```json
{
  "athlete_id": 1,
  "status": "success",
  "metrics": {
    "model_type": "lightgbm",
    "n_ensemble_models": 5,
    "training_samples": 25,
    "r2_score": 0.78
  },
  "message": "Workout prediction ML model trained successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Insufficient sessions or ML not available
- `404 Not Found`: Athlete not found

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

## Webhooks

Not currently implemented.

---

## Versioning

**API Version**: 1.1.0  
**AI Engine Version**: 1.3.0 (Intensity Techniques, November 2025)

Current API does not use versioning in the URL. Future versions may use `/v1/`, `/v2/` prefixes.

### Version History

**v1.3.0 (November 2025)** - Automatic Intensity Techniques
- Added Set Types: drop_set, rest_pause, myo_reps, cluster_set, superset_antagonist, pre_exhaust
- Added Rep Styles: lengthened_partials, tempo_eccentric, tempo_paused, eccentric_overload
- Trigger-based AI recommendations (plateau, struggling, volume ceiling, phase)
- Execution tracking for ML analytics
- New optional fields in exercise_sets for technique tracking
- New fields in next workout response for AI-recommended techniques
- *Backward compatible - all fields optional*

**v1.2.0 (November 2025)** - ML Model Enhancements
- LightGBM with Bayesian ensembles (production model)
- Tiered model selection (10+ sessions: LightGBM, 20+ sessions: Sequential CNN optional)
- Real-time PerformanceTrend integration (no session lag)
- Comprehensive ML management API endpoints
- *No breaking changes - fully backward compatible*

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

### Deprecation Notes

**DateTime Usage:**
- Some API responses may use `datetime.utcnow()` which is being phased out
- Future versions will use `datetime.now(timezone.utc)` for timezone-aware timestamps
- This is an internal implementation detail and does not affect API consumers

**Model Requirements:**
- **LightGBM**: Minimum 10 sessions, requires `lightgbm` package
- **Sequential CNN**: Minimum 20 sessions, requires `tensorflow` and Python ≤3.12
- If Sequential CNN dependencies unavailable, system automatically falls back to LightGBM

