"""
Feature engineering for ML models.

Features come from auto-regulation's OWN performance_trends (denormalised
per-session signal, queried locally) plus api-owned inputs (athlete demographics,
recovery history, current PRs, plan focus areas) supplied by the caller from the
Analysis Context (sync prediction) or a TrainingHistory (async retraining).
Targets (the multipliers that were used) come from local performance_trends +
workout_prescription_history. No api-owned sessions/sets are read.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    PerformanceTrend,
    WorkoutPrescriptionHistory,
)
from app.clients.api_client import (
    AthleteDTO,
    ExercisePersonalRecordDTO,
    RecoveryMetricsDTO,
)
from app.modules.analysis import TrainingHistory
from app.utils.constants import Gender, TrainingExperience, FocusArea


class FeatureEngineer:
    """Feature extraction from local trend history + api-owned context inputs."""

    def __init__(self, db: Session):
        self.db = db

    def extract_workout_features(
        self,
        athlete: AthleteDTO,
        recovery_history: List[RecoveryMetricsDTO],
        personal_records: Dict[int, ExercisePersonalRecordDTO],
        focus_areas: Optional[List[str]],
        lookback_sessions: int = 10,
        cutoff_date: Optional[datetime] = None,
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Extract features from recent local performance trends + athlete/recovery/PR
        inputs. ``cutoff_date`` excludes data at/after a date (prevents leakage).
        Returns (feature_array, feature_names) or (None, None) on insufficient data.
        """
        if cutoff_date is not None and cutoff_date.tzinfo is None:
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)

        # Recent local performance trends before the cutoff
        query = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete.id
        )
        if cutoff_date is not None:
            query = query.filter(PerformanceTrend.session_date < cutoff_date)
        recent_trends = query.order_by(desc(PerformanceTrend.session_date)).limit(lookback_sessions).all()

        if len(recent_trends) < 5:
            return None, None

        # Recent recovery (api-owned, supplied), before the cutoff
        def _before_cutoff(d):
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return cutoff_date is None or d < cutoff_date

        recent_recovery = sorted(
            [r for r in (recovery_history or []) if _before_cutoff(r.date)],
            key=lambda r: r.date,
            reverse=True,
        )[:lookback_sessions]

        features: List[float] = []
        feature_names: List[str] = []

        # 1. Athlete demographics
        features.append(athlete.age)
        feature_names.append("age")
        features.append(1.0 if athlete.gender == Gender.MALE else 0.0)
        feature_names.append("gender_male")
        exp_encoding = {
            TrainingExperience.BEGINNER: 0.0,
            TrainingExperience.INTERMEDIATE: 0.5,
            TrainingExperience.ADVANCED: 1.0,
        }
        features.append(exp_encoding[athlete.training_experience])
        feature_names.append("experience_level")
        features.append(athlete.rpe_calibration_factor)
        feature_names.append("rpe_calibration_factor")

        body_weight = float(athlete.body_weight_kg) if athlete.body_weight_kg else 0.0
        features.append(body_weight)
        feature_names.append("body_weight_kg")

        relative_strength = self._calculate_relative_strength_score(personal_records, body_weight)
        features.append(relative_strength if relative_strength is not None else 0.0)
        feature_names.append("relative_strength_score")

        # Focus areas (one-hot)
        focus_area_set = {area.lower() for area in (focus_areas or [])}
        for area in FocusArea:
            features.append(1.0 if area.value in focus_area_set else 0.0)
            feature_names.append(f"focus_{area.value}")

        # 2. Recent performance metrics (last 5 sessions)
        for i, trend in enumerate(recent_trends[:5]):
            features.extend([
                trend.total_volume, trend.average_intensity, trend.average_rpe,
                trend.readiness_score, trend.performance_score, trend.fatigue_index,
            ])
            feature_names.extend([
                f"volume_session_{i+1}", f"intensity_session_{i+1}", f"rpe_session_{i+1}",
                f"readiness_session_{i+1}", f"performance_session_{i+1}", f"fatigue_session_{i+1}",
            ])
        for i in range(len(recent_trends), 5):
            features.extend([0.0] * 6)
            feature_names.extend([
                f"volume_session_{i+1}", f"intensity_session_{i+1}", f"rpe_session_{i+1}",
                f"readiness_session_{i+1}", f"performance_session_{i+1}", f"fatigue_session_{i+1}",
            ])

        # 3. Derived trend features
        if len(recent_trends) >= 3:
            volumes = [t.total_volume for t in recent_trends[:3]]
            rpes = [t.average_rpe for t in recent_trends[:3]]
            readiness = [t.readiness_score for t in recent_trends[:3]]
            features.extend([
                np.mean(volumes), np.std(volumes) if len(volumes) > 1 else 0.0,
                np.mean(rpes), np.std(rpes) if len(rpes) > 1 else 0.0,
                np.mean(readiness), volumes[0] - volumes[-1],
            ])
        else:
            features.extend([0.0] * 6)
        feature_names.extend([
            "avg_volume_3_sessions", "std_volume_3_sessions", "avg_rpe_3_sessions",
            "std_rpe_3_sessions", "avg_readiness_3_sessions", "volume_change_trend",
        ])

        # 4. Recent recovery metrics (last 3)
        if recent_recovery:
            avg_sleep = np.mean([r.sleep_hours for r in recent_recovery[:3] if r.sleep_hours])
            avg_soreness = np.mean([r.overall_soreness for r in recent_recovery[:3] if r.overall_soreness])
            avg_stress = np.mean([r.stress_level for r in recent_recovery[:3] if r.stress_level])
            avg_energy = np.mean([r.energy_level for r in recent_recovery[:3] if r.energy_level])
            features.extend([
                avg_sleep if not np.isnan(avg_sleep) else 7.0,
                avg_soreness if not np.isnan(avg_soreness) else 5.0,
                avg_stress if not np.isnan(avg_stress) else 5.0,
                avg_energy if not np.isnan(avg_energy) else 5.0,
            ])
        else:
            features.extend([7.0, 5.0, 5.0, 5.0])
        feature_names.extend(["avg_sleep_hours", "avg_soreness", "avg_stress", "avg_energy"])

        # 5. Training load metrics (from the latest local trend)
        if recent_trends and recent_trends[0].acute_load is not None:
            features.extend([
                recent_trends[0].acute_load or 0.0,
                recent_trends[0].chronic_load or 0.0,
                recent_trends[0].acwr or 1.0,
                recent_trends[0].training_monotony or 1.0,
            ])
        else:
            features.extend([0.0, 0.0, 1.0, 1.0])
        feature_names.extend(["acute_load", "chronic_load", "acwr", "training_monotony"])

        return np.array(features, dtype=np.float32), feature_names

    def extract_target_variables_shifted(
        self,
        athlete_id: int,
        target_trend: PerformanceTrend,
    ) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
        """
        Targets = the multipliers prescribed around the target session (from local
        workout_prescription_history), outcome-weighted by the target session's own
        local performance_trend.
        """
        if not target_trend:
            return None, None

        volume_mult = 1.0
        intensity_mult = 1.0
        prescription = (
            self.db.query(WorkoutPrescriptionHistory)
            .filter(
                WorkoutPrescriptionHistory.athlete_id == athlete_id,
                WorkoutPrescriptionHistory.prescribed_date <= target_trend.session_date,
            )
            .order_by(desc(WorkoutPrescriptionHistory.prescribed_date))
            .first()
        )
        if prescription:
            volume_mult = prescription.volume_multiplier
            intensity_mult = prescription.intensity_multiplier

        outcome_score = self._calculate_session_outcome_score(target_trend)

        if outcome_score >= 0.7:
            target_volume = volume_mult
            target_intensity = intensity_mult
        elif outcome_score >= 0.5:
            target_volume = volume_mult * (1.0 + (outcome_score - 0.5) * 0.1)
            target_intensity = intensity_mult * (1.0 + (outcome_score - 0.5) * 0.05)
        else:
            target_volume = 0.95 if volume_mult > 1.0 else (1.05 if volume_mult < 1.0 else 1.0)
            target_intensity = 0.98 if intensity_mult > 1.0 else (1.02 if intensity_mult < 1.0 else 1.0)

        target_volume = np.clip(target_volume, 0.7, 1.3)
        target_intensity = np.clip(target_intensity, 0.8, 1.15)

        return (
            np.array([target_volume, target_intensity], dtype=np.float32),
            ["volume_multiplier", "intensity_multiplier"],
        )

    def _calculate_session_outcome_score(self, perf_trend: PerformanceTrend) -> float:
        """Outcome score (0-1) from a session's own local performance trend."""
        scores = []
        if perf_trend.average_rpe:
            rpe = perf_trend.average_rpe
            if 7.0 <= rpe <= 9.0:
                rpe_score = 1.0
            elif 6.0 <= rpe < 7.0 or 9.0 < rpe <= 10.0:
                rpe_score = 0.7
            elif rpe < 6.0:
                rpe_score = 0.4
            else:
                rpe_score = 0.2
            scores.append((rpe_score, 0.40))
        if perf_trend.performance_score is not None:
            scores.append((float(np.clip(perf_trend.performance_score, 0.0, 1.0)), 0.30))
        if perf_trend.readiness_score is not None:
            scores.append((float(np.clip(perf_trend.readiness_score, 0.0, 1.0)), 0.15))
        if perf_trend.fatigue_index is not None:
            scores.append((1.0 - float(np.clip(perf_trend.fatigue_index, 0.0, 1.0)), 0.15))
        if not scores:
            return 0.5
        total_weight = sum(w for _, w in scores)
        weighted = sum(s * w for s, w in scores)
        return float(np.clip(weighted / total_weight if total_weight > 0 else 0.5, 0.0, 1.0))

    def _calculate_relative_strength_score(
        self,
        personal_records: Dict[int, ExercisePersonalRecordDTO],
        body_weight_kg: float,
    ) -> Optional[float]:
        """Best estimated 1RM / body weight, from the context's PR DTOs (Epley)."""
        if body_weight_kg <= 0 or not personal_records:
            return None
        rep_fields = [
            ("one_rep_max", 1), ("three_rep_max", 3), ("five_rep_max", 5),
            ("eight_rep_max", 8), ("ten_rep_max", 10), ("twelve_rep_max", 12),
        ]
        best = 0.0
        for record in personal_records.values():
            for field_name, reps in rep_fields:
                value = getattr(record, field_name, None)
                if value:
                    estimated = value if reps == 1 else value * (1.0 + reps / 30.0)
                    best = max(best, estimated)
        if best <= 0:
            return None
        return round(best / body_weight_kg, 3)

    def prepare_training_dataset(
        self,
        history: TrainingHistory,
        min_sessions: int = 20,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[List[str]], Optional[List[str]]]:
        """
        Prepare the shifted-target training dataset from a TrainingHistory: features
        from before each trend, targets from the next trend. Iterates the local
        performance_trends (one per session).
        """
        trends = sorted(history.performance_trends, key=lambda t: t.session_date)
        if len(trends) < min_sessions:
            return None, None, None, None

        X_list, y_list = [], []
        feature_names = target_names = None

        for i in range(5, len(trends) - 1):
            current = trends[i]
            next_trend = trends[i + 1]

            cutoff = current.session_date
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)

            features, feat_names = self.extract_workout_features(
                athlete=history.athlete,
                recovery_history=history.recovery_history,
                personal_records=history.personal_records,
                focus_areas=history.focus_areas,
                lookback_sessions=10,
                cutoff_date=cutoff,
            )
            if features is None:
                continue

            targets, targ_names = self.extract_target_variables_shifted(
                history.athlete_id, next_trend
            )
            if targets is None:
                continue

            X_list.append(features)
            y_list.append(targets)
            if feature_names is None:
                feature_names, target_names = feat_names, targ_names

        if len(X_list) < 5:
            return None, None, None, None

        return (
            np.array(X_list, dtype=np.float32),
            np.array(y_list, dtype=np.float32),
            feature_names,
            target_names,
        )
