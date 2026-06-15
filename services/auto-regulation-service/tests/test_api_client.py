"""
Unit tests for the api-service HTTP client.

Two surfaces are covered:
  * the real ApiClient parsing/404 behaviour, driven through an httpx
    MockTransport (no live api needed); and
  * the in-memory fake + autouse fixture that the rest of the suite relies on.
"""
import json

import httpx
import pytest

from app.clients.api_client import (
    ApiClient,
    AthleteDTO,
    RecoveryMetricsDTO,
    WorkoutSessionDTO,
)


def _json(payload, status=200):
    return httpx.Response(status, content=json.dumps(payload))


def test_real_client_parses_athlete_and_nested_session():
    """ApiClient parses api JSON into DTOs, including nested sets."""
    routes = {
        "/internal/athletes/7": _json(
            {
                "id": 7,
                "age": 28,
                "gender": "male",
                "training_experience": "intermediate",
                "rpe_calibration_factor": 1.0,
                "body_weight_kg": 82.5,
            }
        ),
        "/internal/workout-sessions/42": _json(
            {
                "id": 42,
                "athlete_id": 7,
                "workout_day_id": 3,
                "session_date": "2026-06-14T10:00:00",
                "overall_rpe": 8.0,
                "sets": [
                    {
                        "id": 1,
                        "workout_session_id": 42,
                        "exercise_id": 5,
                        "set_number": 1,
                        "weight": 100.0,
                        "reps": 5,
                        "rpe": 8.0,
                    }
                ],
            }
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(request.url.path, httpx.Response(404))

    with ApiClient(
        base_url="http://api.test", token="svc", transport=httpx.MockTransport(handler)
    ) as api:
        athlete = api.get_athlete(7)
        session = api.get_workout_session(42)
        missing = api.get_workout_session(999)

    assert isinstance(athlete, AthleteDTO)
    assert athlete.gender == "male" and athlete.body_weight_kg == 82.5
    assert isinstance(session, WorkoutSessionDTO)
    assert len(session.sets) == 1 and session.sets[0].weight == 100.0
    assert missing is None  # 404 -> None


def test_real_client_sends_service_token_and_query_params():
    """The bearer token is attached and None query params are dropped."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["query"] = dict(request.url.params)
        return _json([])

    with ApiClient(
        base_url="http://api.test", token="secret-123",
        transport=httpx.MockTransport(handler),
    ) as api:
        api.list_recent_sessions(7, since=None, limit=5)

    assert captured["auth"] == "Bearer secret-123"
    assert captured["query"] == {"limit": "5"}  # `since=None` omitted


def test_client_requires_context_manager():
    with pytest.raises(RuntimeError):
        ApiClient(base_url="http://api.test").get_athlete(1)


def test_fake_api_service_fixture_round_trips(fake_api_service):
    """The autouse fake serves seeded DTOs through the patched ApiClient."""
    fake_api_service.add_athlete(
        AthleteDTO(id=1, age=30, gender="female", training_experience="advanced")
    )
    fake_api_service.add_recovery(
        RecoveryMetricsDTO(id=1, athlete_id=1, date="2026-06-10T00:00:00", sleep_quality="good")
    )

    with ApiClient() as api:  # patched to the fake by the fixture
        athlete = api.get_athlete(1)
        recovery = api.list_recovery_metrics(1)
        absent = api.get_athlete(2)

    assert athlete.training_experience == "advanced"
    assert len(recovery) == 1 and recovery[0].sleep_quality == "good"
    assert absent is None
