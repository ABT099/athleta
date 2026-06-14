# AthleteAI - Progressive Overload Training System

An AI-powered training system that implements scientific progressive overload principles for strength, hypertrophy, and hybrid training programs.

## Features

- **Intelligent Progressive Overload**: Automatically adjusts training parameters based on performance and recovery
- **Automatic Prescription Generation**: Scientifically-validated target RPE, RIR, and rest period generation based on exercise type, training goal, and phase
- **Plan-Context Awareness**: Respects periodization models and training phases
- **Recovery Integration**: Considers sleep quality, soreness, stress, and energy levels
- **Injury Prevention**: Monitors volume spikes, intensity limits, and movement patterns
- **Multi-Goal Support**: Optimized for strength, hypertrophy, and hybrid training
- **Scientific Foundation**: Based on NSCA guidelines, RPE-based autoregulation, and exercise physiology research

## System Requirements

- Python 3.11+
- PostgreSQL 15+
- Docker (for database)

## Setup

### 1. Install UV

UV is a blazingly fast Python package manager (10-100x faster than pip):

```bash
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
# Install all dependencies (dev + ml)
uv sync --all-extras

# Or install specific extras:
uv sync --extra dev          # Dev only (testing, linting)
uv sync --extra ml           # ML libraries (lightgbm)
uv sync --extra dev --extra ml  # Both

# Activate virtual environment
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux
```

**Note:** ML libraries (lightgbm) are optional. The system works without them but ML prediction features will be disabled.

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the API server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Architecture

### Database Models

- **Athlete**: User profile with age, gender, training experience
- **WorkoutPlan**: Blueprint template with periodization structure
- **PlanEntry**: Weekly plan instances with adjustments
- **Exercise**: Exercise library with muscle groups and injury risk
- **WorkoutDay**: Scheduled workouts with prescribed parameters
- **WorkoutSession**: Completed workout data
- **ExerciseSet**: Individual set performance (weight, reps, RPE, RIR)
- **RecoveryMetrics**: Sleep quality, soreness, readiness scores

### Auto Regulation Service Components

1. **Prescription Generator**: Generates scientifically-validated target RPE, RIR, and rest periods
2. **Plan Context Analyzer**: Understands current training phase and periodization
3. **Performance Analyzer**: Compares actual vs. prescribed performance
4. **Recovery Assessor**: Evaluates readiness based on sleep and recovery markers
5. **Injury Prevention**: Monitors training load and flags risk factors
6. **Progression Calculator**: Determines optimal adjustments for next workout

## API Endpoints

### Core Endpoints

- `POST /api/workouts/complete`: Submit completed workout and receive next workout adjustments
- `POST /api/prescriptions/generate`: Generate target RPE, RIR, and rest period for an exercise
- `POST /api/prescriptions/generate-batch`: Generate prescriptions for multiple exercises
- `GET /api/athletes/{id}/analytics`: View training progression analytics

## Scientific Principles

The system implements evidence-based training principles:

- **Progressive Overload**: Systematic increase in training stress
- **Prescription Generation**: Automatic RPE/RIR/rest period generation based on:
  - CNS Tax Rule: Compound exercises capped at RPE 9.0 for safety
  - Inverse RPE/RIR Law: Strictly enforced as RIR = 10 - RPE
  - Hybrid Training Logic: Compounds follow strength rules, isolations follow hypertrophy rules
  - Phase-Aware Adjustments: Accumulation, intensification, realization, and deload phases
  - Microcycle Progression: Week-in-phase progressive overload
- **Periodization**: Structured variation in volume and intensity
- **Autoregulation**: RPE/RIR-based adjustments (Zourdos et al., 2016)
- **Recovery Management**: Fatigue-fitness model integration
- **Injury Prevention**: ACWR monitoring (Gabbett, 2016)
- **Volume Landmarks**: MEV, MAV, MRV per muscle group (Renaissance Periodization)

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
flake8 app/
mypy app/
```

## License

MIT License
