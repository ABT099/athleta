"""
Sequential feature engineering for temporal models.

Extracts time-series sequences from workout data for 1D CNN models.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Athlete, WorkoutSession, ExerciseSet, RecoveryMetrics,
    PerformanceTrend
)
from app.models.workout import PlanEntry, WorkoutPlan
from app.utils.constants import Gender, TrainingExperience
from app.modules.ml.feature_scaler import FeatureScaler


class SequentialFeatureEngineer:
    """
    Extracts temporal sequences from workout data for sequential models.
    
    Creates sequences of fixed length with features per timestep.
    """
    
    def __init__(self, db: Session):
        """
        Initialize sequential feature engineer.
        
        Args:
            db: Database session
        """
        self.db = db
        self.feature_scalers: Dict[int, FeatureScaler] = {}  # athlete_id -> scaler
    
    def extract_sequence_features(
        self,
        athlete_id: int,
        sequence_length: int = 15,
        lookback_sessions: int = 20
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Extract temporal sequence features for current prediction.
        
        Args:
            athlete_id: Athlete ID
            sequence_length: Length of sequence (number of timesteps)
            lookback_sessions: Number of recent sessions to consider
            
        Returns:
            Tuple of (sequence_array, feature_names)
            - sequence_array: (sequence_length, n_features_per_timestep)
            - feature_names: List of feature names per timestep
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None, None
        
        # Get recent performance trends
        recent_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        ).order_by(desc(PerformanceTrend.session_date)).limit(lookback_sessions).all()
        
        if len(recent_trends) < sequence_length:
            return None, None
        
        # Reverse to get chronological order (oldest first)
        recent_trends = list(reversed(recent_trends))
        
        # Get recent recovery metrics
        recent_recovery = self.db.query(RecoveryMetrics).filter(
            RecoveryMetrics.athlete_id == athlete_id
        ).order_by(desc(RecoveryMetrics.date)).limit(lookback_sessions).all()
        recent_recovery = list(reversed(recent_recovery))
        
        # Create recovery lookup by date
        recovery_by_date = {r.date.date(): r for r in recent_recovery}
        
        # Extract features for each timestep
        sequence = []
        feature_names = None
        
        for i, trend in enumerate(recent_trends[:sequence_length]):
            timestep_features = []
            timestep_names = []
            
            # Session-level features
            timestep_features.extend([
                trend.total_volume,
                trend.average_intensity,
                trend.average_rpe,
                trend.readiness_score,
                trend.performance_score,
                trend.fatigue_index
            ])
            timestep_names.extend([
                "volume",
                "intensity",
                "rpe",
                "readiness",
                "performance",
                "fatigue"
            ])
            
            # Recovery features (if available)
            recovery = recovery_by_date.get(trend.session_date.date())
            if recovery:
                timestep_features.extend([
                    recovery.sleep_hours or 0.0,
                    recovery.sleep_quality.value if recovery.sleep_quality else 0.0,
                    float(recovery.overall_soreness) if recovery.overall_soreness else 0.0,
                    float(recovery.stress_level) if recovery.stress_level else 0.0,
                    float(recovery.energy_level) if recovery.energy_level else 0.0
                ])
                timestep_names.extend([
                    "sleep_hours",
                    "sleep_quality",
                    "soreness",
                    "stress",
                    "energy"
                ])
            else:
                # Pad with zeros
                timestep_features.extend([0.0] * 5)
                timestep_names.extend([
                    "sleep_hours",
                    "sleep_quality",
                    "soreness",
                    "stress",
                    "energy"
                ])
            
            # Time-based features
            days_since_start = (trend.session_date - recent_trends[0].session_date).days
            timestep_features.extend([
                float(days_since_start),
                float(trend.session_date.weekday()),  # 0=Monday, 6=Sunday
                float(i) / sequence_length  # Position in sequence (0-1)
            ])
            timestep_names.extend([
                "days_since_start",
                "day_of_week",
                "sequence_position"
            ])
            
            # Rolling statistics (last 3 sessions)
            if i >= 2:
                prev_3_volumes = [recent_trends[j].total_volume for j in range(max(0, i-2), i+1)]
                prev_3_intensities = [recent_trends[j].average_intensity for j in range(max(0, i-2), i+1)]
                
                timestep_features.extend([
                    np.mean(prev_3_volumes),
                    np.std(prev_3_volumes) if len(prev_3_volumes) > 1 else 0.0,
                    np.mean(prev_3_intensities),
                    np.std(prev_3_intensities) if len(prev_3_intensities) > 1 else 0.0
                ])
                timestep_names.extend([
                    "volume_ma3",
                    "volume_std3",
                    "intensity_ma3",
                    "intensity_std3"
                ])
            else:
                timestep_features.extend([0.0] * 4)
                timestep_names.extend([
                    "volume_ma3",
                    "volume_std3",
                    "intensity_ma3",
                    "intensity_std3"
                ])
            
            if feature_names is None:
                feature_names = timestep_names
            
            sequence.append(timestep_features)
        
        # Convert to numpy array
        sequence_array = np.array(sequence, dtype=np.float32)
        
        # Normalize features per athlete
        sequence_array = self._normalize_sequence(athlete_id, sequence_array, feature_names)
        
        return sequence_array, feature_names
    
    def prepare_sequential_dataset(
        self,
        athlete_id: int,
        min_sessions: int = 20,
        sequence_length: int = 15
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[List[str]], Optional[List[str]]]:
        """
        Prepare sequential training dataset using SHIFTED TARGETS.
        
        Creates sliding windows of sequences for training where:
        - Features: sequence of sessions [i-sequence_length : i]
        - Targets: multipliers from session i+1 (the NEXT session)
        
        This properly aligns the prediction task: "Given this sequence of
        past sessions, what multipliers should be used for the NEXT workout?"
        
        No temporal data leakage because:
        - Features only use past sessions
        - Targets use the next session's actual multipliers
        - Outcome weighting uses only the next session's own metrics
        
        Args:
            athlete_id: Athlete ID
            min_sessions: Minimum sessions required
            sequence_length: Length of each sequence
            
        Returns:
            Tuple of (X_sequences, y_targets, feature_names, target_names)
            - X_sequences: (n_samples, sequence_length, n_features)
            - y_targets: (n_samples, n_targets)
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None, None, None, None
        
        # Get all workout sessions
        sessions = self.db.query(WorkoutSession).filter(
            WorkoutSession.athlete_id == athlete_id
        ).order_by(WorkoutSession.session_date).all()
        
        if len(sessions) < min_sessions:
            return None, None, None, None
        
        # Get all performance trends
        all_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        ).order_by(PerformanceTrend.session_date).all()
        
        if len(all_trends) < min_sessions:
            return None, None, None, None
        
        X_sequences = []
        y_targets = []
        feature_names = None
        target_names = ["volume_multiplier", "intensity_multiplier"]
        
        # Create sliding windows using SHIFTED TARGETS
        # Features: sequence of sessions [i-sequence_length : i]
        # Target: multipliers from session i+1 (the NEXT session)
        # This properly aligns: "Given this sequence, predict multipliers for NEXT session"
        for i in range(sequence_length, len(all_trends) - 1):  # Stop 1 before end (need next for target)
            # Extract sequence ending at session i
            sequence_trends = all_trends[i-sequence_length:i]
            
            # Build sequence features
            sequence = []
            for j, trend in enumerate(sequence_trends):
                # Get recovery for this date
                recovery = self.db.query(RecoveryMetrics).filter(
                    RecoveryMetrics.athlete_id == athlete_id,
                    RecoveryMetrics.date == trend.session_date.date()
                ).first()
                
                # Extract timestep features (same as extract_sequence_features)
                timestep_features = self._extract_timestep_features(
                    trend, recovery, j, sequence_length
                )
                
                if feature_names is None:
                    feature_names = [f"feature_{k}" for k in range(len(timestep_features))]
                
                sequence.append(timestep_features)
            
            # SHIFTED TARGET: Get target from session i+1 (the NEXT session)
            # This is what we want to predict: what multipliers should be used next
            next_trend = all_trends[i + 1]
            
            # Get actual multipliers that were used in the NEXT session
            volume_mult = 1.0
            intensity_mult = 1.0
            
            # Try to get from plan entry
            plan_entry = self.db.query(PlanEntry).filter(
                PlanEntry.workout_plan_id.in_(
                    self.db.query(WorkoutPlan.id).filter(
                        WorkoutPlan.athlete_id == athlete_id
                    )
                ),
                PlanEntry.start_date <= next_trend.session_date,
                PlanEntry.end_date >= next_trend.session_date
            ).first()
            
            if plan_entry:
                if plan_entry.ai_adjustments:
                    volume_mult = plan_entry.ai_adjustments.get("volume_multiplier", 1.0)
                    intensity_mult = plan_entry.ai_adjustments.get("intensity_multiplier", 1.0)
                else:
                    volume_mult = plan_entry.target_volume_multiplier
                    intensity_mult = plan_entry.target_intensity_multiplier
            else:
                # Fallback: calculate from volume/intensity ratios
                # Must check both numerator and denominator for None before division
                current_trend = all_trends[i]
                if (next_trend.total_volume is not None and 
                    current_trend.total_volume is not None and 
                    current_trend.total_volume > 0):
                    volume_mult = next_trend.total_volume / current_trend.total_volume
                else:
                    volume_mult = 1.0
                
                if (next_trend.average_intensity is not None and 
                    current_trend.average_intensity is not None and 
                    current_trend.average_intensity > 0):
                    intensity_mult = next_trend.average_intensity / current_trend.average_intensity
                else:
                    intensity_mult = 1.0
            
            # Calculate outcome score based on the NEXT session's metrics
            # This is NOT data leakage - we use the target session's own outcome
            # to weight its own multipliers
            outcome_score = self._calculate_session_outcome_score(next_trend)
            
            # Adjust targets based on outcome (same logic as feature_engineering)
            if outcome_score >= 0.7:
                # Good outcome - these multipliers worked well, learn to predict them
                target_volume = volume_mult
                target_intensity = intensity_mult
            elif outcome_score >= 0.5:
                # Medium outcome - slight adjustment
                target_volume = volume_mult * (1.0 + (outcome_score - 0.5) * 0.1)
                target_intensity = intensity_mult * (1.0 + (outcome_score - 0.5) * 0.05)
            else:
                # Poor outcome - predict opposite direction
                if volume_mult > 1.0:
                    target_volume = 0.95
                elif volume_mult < 1.0:
                    target_volume = 1.05
                else:
                    target_volume = 1.0
                
                if intensity_mult > 1.0:
                    target_intensity = 0.98
                elif intensity_mult < 1.0:
                    target_intensity = 1.02
                else:
                    target_intensity = 1.0
            
            # Clamp to reasonable ranges (consistent with FeatureEngineer)
            target_volume = np.clip(target_volume, 0.7, 1.3)
            target_intensity = np.clip(target_intensity, 0.8, 1.15)
            
            X_sequences.append(sequence)
            y_targets.append([target_volume, target_intensity])
        
        if len(X_sequences) < 5:
            return None, None, None, None
        
        X = np.array(X_sequences, dtype=np.float32)
        y = np.array(y_targets, dtype=np.float32)
        
        # Normalize sequences
        X = self._normalize_sequences(athlete_id, X, feature_names)
        
        return X, y, feature_names, target_names
    
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
    
    def _extract_timestep_features(
        self,
        trend: PerformanceTrend,
        recovery: Optional[RecoveryMetrics],
        position: int,
        sequence_length: int
    ) -> List[float]:
        """Extract features for a single timestep."""
        features = []
        
        # Session metrics
        features.extend([
            trend.total_volume,
            trend.average_intensity,
            trend.average_rpe,
            trend.readiness_score,
            trend.performance_score,
            trend.fatigue_index
        ])
        
        # Recovery metrics
        if recovery:
            features.extend([
                recovery.sleep_hours or 0.0,
                recovery.sleep_quality.value if recovery.sleep_quality else 0.0,
                float(recovery.overall_soreness) if recovery.overall_soreness else 0.0,
                float(recovery.stress_level) if recovery.stress_level else 0.0,
                float(recovery.energy_level) if recovery.energy_level else 0.0
            ])
        else:
            features.extend([0.0] * 5)
        
        # Time features
        features.extend([
            float(position),
            float(trend.session_date.weekday()),
            float(position) / sequence_length
        ])
        
        return features
    
    def _normalize_sequence(
        self,
        athlete_id: int,
        sequence: np.ndarray,
        feature_names: List[str]
    ) -> np.ndarray:
        """
        Normalize sequence features per athlete using fitted scaler.
        
        Uses z-score normalization with persistent statistics.
        If no scaler exists, creates one from this sequence (for prediction).
        
        Args:
            athlete_id: Athlete ID
            sequence: Sequence array (sequence_length, n_features)
            feature_names: Feature names
            
        Returns:
            Normalized sequence
        """
        # If scaler exists, use it (for prediction)
        if athlete_id in self.feature_scalers:
            scaler = self.feature_scalers[athlete_id]
            # Reshape to (1, seq_len, n_features) for transform
            seq_reshaped = sequence.reshape(1, sequence.shape[0], sequence.shape[1])
            normalized = scaler.transform(seq_reshaped)
            return normalized[0]  # Reshape back
        
        # No scaler yet - compute on-the-fly (for single prediction without training)
        # This is less ideal but necessary for backward compatibility
        normalized = sequence.copy()
        for i in range(sequence.shape[1]):
            col = sequence[:, i]
            if np.std(col) > 0:
                normalized[:, i] = (col - np.mean(col)) / (np.std(col) + 1e-8)
        
        return normalized
    
    def _normalize_sequences(
        self,
        athlete_id: int,
        sequences: np.ndarray,
        feature_names: List[str]
    ) -> np.ndarray:
        """
        Normalize all sequences for an athlete using fitted scaler.
        
        Fits scaler on training data, then applies normalization.
        This ensures train/test consistency.
        
        Args:
            athlete_id: Athlete ID
            sequences: (n_samples, sequence_length, n_features)
            feature_names: Feature names
            
        Returns:
            Normalized sequences
        """
        # Create and fit scaler on training data
        scaler = FeatureScaler(feature_names=feature_names)
        normalized = scaler.fit_transform(sequences)
        
        # Store scaler for later use (prediction)
        self.feature_scalers[athlete_id] = scaler
        
        return normalized
    
    def get_scaler(self, athlete_id: int) -> Optional[FeatureScaler]:
        """
        Get fitted scaler for athlete.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            FeatureScaler or None if not fitted
        """
        return self.feature_scalers.get(athlete_id)
    
    def set_scaler(self, athlete_id: int, scaler: FeatureScaler):
        """
        Set scaler for athlete (e.g., when loading from saved model).
        
        Args:
            athlete_id: Athlete ID
            scaler: Fitted FeatureScaler
        """
        self.feature_scalers[athlete_id] = scaler

