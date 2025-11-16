"""
Unit tests for form quality service.
"""
import pytest
from datetime import datetime, timedelta
from app.services.form_quality_service import FormQualityService
from app.models import (
    Athlete, Exercise, WorkoutSession, ExerciseSet, FormQualityTrend
)
from app.utils.constants import Gender, TrainingExperience


@pytest.fixture
def form_service(db_session):
    """Create form quality service instance."""
    return FormQualityService(db_session)


@pytest.fixture
def sample_athlete(db_session):
    """Create sample athlete for testing."""
    athlete = Athlete(
        id=1,
        age=25,
        gender=Gender.MALE,
        training_experience=TrainingExperience.INTERMEDIATE,
        rpe_calibration_factor=1.0
    )
    db_session.add(athlete)
    db_session.commit()
    return athlete


@pytest.fixture
def sample_exercise(db_session):
    """Create sample exercise for testing."""
    import json
    exercise = Exercise(
        id=1,
        name="Barbell Bench Press",
        description="Compound chest exercise",
        primary_muscles=json.dumps(["chest"]),  # Serialize for SQLite
        secondary_muscles=json.dumps(["triceps", "shoulders"]),
        injury_risk_level=2.0,
        joint_stress_areas=json.dumps(["shoulder", "elbow"]),
        movement_pattern="push",
        exercise_type="compound",
        complexity_score=1.0
    )
    db_session.add(exercise)
    db_session.commit()
    return exercise


class TestFormScoreCalculation:
    """Test form quality score calculations."""
    
    def test_calculate_form_score_excellent(self, form_service):
        """Test form score calculation for excellent form."""
        score = form_service.calculate_form_score("excellent")
        assert score == 1.0
    
    def test_calculate_form_score_good(self, form_service):
        """Test form score calculation for good form."""
        score = form_service.calculate_form_score("good")
        assert score == 0.75
    
    def test_calculate_form_score_fair(self, form_service):
        """Test form score calculation for fair form."""
        score = form_service.calculate_form_score("fair")
        assert score == 0.5
    
    def test_calculate_form_score_poor(self, form_service):
        """Test form score calculation for poor form."""
        score = form_service.calculate_form_score("poor")
        assert score == 0.25
    
    def test_calculate_form_score_none(self, form_service):
        """Test form score calculation for None (defaults to good)."""
        score = form_service.calculate_form_score(None)
        assert score == 0.75
    
    def test_calculate_form_score_invalid(self, form_service):
        """Test form score calculation for invalid value (defaults to good)."""
        score = form_service.calculate_form_score("invalid")
        assert score == 0.75


class TestFormDegradation:
    """Test form degradation detection."""
    
    def test_track_form_degradation_within_session(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test detection of form degradation within a session."""
        # Create workout session
        session = WorkoutSession(
            id=1,
            athlete_id=sample_athlete.id,
            workout_day_id=1,
            session_date=datetime.utcnow(),
            duration_minutes=60,
            overall_rpe=8.0
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets with degrading form
        sets_data = [
            ("excellent", 1),
            ("excellent", 2),
            ("good", 3),
            ("fair", 4),
        ]
        
        for form_quality, set_number in sets_data:
            ex_set = ExerciseSet(
                workout_session_id=session.id,
                exercise_id=sample_exercise.id,
                set_number=set_number,
                weight=100.0,
                reps=5,
                rpe=8.0,
                form_quality=form_quality
            )
            db_session.add(ex_set)
        
        db_session.commit()
        
        # Track degradation
        degradation_rate = form_service.track_form_degradation_in_session(
            session.id, sample_exercise.id
        )
        
        # Should detect degradation (first half better than second half)
        assert degradation_rate is not None
        assert degradation_rate > 0  # Positive means degraded
    
    def test_track_form_degradation_no_degradation(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test when form quality remains consistent."""
        # Create workout session
        session = WorkoutSession(
            id=1,
            athlete_id=sample_athlete.id,
            workout_day_id=1,
            session_date=datetime.utcnow(),
            duration_minutes=60,
            overall_rpe=8.0
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets with consistent form
        for set_number in range(1, 5):
            ex_set = ExerciseSet(
                workout_session_id=session.id,
                exercise_id=sample_exercise.id,
                set_number=set_number,
                weight=100.0,
                reps=5,
                rpe=8.0,
                form_quality="good"
            )
            db_session.add(ex_set)
        
        db_session.commit()
        
        # Track degradation
        degradation_rate = form_service.track_form_degradation_in_session(
            session.id, sample_exercise.id
        )
        
        # Should show no degradation
        assert degradation_rate is not None
        assert abs(degradation_rate) < 0.01  # Essentially zero
    
    def test_track_form_degradation_insufficient_data(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test when there's insufficient data (only 1 set)."""
        # Create workout session
        session = WorkoutSession(
            id=1,
            athlete_id=sample_athlete.id,
            workout_day_id=1,
            session_date=datetime.utcnow(),
            duration_minutes=60,
            overall_rpe=8.0
        )
        db_session.add(session)
        db_session.flush()
        
        # Create only 1 set
        ex_set = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=sample_exercise.id,
            set_number=1,
            weight=100.0,
            reps=5,
            rpe=8.0,
            form_quality="good"
        )
        db_session.add(ex_set)
        db_session.commit()
        
        # Track degradation
        degradation_rate = form_service.track_form_degradation_in_session(
            session.id, sample_exercise.id
        )
        
        # Should return None (insufficient data)
        assert degradation_rate is None


class TestFormQualityTrends:
    """Test form quality trend analysis."""
    
    def test_save_form_quality_trend(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test saving form quality trend data."""
        trend = form_service.save_form_quality_trend(
            athlete_id=sample_athlete.id,
            exercise_id=sample_exercise.id,
            date=datetime.utcnow(),
            average_form_score=0.75,
            sets_analyzed=4,
            degradation_rate=0.15,
            high_rpe_poor_form_count=0
        )
        
        assert trend.id is not None
        assert trend.athlete_id == sample_athlete.id
        assert trend.exercise_id == sample_exercise.id
        assert trend.average_form_score == 0.75
        assert trend.sets_analyzed == 4
        assert trend.degradation_rate == 0.15
    
    def test_get_form_quality_trend_no_data(
        self, form_service, sample_athlete, sample_exercise
    ):
        """Test getting trend when no data exists."""
        trend = form_service.get_form_quality_trend(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert trend["has_data"] is False
        assert trend["average_score"] is None
        assert trend["session_count"] == 0
    
    def test_get_form_quality_trend_with_data(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test getting trend with data."""
        # Create multiple trend entries
        base_date = datetime.utcnow()
        for i in range(5):
            trend = FormQualityTrend(
                athlete_id=sample_athlete.id,
                exercise_id=sample_exercise.id,
                date=base_date - timedelta(days=i),
                average_form_score=0.75,
                sets_analyzed=4,
                degradation_rate=0.0,
                high_rpe_poor_form_count=0
            )
            db_session.add(trend)
        db_session.commit()
        
        trend_data = form_service.get_form_quality_trend(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert trend_data["has_data"] is True
        assert trend_data["average_score"] == 0.75
        assert trend_data["session_count"] == 5
        assert trend_data["trend_direction"] in ["improving", "degrading", "stable"]


class TestChronicFormIssues:
    """Test chronic form issue detection."""
    
    def test_detect_chronic_form_issues_none(
        self, form_service, sample_athlete, sample_exercise
    ):
        """Test when there are no chronic issues."""
        issues = form_service.detect_chronic_form_issues(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert issues["has_issues"] is False
        assert len(issues["issues"]) == 0
    
    def test_detect_chronic_form_issues_present(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test detection of chronic form issues."""
        # Create multiple trend entries with poor form
        base_date = datetime.utcnow()
        for i in range(5):
            trend = FormQualityTrend(
                athlete_id=sample_athlete.id,
                exercise_id=sample_exercise.id,
                date=base_date - timedelta(days=i),
                average_form_score=0.4,  # Below 0.6 threshold
                sets_analyzed=4,
                degradation_rate=0.1,
                high_rpe_poor_form_count=0
            )
            db_session.add(trend)
        db_session.commit()
        
        issues = form_service.detect_chronic_form_issues(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert issues["has_issues"] is True
        assert len(issues["issues"]) > 0
        assert sample_exercise.id in issues["affected_exercises"]


class TestFormAlerts:
    """Test form quality alert generation."""
    
    def test_generate_form_alerts_no_alerts(
        self, form_service, sample_athlete, sample_exercise
    ):
        """Test when no alerts should be generated."""
        alerts = form_service.generate_form_alerts(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert len(alerts) == 0
    
    def test_generate_form_alerts_degradation_warning(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test generation of degradation warning alert."""
        # Create trend with significant degradation
        trend = FormQualityTrend(
            athlete_id=sample_athlete.id,
            exercise_id=sample_exercise.id,
            date=datetime.utcnow(),
            average_form_score=0.75,
            sets_analyzed=4,
            degradation_rate=0.25,  # 25% degradation (above 20% threshold)
            high_rpe_poor_form_count=0
        )
        db_session.add(trend)
        db_session.commit()
        
        alerts = form_service.generate_form_alerts(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert len(alerts) > 0
        degradation_alerts = [a for a in alerts if a["type"] == "within_session_degradation"]
        assert len(degradation_alerts) > 0
        assert degradation_alerts[0]["severity"] == "WARNING"
    
    def test_generate_form_alerts_high_rpe_poor_form(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test generation of critical alert for high RPE + poor form."""
        # Create trend with high RPE poor form combinations
        trend = FormQualityTrend(
            athlete_id=sample_athlete.id,
            exercise_id=sample_exercise.id,
            date=datetime.utcnow(),
            average_form_score=0.75,
            sets_analyzed=4,
            degradation_rate=0.0,
            high_rpe_poor_form_count=2  # Critical combination
        )
        db_session.add(trend)
        db_session.commit()
        
        alerts = form_service.generate_form_alerts(
            sample_athlete.id, sample_exercise.id, days_lookback=14
        )
        
        assert len(alerts) > 0
        critical_alerts = [a for a in alerts if a["severity"] == "CRITICAL"]
        assert len(critical_alerts) > 0
        assert "high_rpe_poor_form" in critical_alerts[0]["type"]


class TestProgressionBlocking:
    """Test form quality progression blocking."""
    
    def test_should_block_progression_no_data(
        self, form_service, sample_athlete, sample_exercise
    ):
        """Test when there's no data - should not block."""
        should_block, reason = form_service.should_block_progression(
            sample_athlete.id, sample_exercise.id
        )
        
        assert should_block is False
        assert reason is None
    
    def test_should_block_progression_good_form(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test when form is good - should not block."""
        # Create trends with good form
        base_date = datetime.utcnow()
        for i in range(3):
            trend = FormQualityTrend(
                athlete_id=sample_athlete.id,
                exercise_id=sample_exercise.id,
                date=base_date - timedelta(days=i),
                average_form_score=0.75,  # Good form
                sets_analyzed=4,
                degradation_rate=0.0,
                high_rpe_poor_form_count=0
            )
            db_session.add(trend)
        db_session.commit()
        
        should_block, reason = form_service.should_block_progression(
            sample_athlete.id, sample_exercise.id
        )
        
        assert should_block is False
        assert reason is None
    
    def test_should_block_progression_poor_form(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test when form is poor - should block."""
        # Create trends with poor form
        base_date = datetime.utcnow()
        for i in range(3):
            trend = FormQualityTrend(
                athlete_id=sample_athlete.id,
                exercise_id=sample_exercise.id,
                date=base_date - timedelta(days=i),
                average_form_score=0.5,  # Below 0.6 threshold
                sets_analyzed=4,
                degradation_rate=0.0,
                high_rpe_poor_form_count=0
            )
            db_session.add(trend)
        db_session.commit()
        
        should_block, reason = form_service.should_block_progression(
            sample_athlete.id, sample_exercise.id
        )
        
        assert should_block is True
        assert reason is not None
        assert "form quality" in reason.lower()
    
    def test_should_block_progression_degrading_trend(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test when form is degrading - should block."""
        # Create trends showing degradation
        # More recent scores are worse (ordered from newest to oldest)
        base_date = datetime.utcnow()
        scores_by_date = [
            (0, 0.55),  # Most recent (today) - poorest
            (1, 0.60),  # Yesterday
            (3, 0.70),  # 3 days ago
            (5, 0.75),  # 5 days ago - best
        ]
        for days_ago, score in scores_by_date:
            trend = FormQualityTrend(
                athlete_id=sample_athlete.id,
                exercise_id=sample_exercise.id,
                date=base_date - timedelta(days=days_ago),
                average_form_score=score,
                sets_analyzed=4,
                degradation_rate=0.0,
                high_rpe_poor_form_count=0
            )
            db_session.add(trend)
        db_session.commit()
        
        should_block, reason = form_service.should_block_progression(
            sample_athlete.id, sample_exercise.id
        )
        
        assert should_block is True
        assert reason is not None
        # Should block either due to degrading trend or low score
        assert ("degrading" in reason.lower() or "quality" in reason.lower())


class TestSessionFormQualityTracking:
    """Test tracking form quality for entire sessions."""
    
    def test_track_session_form_quality(
        self, db_session, form_service, sample_athlete, sample_exercise
    ):
        """Test tracking form quality for a session."""
        # Create workout session
        session = WorkoutSession(
            id=1,
            athlete_id=sample_athlete.id,
            workout_day_id=1,
            session_date=datetime.utcnow(),
            duration_minutes=60,
            overall_rpe=8.0
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets with varying form
        for set_number in range(1, 5):
            ex_set = ExerciseSet(
                workout_session_id=session.id,
                exercise_id=sample_exercise.id,
                set_number=set_number,
                weight=100.0,
                reps=5,
                rpe=8.0,
                form_quality="good"
            )
            db_session.add(ex_set)
        
        db_session.commit()
        
        # Track session form quality
        metrics = form_service.track_session_form_quality(session.id)
        
        assert sample_exercise.id in metrics
        exercise_metrics = metrics[sample_exercise.id]
        assert exercise_metrics["average_form_score"] == 0.75  # "good" = 0.75
        assert exercise_metrics["sets_analyzed"] == 4
        assert "degradation_rate" in exercise_metrics
        assert "high_rpe_poor_form_count" in exercise_metrics

