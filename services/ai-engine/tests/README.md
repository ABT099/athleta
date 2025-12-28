# Test Suite Documentation

This directory contains the test suite for the AI Engine service.

## Directory Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
│   ├── services/      # Service layer tests
│   ├── ml/            # ML model tests
│   └── models/        # Model tests
├── integration/       # Integration tests (slower, test interactions)
├── fixtures/         # Shared test fixtures and helpers
├── factories.py       # Test data factories
└── conftest.py        # Pytest configuration and shared fixtures
```

## Test Organization

### Unit Tests (`tests/unit/`)
Fast, isolated tests that test individual components in isolation:
- **Services**: Test service logic without database dependencies where possible
- **ML**: Test ML model selection, training, and prediction logic
- **Models**: Test model behavior and relationships

### Integration Tests (`tests/integration/`)
Tests that verify component interactions:
- End-to-end workflows
- Database integration
- Service orchestration

## Running Tests

### Run all tests
```bash
pytest
```

### Run only unit tests (fast feedback)
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

### Run tests excluding slow tests
```bash
pytest -m "unit and not slow"
```

### Run ML tests (requires TensorFlow/LightGBM)
```bash
pytest -m ml
```

### Run smoke tests (critical path)
```bash
pytest -m smoke
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

## CI/CD Test Strategy

### Test Tiers

1. **Smoke Tests** (Priority 1): Critical path tests for complete workout workflow
   - Run on: Every PR + Merge + Nightly
   - Duration: ~30 seconds
   - Command: `pytest -m smoke`
   - Tests: Complete workout workflow end-to-end

2. **Fast Unit Tests** (Priority 2): 228 isolated unit tests
   - Run on: Every PR + Merge + Nightly
   - Duration: ~2 minutes
   - Command: `pytest -m "not slow"`
   - Tests: All unit tests excluding slow ML and integration tests

3. **Integration Tests** (Priority 3): Full workflow tests
   - Run on: Merge to main + Nightly
   - Duration: ~3 minutes
   - Command: `pytest -m integration`
   - Tests: End-to-end workflows, database integration, service orchestration

4. **ML Training Tests** (Priority 4): Model training validation
   - Run on: Merge to main + Nightly
   - Duration: ~2 minutes
   - Command: `pytest -m ml`
   - Tests: ML model training, ensemble validation, model selection

### GitHub Actions Workflows

- **PR Tests** (`.github/workflows/pr-tests.yml`): Smoke + Fast tests on every pull request
  - Triggers: Pull requests to `main` or `develop` branches
  - Runs: Smoke tests (Priority 1) + Fast unit tests (Priority 2)
  - Provides fast feedback (~2-3 minutes) for developers

- **Full Tests** (`.github/workflows/full-tests.yml`): All tests on merge to main
  - Triggers: Push to `main` branch
  - Runs: Complete test suite (294 tests) with coverage reporting
  - Ensures comprehensive validation before deployment

- **Nightly Tests** (`.github/workflows/nightly-tests.yml`): Scheduled comprehensive testing
  - Triggers: Daily at 2 AM UTC + Manual dispatch
  - Runs: Full test suite with detailed reporting and coverage
  - Catches regressions and provides comprehensive test metrics

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.ml` - ML model tests (require TensorFlow/LightGBM)
- `@pytest.mark.smoke` - Critical smoke tests (complete workout workflow)

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

## Fixtures

Common fixtures available in `conftest.py`:

- `db_session` - Database session with automatic rollback
- `freeze_time` - Freeze time for time-based tests
- `mock_ml_services` - Mock ML services for non-ML tests
- `sample_athlete` - Pre-created athlete instance
- `sample_exercise` - Pre-created exercise instance
- `sample_workout_plan` - Pre-created workout plan
- `sample_workout_day` - Pre-created workout day

## Best Practices

1. **Use factories** instead of manually creating test data
2. **Parametrize tests** to reduce duplication
3. **Use appropriate markers** for test organization
4. **Mock external dependencies** (ML services, datetime, etc.)
5. **Keep tests fast** - unit tests should run in < 1 second each
6. **Test edge cases** and error conditions
7. **Use descriptive test names** that explain what is being tested

## Writing New Tests

### Example: Unit Test
```python
import pytest
from tests.factories import AthleteFactory
from app.services.my_service import MyService

@pytest.mark.unit
class TestMyService:
    def test_feature(self, db_session):
        """Test that feature works correctly."""
        athlete = AthleteFactory.create(db_session)
        service = MyService(db_session)
        result = service.do_something(athlete.id)
        assert result is not None
```

### Example: Parametrized Test
```python
@pytest.mark.parametrize("input_value,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_multiply_by_two(input_value, expected):
    assert input_value * 2 == expected
```

## Coverage Goals

- **Core services**: 90%+ coverage
- **ML components**: 80%+ coverage
- **Models**: 70%+ coverage

Run `pytest --cov=app --cov-report=term-missing` to see coverage details.

