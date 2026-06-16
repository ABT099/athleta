# Test Suite - Solo Dev Optimized

This test suite is optimized for **solo development** with fast feedback, minimal maintenance, and integration-first testing.

## Philosophy

- **Integration-first**: Test real user journeys, not isolated units
- **Fast feedback**: Core tests run in ~1 minute
- **Minimal maintenance**: Fewer brittle mocks, test what matters
- **ML separate**: Heavy ML tests run nightly only

## Directory Structure

```
tests/
├── unit/                      # ~50 tests, ~30 seconds
│   ├── calculations/          # Pure math (1RM, RPE, etc.)
│   │   └── test_training_calculations.py
│   └── algorithms/            # Complex business logic
│       ├── test_recovery_analyzer.py
│       ├── test_volume_landmarks.py
│       ├── test_advanced_deload_triggers.py
│       └── test_extended_break_detection.py
│
├── integration/               # ~66 tests, ~2-3 minutes
│   ├── journeys/              # End-to-end user scenarios
│   │   └── test_complete_workout_workflow.py
│   └── features/              # Feature-specific workflows
│       ├── test_intensity_techniques_workflow.py
│       ├── test_progressive_overload_intensity.py
│       ├── test_recovery_gender_age.py
│       └── test_robustness.py
│
├── ml/                        # ~20 tests, ~2 minutes (nightly only)
│   ├── test_bayesian_ensemble.py
│   ├── test_ml_integration.py
│   ├── test_model_selector.py
│   ├── test_sequential_features.py
│   └── test_workout_predictor_upgrade.py
│
├── fixtures/                  # Shared test helpers
├── conftest.py               # Pytest configuration and fixtures
└── factories.py              # Test data factories
```

## Running Tests

### Fast Feedback (~1 minute)

```bash
# Calculations + smoke test (what runs on every PR)
pytest tests/unit/calculations tests/integration/journeys -m smoke -v
```

### All Non-ML Tests (~3 minutes)

```bash
# Everything except ML (runs on merge to main)
pytest -m "not ml"
```

### By Category

```bash
# Pure calculations (fast)
pytest tests/unit/calculations/

# Algorithms (core business logic)
pytest tests/unit/algorithms/

# Integration tests only
pytest tests/integration/

# ML tests (nightly)
pytest tests/ml/
```

### With Coverage

```bash
# Full coverage report
pytest --cov=app --cov-report=html
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.calculations` - Pure calculation/math tests (fast)
- `@pytest.mark.algorithms` - Complex algorithm tests (business logic)
- `@pytest.mark.integration` - Integration tests (user journeys and workflows)
- `@pytest.mark.ml` - ML model tests (requires TensorFlow/LightGBM, runs nightly)
- `@pytest.mark.smoke` - Critical smoke test (complete workout endpoint)
- `@pytest.mark.slow` - Slow-running tests

## CI/CD Workflow

### PR Tests (Fast Feedback)

**Duration**: ~1 minute  
**Runs on**: Every pull request

```bash
pytest tests/unit/calculations/ -v      # Pure math
pytest -m smoke -v                       # Critical path
pytest tests/unit/algorithms/ -v        # Core logic
```

### Integration Tests

**Duration**: ~3 minutes  
**Runs on**: Merge to main

```bash
pytest -m "not ml" --cov=app
```

### Nightly Tests

**Duration**: ~5 minutes  
**Runs on**: Daily at 2 AM UTC

```bash
pytest tests/ml/ -v                      # ML training tests
pytest --cov=app --cov-report=html       # Full coverage
```

## Test Factories

Use factories from `tests/factories.py` to create test data:

```python
from tests.factories import AthleteFactory, ExerciseFactory, WorkoutPlanFactory

# Create a test athlete
athlete = AthleteFactory.create(db_session, age=25)

# Create a compound exercise
exercise = ExerciseFactory.create_compound(db_session, name="Bench Press")

# Create a workout plan
plan = WorkoutPlanFactory.create(db_session, athlete_id=athlete.id)
```

## Common Fixtures

Available in `conftest.py`:

- `db_session` - Database session with automatic rollback
- `freeze_time` - Freeze time for time-based tests
- `mock_ml_services` - Mock ML services for non-ML tests
- `sample_athlete` - Pre-created athlete instance
- `sample_exercise` - Pre-created exercise instance
- `sample_workout_plan` - Pre-created workout plan
- `sample_workout_day` - Pre-created workout day

## Writing New Tests

### Calculation Test Example

```python
import pytest

@pytest.mark.calculations
class TestTrainingCalculations:
    def test_estimate_1rm(self):
        """Test 1RM estimation formula."""
        calc = TrainingCalculations()
        result = calc.estimate_1rm_epley(100, 5)
        assert abs(result - 116.67) < 0.01
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
class TestWorkoutJourney:
    def test_complete_workout_flow(self, client, db_session, workout_setup):
        """api pushes the logged session; auto-reg computes and returns adjustments."""
        # Build the analyze request (athlete + plan + session + recovery) and POST it
        request = AnalysisRequestFactory.create(...)
        response = client.post("/api/analysis/sessions", json=request.model_dump(mode="json"))

        # Verify response structure (adjustments + write-backs for api)
        assert response.status_code == 200
        assert "next_workout" in response.json()
        assert "ai_insights" in response.json()
```

## Best Practices

1. **Test user journeys**, not implementation details
2. **Use factories** for test data creation
3. **Mock heavy operations** (ML processing, external APIs)
4. **Keep calculations pure** - fast unit tests for math
5. **Integration tests for workflows** - test the complete flow
6. **ML tests run nightly** - expensive operations don't block PRs

## Coverage Goals

- **Critical paths** (workout completion, progression): 100%
- **Calculations & algorithms**: 90%+
- **Integration journeys**: 85%+
- **Overall**: 85%+

Run `pytest --cov=app --cov-report=term-missing` to see coverage details.

## Migration Notes

This test suite was refactored to optimize for solo development:

- **Removed**: ~185 redundant unit tests (API layer, simple CRUD)
- **Kept**: ~50 focused unit tests (calculations, algorithms)
- **Expanded**: Integration tests focused on user journeys
- **Separated**: ML tests into dedicated directory

**Result**: 50% faster PR feedback, 60% less maintenance, same confidence level.
