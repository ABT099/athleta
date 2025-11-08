# AthleteAI - Progressive Overload Training System

An AI-powered training system that implements scientific progressive overload principles for strength, hypertrophy, and hybrid training programs.

## Features

- **Intelligent Progressive Overload**: Automatically adjusts training parameters based on performance and recovery
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

### 1. Install UV (Recommended)

UV is a blazingly fast Python package installer (10-100x faster than pip):

```bash
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create virtual environment and install dependencies

**With UV (Recommended):**
```bash
uv venv
.venv\Scripts\activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

**Or with traditional pip:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

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

### AI Engine Components

1. **Plan Context Analyzer**: Understands current training phase and periodization
2. **Performance Analyzer**: Compares actual vs. prescribed performance
3. **Recovery Assessor**: Evaluates readiness based on sleep and recovery markers
4. **Injury Prevention**: Monitors training load and flags risk factors
5. **Progression Calculator**: Determines optimal adjustments for next workout

## API Endpoints

### Core Endpoints

- `POST /api/workouts/complete`: Submit completed workout and receive next workout adjustments
- `GET /api/athletes/{id}/current-plan`: Get current weekly training plan
- `GET /api/athletes/{id}/next-workout`: Get next scheduled workout with updated parameters
- `POST /api/athletes`: Create new athlete profile
- `GET /api/athletes/{id}/progress`: View training progression analytics

## Scientific Principles

The system implements evidence-based training principles:

- **Progressive Overload**: Systematic increase in training stress
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

