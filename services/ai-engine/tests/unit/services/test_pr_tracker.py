"""
Tests for Personal Record (PR) tracking service.

Tests PR detection, storage, retrieval, and integration with workout system.
"""
import pytest
import json
from datetime import datetime, timedelta, timezone
from app.services.pr_tracker import PRTrackerService
from app.models import (
    Athlete, Exercise, WorkoutPlan, WorkoutDay, WorkoutSession, ExerciseSet,
    ExercisePersonalRecord
)
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, PeriodizationModel
)
from tests.factories import ExerciseFactory


class TestPRDetection:
    """Test PR detection from workout sessions."""
    
    def test_detect_new_5rm_pr(self, db_session):
        """Test detection of new 5RM PR."""
        # Create athlete and exercise
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create workout session
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Push Day",
            order_in_week=1,
            target_muscle_groups=["chest"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets: 5 reps at 100kg (new 5RM PR)
        set1 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight=100.0,
            reps=5,
            rpe=9.0
        )
        db_session.add(set1)
        db_session.commit()
        
        # Detect PRs
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_and_update_prs(session.id)
        
        # Check results - should detect 5RM, volume, and rep PRs
        assert len(result["achievements"]) >= 1
        assert any("5RM PR" in a for a in result["achievements"])
        assert len(result["updates"]) >= 1
        
        # Find 5RM update
        rm_updates = [u for u in result["updates"] if u["pr_type"] == "5RM"]
        assert len(rm_updates) == 1
        assert rm_updates[0]["new_value"] == 100.0
        assert rm_updates[0]["is_new_pr"] is True
        
        # Verify PR record was created
        pr_record = db_session.query(ExercisePersonalRecord).filter(
            ExercisePersonalRecord.athlete_id == athlete.id,
            ExercisePersonalRecord.exercise_id == exercise.id
        ).first()
        
        assert pr_record is not None
        assert pr_record.five_rep_max == 100.0
        # Total PR count includes volume and rep PRs
        assert pr_record.total_pr_count >= 1
    
    def test_detect_multiple_rep_max_prs(self, db_session):
        """Test detection of multiple rep-max PRs in one session."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Squat",
            muscles=[("quadriceps", 90)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.STRENGTH,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Leg Day",
            order_in_week=1,
            target_muscle_groups=["quadriceps"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets: 1RM at 150kg, 3RM at 140kg, 5RM at 130kg
        set1 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight=150.0,
            reps=1,
            rpe=10.0
        )
        set2 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=2,
            weight=140.0,
            reps=3,
            rpe=9.5
        )
        set3 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=3,
            weight=130.0,
            reps=5,
            rpe=9.0
        )
        db_session.add_all([set1, set2, set3])
        db_session.commit()
        
        # Detect PRs
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_and_update_prs(session.id)
        
        # Should detect 3 PRs
        assert len(result["updates"]) >= 3
        
        pr_types = [u["pr_type"] for u in result["updates"]]
        assert "1RM" in pr_types
        assert "3RM" in pr_types
        assert "5RM" in pr_types
        
        # Verify PR record
        pr_record = db_session.query(ExercisePersonalRecord).filter(
            ExercisePersonalRecord.athlete_id == athlete.id,
            ExercisePersonalRecord.exercise_id == exercise.id
        ).first()
        
        assert pr_record.one_rep_max == 150.0
        assert pr_record.three_rep_max == 140.0
        assert pr_record.five_rep_max == 130.0
        # Total PR count includes volume and rep PRs
        assert pr_record.total_pr_count >= 3
    
    def test_detect_volume_pr(self, db_session):
        """Test detection of volume PR (total weight×reps)."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Deadlift",
            muscles=[("lats", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Pull Day",
            order_in_week=1,
            target_muscle_groups=["back"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.flush()
        
        # Create sets: 3 sets × 100kg × 10 reps = 3000kg total volume
        for i in range(3):
            set_record = ExerciseSet(
                workout_session_id=session.id,
                exercise_id=exercise.id,
                set_number=i + 1,
                weight=100.0,
                reps=10,
                rpe=8.0
            )
            db_session.add(set_record)
        db_session.commit()
        
        # Detect PRs
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_and_update_prs(session.id)
        
        # Should detect volume PR
        volume_updates = [u for u in result["updates"] if u["pr_type"] == "volume"]
        assert len(volume_updates) == 1
        assert volume_updates[0]["new_value"] == 3000.0  # 3 × 100 × 10
        
        # Verify PR record
        pr_record = db_session.query(ExercisePersonalRecord).filter(
            ExercisePersonalRecord.athlete_id == athlete.id,
            ExercisePersonalRecord.exercise_id == exercise.id
        ).first()
        
        assert pr_record.max_volume_session == 3000.0
    
    def test_no_pr_if_lower_than_existing(self, db_session):
        """Test that lower weights don't update existing PRs."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create existing PR record with 5RM = 100kg
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=7),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.flush()
        
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Push Day",
            order_in_week=1,
            target_muscle_groups=["chest"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.flush()
        
        # Create set: 5 reps at 95kg (lower than PR)
        set1 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight=95.0,
            reps=5,
            rpe=8.0
        )
        db_session.add(set1)
        db_session.commit()
        
        # Detect PRs
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_and_update_prs(session.id)
        
        # Should not detect new PR
        pr_updates = [u for u in result["updates"] if u["pr_type"] == "5RM"]
        assert len(pr_updates) == 0
        
        # PR should remain unchanged
        db_session.refresh(pr_record)
        assert pr_record.five_rep_max == 100.0
        # Total count may include volume/rep PRs even if weight PR didn't change
        assert pr_record.total_pr_count >= 1


class TestPRRetrieval:
    """Test PR retrieval for rep ranges."""
    
    def test_get_pr_for_rep_range(self, db_session):
        """Test getting PR for specific rep range."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create PR record
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=7),
            ten_rep_max=85.0,
            ten_rm_date=datetime.now(timezone.utc) - timedelta(days=14),
            total_pr_count=2
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        
        # Test getting 5RM for target of 5 reps
        pr_data = pr_tracker.get_pr_for_rep_range(exercise.id, athlete.id, 5.0)
        assert pr_data is not None
        assert pr_data["weight"] == 100.0
        assert pr_data["reps"] == 5
        assert pr_data["rep_max"] == 5
        
        # Test getting 10RM for target of 10 reps
        pr_data = pr_tracker.get_pr_for_rep_range(exercise.id, athlete.id, 10.0)
        assert pr_data is not None
        assert pr_data["weight"] == 85.0
        assert pr_data["reps"] == 10
    
    def test_get_pr_for_rep_range_no_pr(self, db_session):
        """Test getting PR when none exists."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="New Exercise",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        pr_tracker = PRTrackerService(db_session)
        pr_data = pr_tracker.get_pr_for_rep_range(exercise.id, athlete.id, 5.0)
        
        assert pr_data is None


class TestTrainingPercentage:
    """Test training percentage calculation."""
    
    def test_training_percentage_deload(self, db_session):
        """Test training percentage for deload week."""
        pr_tracker = PRTrackerService(db_session)
        
        pct = pr_tracker.calculate_training_percentage(
            week_number=4,
            phase="accumulation",
            is_deload=True
        )
        
        assert pct == 0.75  # 75% for deload
    
    def test_training_percentage_by_phase(self, db_session):
        """Test training percentage varies by phase."""
        pr_tracker = PRTrackerService(db_session)
        
        # Accumulation phase
        pct_accum = pr_tracker.calculate_training_percentage(
            week_number=1,
            phase="accumulation",
            is_deload=False
        )
        assert 0.80 <= pct_accum <= 0.85
        
        # Intensification phase
        pct_intens = pr_tracker.calculate_training_percentage(
            week_number=1,
            phase="intensification",
            is_deload=False
        )
        assert 0.85 <= pct_intens <= 0.90
        
        # Realization phase
        pct_real = pr_tracker.calculate_training_percentage(
            week_number=1,
            phase="realization",
            is_deload=False
        )
        assert 0.90 <= pct_real <= 0.95
        
        # Intensification should be higher than accumulation
        assert pct_intens > pct_accum
        # Realization should be highest
        assert pct_real > pct_intens


class TestPlateauDetection:
    """Test plateau detection."""
    
    def test_detect_plateau_no_pr(self, db_session):
        """Test plateau detection when no PR exists."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_plateau(exercise.id, athlete.id, weeks=4)
        
        assert result["is_plateaued"] is False
        assert result["weeks_since_pr"] is None
    
    def test_detect_plateau_recent_pr(self, db_session):
        """Test that recent PR doesn't trigger plateau."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create PR from 2 weeks ago
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=14),
            last_pr_date=datetime.now(timezone.utc) - timedelta(days=14),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_plateau(exercise.id, athlete.id, weeks=4)
        
        assert result["is_plateaued"] is False
        assert 1.5 <= result["weeks_since_pr"] <= 2.5
    
    def test_detect_plateau_old_pr(self, db_session):
        """Test that old PR triggers plateau."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create PR from 5 weeks ago
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=35),
            last_pr_date=datetime.now(timezone.utc) - timedelta(days=35),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        result = pr_tracker.detect_plateau(exercise.id, athlete.id, weeks=4)
        
        assert result["is_plateaued"] is True
        assert 4.5 <= result["weeks_since_pr"] <= 5.5
        assert result["message"] is not None
        assert "No PRs" in result["message"]


class TestPRComparison:
    """Test PR comparison functionality."""
    
    def test_compare_to_pr_new_pr(self, db_session):
        """Test comparison when set beats PR."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create existing PR: 5RM = 100kg
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=7),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        
        # Compare set that beats PR: 105kg × 5 reps
        best_set = {"weight": 105.0, "reps": 5}
        result = pr_tracker.compare_to_pr(exercise.id, athlete.id, best_set)
        
        assert result["is_pr"] is True
        assert result["diff_kg"] == 5.0
        assert result["pr_trend"] == "improving"
        assert result["pr_weight"] == 100.0
    
    def test_compare_to_pr_maintaining(self, db_session):
        """Test comparison when set is close to PR."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create existing PR: 5RM = 100kg
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=7),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        
        # Compare set close to PR: 98kg × 5 reps (within 2.5kg)
        best_set = {"weight": 98.0, "reps": 5}
        result = pr_tracker.compare_to_pr(exercise.id, athlete.id, best_set)
        
        assert result["is_pr"] is False
        assert result["diff_kg"] == -2.0
        assert result["pr_trend"] == "maintaining"
    
    def test_compare_to_pr_regressing(self, db_session):
        """Test comparison when set is far below PR."""
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        # Create existing PR: 5RM = 100kg
        pr_record = ExercisePersonalRecord(
            athlete_id=athlete.id,
            exercise_id=exercise.id,
            five_rep_max=100.0,
            five_rm_date=datetime.now(timezone.utc) - timedelta(days=7),
            total_pr_count=1
        )
        db_session.add(pr_record)
        db_session.commit()
        
        pr_tracker = PRTrackerService(db_session)
        
        # Compare set far below PR: 90kg × 5 reps (more than 5kg below)
        best_set = {"weight": 90.0, "reps": 5}
        result = pr_tracker.compare_to_pr(exercise.id, athlete.id, best_set)
        
        assert result["is_pr"] is False
        assert result["diff_kg"] == -10.0
        assert result["pr_trend"] == "regressing"


class TestPRIntegration:
    """Test PR integration with workout system."""
    
    def test_pr_detection_in_workout_flow(self, db_session):
        """Test that PRs are detected during normal workout completion flow."""
        from app.services.plan_updater import PlanUpdaterService
        
        athlete = Athlete(
            age=25,
            gender=Gender.MALE,
            training_experience=TrainingExperience.INTERMEDIATE,
            rpe_calibration_factor=1.0
        )
        db_session.add(athlete)
        db_session.flush()
        
        exercise = ExerciseFactory.create(
            db_session,
            name="Bench Press",
            muscles=[("mid_chest", 95)],
            exercise_type="compound"
        )
        db_session.add(exercise)
        db_session.flush()
        
        plan = WorkoutPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            training_type=TrainingType.HYPERTROPHY,
            periodization_model=PeriodizationModel.LINEAR,
            frequency=3,
            duration_weeks=12,
            start_date=datetime.now(timezone.utc)
        )
        db_session.add(plan)
        db_session.flush()
        
        workout_day = WorkoutDay(
            workout_plan_id=plan.id,
            name="Push Day",
            order_in_week=1,
            target_muscle_groups=["chest"]
        )
        db_session.add(workout_day)
        db_session.flush()
        
        from app.models import WorkoutDayExercise
        from app.utils.constants import TrainingPhase
        
        workout_exercise = WorkoutDayExercise(
            workout_day_id=workout_day.id,
            exercise_id=exercise.id,
            order_in_workout=1,
            target_sets_min=3,
            target_sets_max=4,
            target_reps_min=5,
            target_reps_max=8,
            is_primary=1
        )
        db_session.add(workout_exercise)
        db_session.flush()
        
        session = WorkoutSession(
            athlete_id=athlete.id,
            workout_day_id=workout_day.id,
            session_date=datetime.now(timezone.utc)
        )
        db_session.add(session)
        db_session.flush()
        
        # Create set: 5 reps at 100kg (new PR)
        set1 = ExerciseSet(
            workout_session_id=session.id,
            exercise_id=exercise.id,
            set_number=1,
            weight=100.0,
            reps=5,
            rpe=9.0
        )
        db_session.add(set1)
        db_session.commit()
        
        # Simulate PR detection (as would happen in workout completion)
        pr_tracker = PRTrackerService(db_session)
        pr_updates = pr_tracker.detect_and_update_prs(session.id)
        
        # Verify PR was detected
        assert len(pr_updates["achievements"]) > 0
        
        # Verify PR is stored in database
        from app.models import ExercisePersonalRecord
        pr_record = db_session.query(ExercisePersonalRecord).filter(
            ExercisePersonalRecord.athlete_id == athlete.id,
            ExercisePersonalRecord.exercise_id == exercise.id
        ).first()
        
        assert pr_record is not None
        assert pr_record.five_rep_max == 100.0
        
        # Verify PR can be retrieved
        pr_data = pr_tracker.get_pr_for_rep_range(exercise.id, athlete.id, 5.0)
        assert pr_data is not None
        assert pr_data["weight"] == 100.0
        assert pr_data["reps"] == 5

