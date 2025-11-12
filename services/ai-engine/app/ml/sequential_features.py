"""
Sequential feature engineering for temporal models.

Extracts time-series sequences from workout data for 1D CNN models.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Athlete, WorkoutSession, ExerciseSet, RecoveryMetrics,
    PerformanceTrend
)
from app.utils.constants import Gender, TrainingExperience


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
        self.feature_scalers: Dict[int, Dict[str, Tuple[float, float]]] = {}
    
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
        Prepare sequential training dataset.
        
        Creates sliding windows of sequences for training.
        
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
        
        # Create sliding windows
        # For each session after sequence_length, use previous sessions as input
        for i in range(sequence_length, len(all_trends)):
            # Extract sequence ending at session i-1
            sequence_trends = all_trends[i-sequence_length:i]
            
            # Build sequence features
            sequence = []
            for trend in sequence_trends:
                # Get recovery for this date
                recovery = self.db.query(RecoveryMetrics).filter(
                    RecoveryMetrics.athlete_id == athlete_id,
                    RecoveryMetrics.date == trend.session_date.date()
                ).first()
                
                # Extract timestep features (same as extract_sequence_features)
                timestep_features = self._extract_timestep_features(
                    trend, recovery, i - sequence_length, sequence_length
                )
                
                if feature_names is None:
                    feature_names = [f"feature_{j}" for j in range(len(timestep_features))]
                
                sequence.append(timestep_features)
            
            # Get target from session i
            current_trend = all_trends[i]
            prev_trend = all_trends[i-1] if i > 0 else current_trend
            
            # Calculate actual multipliers
            volume_mult = current_trend.total_volume / prev_trend.total_volume if prev_trend.total_volume > 0 else 1.0
            intensity_mult = current_trend.average_intensity / prev_trend.average_intensity if prev_trend.average_intensity > 0 else 1.0
            
            # Clamp to reasonable ranges
            volume_mult = np.clip(volume_mult, 0.5, 1.5)
            intensity_mult = np.clip(intensity_mult, 0.7, 1.2)
            
            X_sequences.append(sequence)
            y_targets.append([volume_mult, intensity_mult])
        
        if len(X_sequences) < 5:
            return None, None, None, None
        
        X = np.array(X_sequences, dtype=np.float32)
        y = np.array(y_targets, dtype=np.float32)
        
        # Normalize sequences
        X = self._normalize_sequences(athlete_id, X, feature_names)
        
        return X, y, feature_names, target_names
    
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
        Normalize sequence features per athlete.
        
        Uses min-max normalization based on athlete's historical data.
        """
        # For now, simple z-score normalization
        # In production, would use athlete-specific scalers
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
        Normalize all sequences for an athlete.
        
        Args:
            athlete_id: Athlete ID
            sequences: (n_samples, sequence_length, n_features)
            feature_names: Feature names
            
        Returns:
            Normalized sequences
        """
        normalized = sequences.copy()
        
        # Normalize each feature across all sequences
        for feat_idx in range(sequences.shape[2]):
            all_values = sequences[:, :, feat_idx].flatten()
            if np.std(all_values) > 0:
                mean_val = np.mean(all_values)
                std_val = np.std(all_values)
                normalized[:, :, feat_idx] = (sequences[:, :, feat_idx] - mean_val) / (std_val + 1e-8)
        
        return normalized

