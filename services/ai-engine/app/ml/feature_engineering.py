"""
Feature engineering for ML models.

Extracts and transforms workout data into features suitable for ML training.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Athlete, WorkoutSession, ExerciseSet, RecoveryMetrics,
    PerformanceTrend, ExerciseProgressionTracking, ExercisePersonalRecord
)
from app.models.workout import PlanEntry, WorkoutPlan
from app.utils.constants import Gender, TrainingExperience, TrainingType, FocusArea


class FeatureEngineer:
    """
    Handles feature extraction and engineering from workout data.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_workout_features(
        self,
        athlete_id: int,
        lookback_sessions: int = 10,
        cutoff_date: Optional[datetime] = None
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Extract features from recent workout history.
        
        Features include:
        - Athlete demographics (age, gender, experience)
        - Recent performance metrics
        - Recovery metrics
        - Volume trends
        - Intensity trends
        - RPE trends
        
        Args:
            athlete_id: Athlete ID
            lookback_sessions: Number of recent sessions to include
            cutoff_date: Only include sessions before this date (prevents data leakage)
            
        Returns:
            Tuple of (feature_array, feature_names) or (None, None) if insufficient data
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None, None
        
        # Get recent performance trends before cutoff_date
        query = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        )
        
        if cutoff_date is not None:
            # Ensure cutoff_date is timezone-aware
            if cutoff_date.tzinfo is None:
                cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
            query = query.filter(PerformanceTrend.session_date < cutoff_date)
        
        recent_trends = query.order_by(desc(PerformanceTrend.session_date)).limit(lookback_sessions).all()
        
        if len(recent_trends) < 5:
            # Insufficient data for feature extraction
            return None, None
        
        # Get recent recovery metrics before cutoff_date
        recovery_query = self.db.query(RecoveryMetrics).filter(
            RecoveryMetrics.athlete_id == athlete_id
        )
        
        if cutoff_date is not None:
            # Ensure cutoff_date is timezone-aware
            if cutoff_date.tzinfo is None:
                cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
            recovery_query = recovery_query.filter(RecoveryMetrics.date < cutoff_date)
        
        recent_recovery = recovery_query.order_by(desc(RecoveryMetrics.date)).limit(lookback_sessions).all()
        
        features = []
        feature_names = []
        
        # 1. Athlete demographics
        features.append(athlete.age)
        feature_names.append("age")
        
        features.append(1.0 if athlete.gender == Gender.MALE else 0.0)
        feature_names.append("gender_male")
        
        # Experience level (ordinal encoding)
        exp_encoding = {
            TrainingExperience.BEGINNER: 0.0,
            TrainingExperience.INTERMEDIATE: 0.5,
            TrainingExperience.ADVANCED: 1.0
        }
        features.append(exp_encoding[athlete.training_experience])
        feature_names.append("experience_level")
        
        features.append(athlete.rpe_calibration_factor)
        feature_names.append("rpe_calibration_factor")

        # Body weight (used for relative strength + volume normalization)
        body_weight = float(athlete.body_weight_kg) if athlete.body_weight_kg else 0.0
        features.append(body_weight)
        feature_names.append("body_weight_kg")

        relative_strength = self._calculate_relative_strength_score(athlete_id, body_weight)
        features.append(relative_strength if relative_strength is not None else 0.0)
        feature_names.append("relative_strength_score")

        # Focus area preferences (one-hot encoding)
        focus_area_set = {area.lower() for area in (athlete.focus_areas or [])}
        for area in FocusArea:
            features.append(1.0 if area.value in focus_area_set else 0.0)
            feature_names.append(f"focus_{area.value}")
        
        # 2. Recent performance metrics (last 5 sessions)
        for i, trend in enumerate(recent_trends[:5]):
            features.extend([
                trend.total_volume,
                trend.average_intensity,
                trend.average_rpe,
                trend.readiness_score,
                trend.performance_score,
                trend.fatigue_index
            ])
            feature_names.extend([
                f"volume_session_{i+1}",
                f"intensity_session_{i+1}",
                f"rpe_session_{i+1}",
                f"readiness_session_{i+1}",
                f"performance_session_{i+1}",
                f"fatigue_session_{i+1}"
            ])
        
        # Pad with zeros if fewer than 5 sessions
        for i in range(len(recent_trends), 5):
            features.extend([0.0] * 6)
            feature_names.extend([
                f"volume_session_{i+1}",
                f"intensity_session_{i+1}",
                f"rpe_session_{i+1}",
                f"readiness_session_{i+1}",
                f"performance_session_{i+1}",
                f"fatigue_session_{i+1}"
            ])
        
        # 3. Performance trends (derived features)
        if len(recent_trends) >= 3:
            volumes = [t.total_volume for t in recent_trends[:3]]
            rpes = [t.average_rpe for t in recent_trends[:3]]
            readiness = [t.readiness_score for t in recent_trends[:3]]
            
            features.extend([
                np.mean(volumes),
                np.std(volumes) if len(volumes) > 1 else 0.0,
                np.mean(rpes),
                np.std(rpes) if len(rpes) > 1 else 0.0,
                np.mean(readiness),
                volumes[0] - volumes[-1]  # Volume trend
            ])
            feature_names.extend([
                "avg_volume_3_sessions",
                "std_volume_3_sessions",
                "avg_rpe_3_sessions",
                "std_rpe_3_sessions",
                "avg_readiness_3_sessions",
                "volume_change_trend"
            ])
        else:
            features.extend([0.0] * 6)
            feature_names.extend([
                "avg_volume_3_sessions",
                "std_volume_3_sessions",
                "avg_rpe_3_sessions",
                "std_rpe_3_sessions",
                "avg_readiness_3_sessions",
                "volume_change_trend"
            ])
        
        # 4. Recent recovery metrics (last 3 days)
        if recent_recovery:
            avg_sleep_hours = np.mean([r.sleep_hours for r in recent_recovery[:3] if r.sleep_hours])
            avg_soreness = np.mean([r.overall_soreness for r in recent_recovery[:3] if r.overall_soreness])
            avg_stress = np.mean([r.stress_level for r in recent_recovery[:3] if r.stress_level])
            avg_energy = np.mean([r.energy_level for r in recent_recovery[:3] if r.energy_level])
            
            features.extend([
                avg_sleep_hours if not np.isnan(avg_sleep_hours) else 7.0,
                avg_soreness if not np.isnan(avg_soreness) else 5.0,
                avg_stress if not np.isnan(avg_stress) else 5.0,
                avg_energy if not np.isnan(avg_energy) else 5.0
            ])
        else:
            features.extend([7.0, 5.0, 5.0, 5.0])
        
        feature_names.extend([
            "avg_sleep_hours",
            "avg_soreness",
            "avg_stress",
            "avg_energy"
        ])
        
        # 5. Training load metrics
        if len(recent_trends) >= 1 and recent_trends[0].acute_load is not None:
            features.extend([
                recent_trends[0].acute_load or 0.0,
                recent_trends[0].chronic_load or 0.0,
                recent_trends[0].acwr or 1.0,
                recent_trends[0].training_monotony or 1.0
            ])
        else:
            features.extend([0.0, 0.0, 1.0, 1.0])
        
        feature_names.extend([
            "acute_load",
            "chronic_load",
            "acwr",
            "training_monotony"
        ])
        
        return np.array(features, dtype=np.float32), feature_names
    
    def extract_target_variables_shifted(
        self,
        athlete_id: int,
        target_session_id: int
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Extract target variables using the SHIFTED TARGET approach.
        
        This method extracts targets from a FUTURE session (the session that will
        use the predicted multipliers). The target is the multipliers that were
        actually used in that session, weighted by how well that session went.
        
        This avoids temporal data leakage because:
        - Features are extracted from sessions BEFORE the current session
        - Targets are the multipliers used in the NEXT session
        - Outcome weighting uses only the NEXT session's own metrics
        
        Args:
            athlete_id: Athlete ID
            target_session_id: Session ID to extract targets from (the "next" session)
            
        Returns:
            Tuple of (target_array, target_names) or (None, None)
        """
        # Get the target session (this is the session that will use our predicted multipliers)
        target_session = self.db.query(WorkoutSession).filter(
            WorkoutSession.id == target_session_id
        ).first()
        
        if not target_session:
            return None, None
        
        # Get performance trend for the target session
        target_trend = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.workout_session_id == target_session_id
        ).first()
        
        if not target_trend:
            return None, None
        
        # Get actual multipliers that were used in the target session
        volume_mult = 1.0
        intensity_mult = 1.0
        
        # Try to get from plan entry
        plan_entry = self.db.query(PlanEntry).filter(
            PlanEntry.workout_plan_id.in_(
                self.db.query(WorkoutPlan.id).filter(
                    WorkoutPlan.athlete_id == athlete_id
                )
            ),
            PlanEntry.start_date <= target_trend.session_date,
            PlanEntry.end_date >= target_trend.session_date
        ).first()
        
        if plan_entry:
            if plan_entry.ai_adjustments:
                volume_mult = plan_entry.ai_adjustments.get("volume_multiplier", 1.0)
                intensity_mult = plan_entry.ai_adjustments.get("intensity_multiplier", 1.0)
            else:
                volume_mult = plan_entry.target_volume_multiplier
                intensity_mult = plan_entry.target_intensity_multiplier
        
        # Calculate outcome score based on the TARGET session's metrics
        # This is NOT data leakage because we're using the target session's own outcome
        # to weight its own multipliers (not future sessions)
        outcome_score = self._calculate_session_outcome_score(target_trend)
        
        # Scale multipliers by outcome: high outcome keeps multipliers, low outcome adjusts
        if outcome_score >= 0.7:
            # Good outcome - these multipliers worked well, learn to predict them
            target_volume = volume_mult
            target_intensity = intensity_mult
        elif outcome_score >= 0.5:
            # Medium outcome - slight adjustment toward what might have been better
            target_volume = volume_mult * (1.0 + (outcome_score - 0.5) * 0.1)
            target_intensity = intensity_mult * (1.0 + (outcome_score - 0.5) * 0.05)
        else:
            # Poor outcome - these multipliers didn't work well
            # Learn to predict different values (opposite direction)
            if volume_mult > 1.0:
                target_volume = 0.95  # Should have reduced instead
            elif volume_mult < 1.0:
                target_volume = 1.05  # Should have increased instead
            else:
                target_volume = 1.0
            
            if intensity_mult > 1.0:
                target_intensity = 0.98  # Should have reduced instead
            elif intensity_mult < 1.0:
                target_intensity = 1.02  # Should have increased instead
            else:
                target_intensity = 1.0
        
        # Clamp to reasonable ranges
        target_volume = np.clip(target_volume, 0.7, 1.3)
        target_intensity = np.clip(target_intensity, 0.8, 1.15)
        
        targets = [target_volume, target_intensity]
        target_names = ["volume_multiplier", "intensity_multiplier"]
        
        return np.array(targets, dtype=np.float32), target_names
    
    def _calculate_session_outcome_score(
        self,
        perf_trend: PerformanceTrend
    ) -> float:
        """
        Calculate outcome score based on CURRENT session metrics only.
        
        This avoids temporal data leakage by not looking at future sessions.
        Uses only information available at the time of the session.
        
        Score is based on:
        - RPE in optimal range (7-9 is ideal)
        - Performance score from the session
        - Readiness score (was athlete well-recovered?)
        - Fatigue index (not overly fatigued)
        
        Args:
            perf_trend: Performance trend for the current session
            
        Returns:
            Outcome score (0.0 - 1.0)
        """
        scores = []
        
        # 1. RPE quality (40% weight) - was RPE in optimal training range?
        if perf_trend.average_rpe:
            rpe = perf_trend.average_rpe
            if 7.0 <= rpe <= 9.0:
                # Optimal range for productive training
                rpe_score = 1.0
            elif 6.0 <= rpe < 7.0 or 9.0 < rpe <= 10.0:
                # Acceptable range
                rpe_score = 0.7
            elif rpe < 6.0:
                # Too easy - not challenging enough
                rpe_score = 0.4
            else:  # rpe > 10.0
                # Too hard - overreaching risk
                rpe_score = 0.2
            scores.append(('rpe', rpe_score, 0.40))
        
        # 2. Performance score (30% weight) - direct measure of session quality
        if perf_trend.performance_score is not None:
            # Performance score is typically 0.0-1.0
            perf_score = float(np.clip(perf_trend.performance_score, 0.0, 1.0))
            scores.append(('performance', perf_score, 0.30))
        
        # 3. Readiness score (15% weight) - was the athlete ready for this workout?
        if perf_trend.readiness_score is not None:
            readiness = float(np.clip(perf_trend.readiness_score, 0.0, 1.0))
            scores.append(('readiness', readiness, 0.15))
        
        # 4. Fatigue management (15% weight) - fatigue index not too high
        if perf_trend.fatigue_index is not None:
            fatigue = perf_trend.fatigue_index
            # Lower fatigue is better (score inversely proportional)
            # fatigue_index typically 0-1, where higher = more fatigued
            fatigue_score = 1.0 - float(np.clip(fatigue, 0.0, 1.0))
            scores.append(('fatigue', fatigue_score, 0.15))
        
        if not scores:
            # No metrics available - return neutral
            return 0.5
        
        # Calculate weighted average
        total_weight = sum(weight for _, _, weight in scores)
        weighted_sum = sum(score * weight for _, score, weight in scores)
        
        outcome_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        return float(np.clip(outcome_score, 0.0, 1.0))

    def _calculate_relative_strength_score(
        self,
        athlete_id: int,
        body_weight_kg: float
    ) -> Optional[float]:
        """
        Estimate relative strength using the best available rep-max PR divided by body weight.

        Uses Epley-style conversion: 1RM ≈ weight × (1 + reps / 30).
        """
        if body_weight_kg <= 0:
            return None

        rep_fields = [
            ("one_rep_max", 1),
            ("three_rep_max", 3),
            ("five_rep_max", 5),
            ("eight_rep_max", 8),
            ("ten_rep_max", 10),
            ("twelve_rep_max", 12),
        ]

        pr_records = (
            self.db.query(ExercisePersonalRecord)
            .filter(ExercisePersonalRecord.athlete_id == athlete_id)
            .all()
        )

        if not pr_records:
            return None

        best_estimated_1rm = 0.0
        for record in pr_records:
            for field_name, reps in rep_fields:
                value = getattr(record, field_name, None)
                if value:
                    if reps == 1:
                        estimated_1rm = value
                    else:
                        estimated_1rm = value * (1.0 + reps / 30.0)
                    if estimated_1rm > best_estimated_1rm:
                        best_estimated_1rm = estimated_1rm

        if best_estimated_1rm <= 0:
            return None

        return round(best_estimated_1rm / body_weight_kg, 3)
    
    def prepare_training_dataset(
        self,
        athlete_id: int,
        min_sessions: int = 20
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[List[str]], Optional[List[str]]]:
        """
        Prepare complete training dataset for an athlete using SHIFTED TARGETS.
        
        Uses the shifted target approach where:
        - Features are extracted from sessions BEFORE session i
        - Targets are extracted from session i+1 (the NEXT session)
        
        This properly aligns the prediction task: "Given current state, 
        what multipliers should be used for the NEXT workout?"
        
        Args:
            athlete_id: Athlete ID
            min_sessions: Minimum sessions required
            
        Returns:
            Tuple of (X, y, feature_names, target_names) or (None, None, None, None)
        """
        # Get all workout sessions
        sessions = self.db.query(WorkoutSession).filter(
            WorkoutSession.athlete_id == athlete_id
        ).order_by(WorkoutSession.session_date).all()
        
        if len(sessions) < min_sessions:
            return None, None, None, None
        
        X_list = []
        y_list = []
        feature_names = None
        target_names = None
        
        # Use shifted targets: features from before session i, targets from session i+1
        # We need at least 5 sessions for history, and 1 more for the target
        # So we iterate sessions[5:-1] and use sessions[i+1] as target
        for i in range(5, len(sessions) - 1):  # Stop 1 before end (need next session for target)
            current_session = sessions[i]
            next_session = sessions[i + 1]
            
            # Extract features from sessions before the current one (prevent data leakage)
            # Use current session date as cutoff to ensure we only use past data
            session_date = current_session.session_date
            if session_date.tzinfo is None:
                session_date = session_date.replace(tzinfo=timezone.utc)
            
            features, feat_names = self.extract_workout_features(
                athlete_id, lookback_sessions=10, cutoff_date=session_date
            )
            
            if features is None:
                continue
            
            # Extract targets from the NEXT session (shifted target approach)
            # This is what we're trying to predict: what multipliers to use next
            targets, targ_names = self.extract_target_variables_shifted(
                athlete_id, next_session.id
            )
            
            if targets is None:
                continue
            
            X_list.append(features)
            y_list.append(targets)
            
            if feature_names is None:
                feature_names = feat_names
                target_names = targ_names
        
        # Require minimum 5 samples for meaningful ML training
        # Note: min_sessions from config is for model selection, not sample count validation
        # With N sessions, we produce N-6 samples (5 history + 1 target = 6 overhead)
        # Using a fixed floor of 5 ensures consistent behavior regardless of config
        min_samples_required = 5
        if len(X_list) < min_samples_required:
            return None, None, None, None
        
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        
        return X, y, feature_names, target_names

