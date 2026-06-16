"""
Recovery assessment and readiness scoring.

Readiness is computed from the current session's recovery metrics (in the
Analysis Context); cumulative fatigue is computed from auto-regulation's OWN
denormalised performance_trends (per-session load + cns_load + readiness), so no
api-owned sessions/sets are read.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from app.modules.analysis import AnalysisContext
from app.utils.constants import (
    SleepQuality, SLEEP_QUALITY_MULTIPLIERS,
    Gender, AGE_PROGRESSION_MODIFIERS, GENDER_RECOVERY_MODIFIERS,
    TrainingExperience,
    TRAINING_AGE_EXPERIENCED_THRESHOLD, TRAINING_AGE_VETERAN_THRESHOLD,
    TRAINING_AGE_BOOST_CAP, TRAINING_AGE_BOOST_RATE,
    AGE_PENALTY_OFFSET_EXPERIENCED, AGE_PENALTY_OFFSET_VETERAN,
    AGE_PENALTY_OFFSET_RATE_EXPERIENCED, AGE_PENALTY_OFFSET_RATE_VETERAN,
    RECOVERY_MODIFIER_MIN, RECOVERY_MODIFIER_MAX,
    DURATION_SCORE_DEFAULT,
)


class RecoveryAnalyzer:
    """Analyzes recovery status and calculates readiness scores."""

    def __init__(self, db=None):
        # db retained for interface symmetry; recovery reads come from the
        # context and local trends, not direct queries.
        self.db = db

    @staticmethod
    def calculate_gender_recovery_modifier(
        gender: Gender,
        age: int,
        training_age_years: Optional[int] = None
    ) -> float:
        """
        Gender-specific recovery modifier (fatigue-resistance focused). Individual
        variability typically exceeds gender differences.
        """
        base_modifier = GENDER_RECOVERY_MODIFIERS[gender]
        age_modifier = RecoveryAnalyzer.calculate_age_progression_modifier(age, training_age_years)
        if training_age_years is not None and training_age_years >= TRAINING_AGE_EXPERIENCED_THRESHOLD:
            training_age_boost = min(TRAINING_AGE_BOOST_CAP, training_age_years * TRAINING_AGE_BOOST_RATE)
            age_modifier *= (1.0 + training_age_boost)
        combined_modifier = base_modifier * age_modifier
        combined_modifier = max(RECOVERY_MODIFIER_MIN, min(RECOVERY_MODIFIER_MAX, combined_modifier))
        return round(combined_modifier, 3)

    @staticmethod
    def calculate_age_progression_modifier(
        age: int,
        training_age_years: Optional[int] = None
    ) -> float:
        """Age-based progression modifier; training age can offset age-related decline."""
        base_modifier = 1.0
        for (min_age, max_age), modifier in AGE_PROGRESSION_MODIFIERS.items():
            if min_age <= age <= max_age:
                base_modifier = modifier
                break
        if training_age_years is not None and base_modifier < 1.0:
            if training_age_years >= TRAINING_AGE_VETERAN_THRESHOLD:
                offset = min(AGE_PENALTY_OFFSET_VETERAN, AGE_PENALTY_OFFSET_EXPERIENCED + (training_age_years - TRAINING_AGE_VETERAN_THRESHOLD) * AGE_PENALTY_OFFSET_RATE_VETERAN)
                base_modifier = base_modifier + (1.0 - base_modifier) * offset
            elif training_age_years >= TRAINING_AGE_EXPERIENCED_THRESHOLD:
                offset = min(AGE_PENALTY_OFFSET_EXPERIENCED, 0.05 + (training_age_years - TRAINING_AGE_EXPERIENCED_THRESHOLD) * AGE_PENALTY_OFFSET_RATE_EXPERIENCED)
                base_modifier = base_modifier + (1.0 - base_modifier) * offset
        return round(base_modifier, 3)

    @staticmethod
    def estimate_training_age_from_experience(training_experience: TrainingExperience) -> int:
        """Rough estimate of training age in years from experience level."""
        estimates = {
            TrainingExperience.BEGINNER: 0,
            TrainingExperience.INTERMEDIATE: 2,
            TrainingExperience.ADVANCED: 5,
        }
        return estimates.get(training_experience, 0)

    def calculate_readiness_score(
        self,
        sleep_quality: SleepQuality,
        sleep_hours: Optional[float],
        overall_soreness: Optional[int],
        stress_level: Optional[int],
        energy_level: Optional[int],
        muscle_soreness: Optional[Dict[str, int]] = None
    ) -> float:
        """
        Overall readiness (0.0-1.0). Weighted: sleep 40%, soreness 30%, stress 15%,
        energy 15%.
        """
        scores = []
        weights = []

        sleep_score = self._calculate_sleep_score(sleep_quality, sleep_hours)
        scores.append(sleep_score)
        weights.append(0.40)

        if overall_soreness is not None:
            scores.append((10 - overall_soreness) / 10)
            weights.append(0.30)

        if stress_level is not None:
            scores.append((10 - stress_level) / 10)
            weights.append(0.15)

        if energy_level is not None:
            scores.append(energy_level / 10)
            weights.append(0.15)

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        readiness = sum(score * weight for score, weight in zip(scores, normalized_weights))
        return round(readiness, 3)

    def _calculate_sleep_score(
        self,
        sleep_quality: SleepQuality,
        sleep_hours: Optional[float]
    ) -> float:
        """Sleep score component (quality + duration)."""
        quality_multiplier = SLEEP_QUALITY_MULTIPLIERS[sleep_quality]
        if sleep_hours is None:
            return quality_multiplier
        if 7 <= sleep_hours <= 9:
            duration_score = 1.0
        elif 6 <= sleep_hours < 7 or 9 < sleep_hours <= 10:
            duration_score = 0.9
        elif 5 <= sleep_hours < 6 or 10 < sleep_hours <= 11:
            duration_score = DURATION_SCORE_DEFAULT
        else:
            duration_score = 0.6
        return (quality_multiplier + duration_score) / 2

    def calculate_cumulative_fatigue(
        self,
        ctx: AnalysisContext,
        days_lookback: int = 14
    ) -> Dict:
        """
        Cumulative fatigue (simplified fitness-fatigue model) over recent local
        performance trends. Each trend carries the per-session load signal
        (volume, RPE, CNS load, readiness), so no api-owned data is read.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days_lookback)

        trends = []
        for t in ctx.recent_performance_trends:
            session_date = t.session_date
            if session_date.tzinfo is None:
                session_date = session_date.replace(tzinfo=timezone.utc)
            if session_date >= cutoff:
                trends.append((t, session_date))

        if not trends:
            return {
                "fatigue_level": "low",
                "fatigue_score": 0.0,
                "recommendation": "Ready to train",
                "needs_deload": False
            }

        training_loads = []
        days_ago = []
        for t, session_date in trends:
            days_since = (now - session_date).total_seconds() / 86400
            load = 0.0
            if t.total_volume and t.average_rpe:
                load = (t.total_volume / 1000) * t.average_rpe
            elif t.average_rpe:
                load = t.average_rpe
            # CNS (systemic) fatigue, weighted more heavily
            load = load + ((t.cns_load or 0.0) * 1.5)
            training_loads.append(load)
            days_ago.append(days_since)

        readiness_scores = [t.readiness_score for t, _ in trends if t.readiness_score]
        avg_recovery_score = sum(readiness_scores) / len(readiness_scores) if readiness_scores else 0.7

        weighted_fatigue = 0.0
        for load, day in zip(training_loads, days_ago):
            weighted_fatigue += load * (2 ** (-day / 7))

        fatigue_score = min(weighted_fatigue / 10, 1.0)
        fatigue_score = fatigue_score * (1.5 - avg_recovery_score)
        fatigue_score = min(fatigue_score, 1.0)

        if fatigue_score < 0.3:
            fatigue_level, recommendation, needs_deload = "low", "Ready for high-intensity training", False
        elif fatigue_score < 0.6:
            fatigue_level, recommendation, needs_deload = "moderate", "Continue training with awareness", False
        elif fatigue_score < 0.8:
            fatigue_level, recommendation, needs_deload = "high", "Consider reducing volume or intensity", False
        else:
            fatigue_level, recommendation, needs_deload = "very_high", "Deload week strongly recommended", True

        return {
            "fatigue_level": fatigue_level,
            "fatigue_score": round(fatigue_score, 3),
            "recommendation": recommendation,
            "needs_deload": needs_deload,
            "average_recovery_score": round(avg_recovery_score, 3),
            "workouts_analyzed": len(trends),
            "note": "Fatigue includes CNS (systemic) load denormalised onto performance trends"
        }

    def get_recovery_recommendations(
        self,
        readiness_score: float,
        fatigue_level: str,
        sleep_quality: Optional[SleepQuality]
    ) -> List[str]:
        """Generate actionable recovery recommendations."""
        recommendations = []
        if readiness_score < 0.5:
            recommendations.append("Consider skipping or significantly reducing today's training")
            recommendations.append("Focus on recovery: sleep, nutrition, stress management")
        elif readiness_score < 0.7:
            recommendations.append("Reduce training volume by 20-30%")
            recommendations.append("Focus on technique and lighter loads")

        if sleep_quality in [SleepQuality.POOR, SleepQuality.NOT_BAD]:
            recommendations.append("Prioritize sleep quality and duration (aim for 7-9 hours)")
            recommendations.append("Consider sleep hygiene improvements: dark room, cool temperature, no screens before bed")

        if fatigue_level in ["high", "very_high"]:
            recommendations.append("Consider implementing a deload week (50% volume, 90% intensity)")
            recommendations.append("Increase rest days or active recovery sessions")
            recommendations.append("Ensure adequate protein intake (1.6-2.2g/kg bodyweight)")

        if not recommendations:
            recommendations.append("Recovery status is good - maintain current practices")
            recommendations.append("Continue monitoring sleep, nutrition, and stress")

        return recommendations
