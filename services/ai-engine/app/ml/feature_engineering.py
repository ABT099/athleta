"""
Feature engineering for ML models.

Extracts and transforms workout data into features suitable for ML training.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Athlete, WorkoutSession, ExerciseSet, RecoveryMetrics,
    PerformanceTrend, ExerciseProgressionTracking
)
from app.utils.constants import Gender, TrainingExperience, TrainingType


class FeatureEngineer:
    """
    Handles feature extraction and engineering from workout data.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_workout_features(
        self,
        athlete_id: int,
        lookback_sessions: int = 10
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
            
        Returns:
            Tuple of (feature_array, feature_names) or (None, None) if insufficient data
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None, None
        
        # Get recent performance trends
        recent_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        ).order_by(desc(PerformanceTrend.session_date)).limit(lookback_sessions).all()
        
        if len(recent_trends) < 5:
            # Insufficient data for feature extraction
            return None, None
        
        # Get recent recovery metrics
        recent_recovery = self.db.query(RecoveryMetrics).filter(
            RecoveryMetrics.athlete_id == athlete_id
        ).order_by(desc(RecoveryMetrics.date)).limit(lookback_sessions).all()
        
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
    
    def extract_target_variables(
        self,
        athlete_id: int,
        session_id: int
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Extract target variables for supervised learning.
        
        Targets are the actual adjustments that were successful
        (volume_multiplier, intensity_multiplier).
        
        Args:
            athlete_id: Athlete ID
            session_id: Workout session ID
            
        Returns:
            Tuple of (target_array, target_names) or (None, None)
        """
        # Get the session
        session = self.db.query(WorkoutSession).filter(
            WorkoutSession.id == session_id
        ).first()
        
        if not session:
            return None, None
        
        # Get performance trend for this session
        perf_trend = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.workout_session_id == session_id
        ).first()
        
        if not perf_trend:
            return None, None
        
        # Calculate what the "optimal" adjustments would have been
        # based on how well the athlete performed
        performance_score = perf_trend.performance_score
        
        # If performance was good (>0.8), the adjustments were appropriate
        # If performance was poor (<0.5), different adjustments needed
        
        # For now, use simple heuristic targets
        # In production, these would be refined based on actual outcomes
        if performance_score > 0.8:
            volume_mult = 1.05  # Increase volume slightly
            intensity_mult = 1.02  # Increase intensity slightly
        elif performance_score > 0.6:
            volume_mult = 1.0  # Maintain
            intensity_mult = 1.0
        else:
            volume_mult = 0.95  # Reduce volume
            intensity_mult = 0.98  # Reduce intensity
        
        targets = [volume_mult, intensity_mult]
        target_names = ["volume_multiplier", "intensity_multiplier"]
        
        return np.array(targets, dtype=np.float32), target_names
    
    def prepare_training_dataset(
        self,
        athlete_id: int,
        min_sessions: int = 20
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[List[str]], Optional[List[str]]]:
        """
        Prepare complete training dataset for an athlete.
        
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
        
        # For each session, extract features from history and targets from outcome
        for i, session in enumerate(sessions[5:]):  # Skip first 5 (need history)
            # Extract features from sessions before this one
            features, feat_names = self.extract_workout_features(
                athlete_id, lookback_sessions=10
            )
            
            if features is None:
                continue
            
            # Extract targets from this session
            targets, targ_names = self.extract_target_variables(
                athlete_id, session.id
            )
            
            if targets is None:
                continue
            
            X_list.append(features)
            y_list.append(targets)
            
            if feature_names is None:
                feature_names = feat_names
                target_names = targ_names
        
        if len(X_list) < min_sessions:
            return None, None, None, None
        
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        
        return X, y, feature_names, target_names

