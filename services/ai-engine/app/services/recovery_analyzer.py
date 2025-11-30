"""
Recovery assessment and readiness scoring service.

Evaluates athlete readiness based on sleep, soreness, stress, and other wellness markers.
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import RecoveryMetrics, WorkoutSession, Athlete
from app.utils.constants import (
    SleepQuality, SLEEP_QUALITY_MULTIPLIERS, MuscleGroup, 
    Gender, AGE_PROGRESSION_MODIFIERS, GENDER_RECOVERY_MODIFIERS,
    TrainingExperience
)


class RecoveryAnalyzer:
    """
    Analyzes recovery status and calculates readiness scores.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def calculate_gender_recovery_modifier(
        gender: Gender, 
        age: int, 
        training_age_years: Optional[int] = None
    ) -> float:
        """
        Calculate gender-specific recovery modifier with nuanced approach.
        
        Women show greater fatigue resistance in submaximal work, but recovery
        rates are more nuanced and vary by exercise type, volume, and individual factors.
        Individual variability within genders is often larger than between-gender differences.
        
        References:
        - Kraemer et al. (2001): Gender differences in recovery from resistance training
        - Hunter (2014): Sex differences in human fatigability
        - Individual variability often exceeds gender differences
        
        Args:
            gender: Athlete gender
            age: Chronological age
            training_age_years: Years of consistent training (optional, can be inferred)
            
        Returns:
            Recovery multiplier (1.0 = baseline)
            Note: Individual variability is typically larger than gender differences
        """
        # Base modifier focuses on fatigue resistance rather than blanket "faster recovery"
        # Women show ~10% greater fatigue resistance in submaximal work
        base_modifier = GENDER_RECOVERY_MODIFIERS[gender]
        
        # Age adjustments (softer than before, with wider ranges)
        # Well-trained older athletes may progress similar to younger novices
        age_modifier = RecoveryAnalyzer.calculate_age_progression_modifier(age, training_age_years)
        
        # Training age consideration: experienced athletes adapt better regardless of age
        if training_age_years is not None and training_age_years >= 5:
            # Experienced athletes have better recovery capacity
            training_age_boost = min(0.05, training_age_years * 0.01)  # Up to 5% boost
            age_modifier *= (1.0 + training_age_boost)
        
        # Combine gender and age modifiers
        # Individual variability is emphasized - these are starting points
        combined_modifier = base_modifier * age_modifier
        
        # Clamp to reasonable range (0.7 - 1.2)
        combined_modifier = max(0.7, min(1.2, combined_modifier))
        
        return round(combined_modifier, 3)
    
    @staticmethod
    def calculate_age_progression_modifier(
        age: int, 
        training_age_years: Optional[int] = None
    ) -> float:
        """
        Calculate age-based progression rate modifier with softer ranges.
        
        Distinguishes between chronological age and training age.
        Masters athletes (40+) can still achieve significant gains with proper programming.
        Well-trained older athletes may progress similar to younger novices.
        
        References:
        - Schoenfeld et al. (2016): Effects of age on muscle hypertrophy
        - Ahtiainen et al. (2016): Training adaptations across age groups
        - Tanaka & Seals (2008): Aging athlete adaptations
        
        Args:
            age: Chronological age
            training_age_years: Years of consistent training (optional)
            
        Returns:
            Progression multiplier (1.0 = baseline)
        """
        # Find base modifier from age brackets (softer ranges than before)
        base_modifier = 1.0
        for (min_age, max_age), modifier in AGE_PROGRESSION_MODIFIERS.items():
            if min_age <= age <= max_age:
                base_modifier = modifier
                break
        
        # If training age is provided, adjust based on training experience
        # Well-trained older athletes can offset age-related decline
        if training_age_years is not None and base_modifier < 1.0:
            if training_age_years >= 10:
                # Very experienced: offset 10-20% of age penalty
                # At 10 years: 10% offset, increases by 2% per additional year, capped at 20%
                offset = min(0.2, 0.1 + (training_age_years - 10) * 0.02)
                base_modifier = base_modifier + (1.0 - base_modifier) * offset
            elif training_age_years >= 5:
                # Moderately experienced: offset 5-10% of age penalty
                # At 5 years: 5% offset, increases by 1% per additional year, capped at 10%
                offset = min(0.1, 0.05 + (training_age_years - 5) * 0.01)
                base_modifier = base_modifier + (1.0 - base_modifier) * offset
        
        return round(base_modifier, 3)
    
    @staticmethod
    def estimate_training_age_from_experience(training_experience: TrainingExperience) -> int:
        """
        Estimate training age in years from experience level.
        
        This is a rough estimate - actual training age should be provided when available.
        
        Args:
            training_experience: Training experience enum
            
        Returns:
            Estimated years of training
        """
        from app.utils.constants import TrainingExperience
        
        estimates = {
            TrainingExperience.BEGINNER: 0,  # 0-1 years
            TrainingExperience.INTERMEDIATE: 2,  # 2-4 years
            TrainingExperience.ADVANCED: 5,  # 5+ years
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
        Calculate overall readiness score (0.0 - 1.0).
        
        Weighted formula:
        - Sleep: 40%
        - Soreness: 30%
        - Stress: 15%
        - Energy: 15%
        
        Args:
            sleep_quality: Sleep quality enum
            sleep_hours: Hours of sleep
            overall_soreness: 1-10 scale (1=none, 10=extreme)
            stress_level: 1-10 scale
            energy_level: 1-10 scale (1=exhausted, 10=energized)
            muscle_soreness: Dict of muscle-specific soreness
            
        Returns:
            Readiness score (0.0 - 1.0)
        """
        scores = []
        weights = []
        
        # Sleep score (40% weight - increased from 35%)
        sleep_score = self._calculate_sleep_score(sleep_quality, sleep_hours)
        scores.append(sleep_score)
        weights.append(0.40)
        
        # Soreness score (30% weight - increased from 25%)
        if overall_soreness is not None:
            # Invert soreness: 10 = very sore = low score
            soreness_score = (10 - overall_soreness) / 10
            scores.append(soreness_score)
            weights.append(0.30)
        
        # Stress score (15% weight - unchanged)
        if stress_level is not None:
            # Lower stress = better readiness
            stress_score = (10 - stress_level) / 10
            scores.append(stress_score)
            weights.append(0.15)
        
        # Energy score (15% weight - unchanged)
        if energy_level is not None:
            energy_score = energy_level / 10
            scores.append(energy_score)
            weights.append(0.15)
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Calculate weighted average
        readiness = sum(score * weight for score, weight in zip(scores, normalized_weights))
        
        return round(readiness, 3)
    
    def _calculate_sleep_score(
        self,
        sleep_quality: SleepQuality,
        sleep_hours: Optional[float]
    ) -> float:
        """
        Calculate sleep score component.
        
        Args:
            sleep_quality: Sleep quality enum
            sleep_hours: Hours of sleep
            
        Returns:
            Sleep score (0.0 - 1.0)
        """
        # Base score from quality
        quality_multiplier = SLEEP_QUALITY_MULTIPLIERS[sleep_quality]
        
        if sleep_hours is None:
            return quality_multiplier
        
        # Optimal sleep: 7-9 hours
        # Penalize if too little or too much
        if 7 <= sleep_hours <= 9:
            duration_score = 1.0
        elif 6 <= sleep_hours < 7 or 9 < sleep_hours <= 10:
            duration_score = 0.9
        elif 5 <= sleep_hours < 6 or 10 < sleep_hours <= 11:
            duration_score = 0.75
        else:
            duration_score = 0.6
        
        # Combine quality and duration
        return (quality_multiplier + duration_score) / 2
    
    def assess_muscle_recovery(
        self,
        athlete_id: int,
        muscle_group: MuscleGroup,
        days_lookback: int = 7
    ) -> Dict:
        """
        Assess recovery status for a specific muscle group.
        
        Args:
            athlete_id: Athlete ID
            muscle_group: Muscle group to assess
            days_lookback: Days to look back for workouts
            
        Returns:
            Dict with recovery status and metrics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Get recent workouts targeting this muscle
        recent_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .order_by(WorkoutSession.session_date.desc())
            .all()
        )
        
        # Calculate days since last workout for this muscle
        # (Simplified - in production would need to check workout_day target muscles)
        if recent_sessions:
            last_workout = recent_sessions[0]
            current_time = datetime.now(timezone.utc)
            session_time = last_workout.session_date
            if session_time.tzinfo is None:
                session_time = session_time.replace(tzinfo=timezone.utc)
            
            days_since_workout = (current_time - session_time).days
        else:
            days_since_workout = 7  # No recent workout
        
        # Get recent soreness data
        recent_recovery = (
            self.db.query(RecoveryMetrics)
            .filter(
                RecoveryMetrics.athlete_id == athlete_id,
                RecoveryMetrics.date >= cutoff_date
            )
            .order_by(RecoveryMetrics.date.desc())
            .first()
        )
        
        muscle_soreness_level = 1  # Default: no soreness
        if recent_recovery and recent_recovery.muscle_soreness:
            try:
                soreness_dict = json.loads(recent_recovery.muscle_soreness)
                muscle_soreness_level = soreness_dict.get(muscle_group.value, 1)
            except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
                # AttributeError: JSON parses to non-dict (list/string), .get() fails
                pass
        
        # Determine recovery status
        # Large muscles need 72h, medium 60h, small 48h
        from app.utils.constants import MUSCLE_SIZE_MAP, RECOVERY_TIME_HOURS
        
        muscle_size = MUSCLE_SIZE_MAP.get(muscle_group)
        required_recovery_hours = RECOVERY_TIME_HOURS.get(muscle_size, 48)
        required_recovery_days = required_recovery_hours / 24
        
        hours_since_workout = days_since_workout * 24
        recovery_percentage = min(hours_since_workout / required_recovery_hours, 1.0)
        
        # Adjust for soreness
        soreness_penalty = (muscle_soreness_level - 1) / 9  # Scale to 0-1
        recovery_percentage = max(recovery_percentage - soreness_penalty, 0.0)
        
        is_recovered = recovery_percentage >= 0.9 and muscle_soreness_level <= 3
        
        return {
            "muscle_group": muscle_group.value,
            "is_recovered": is_recovered,
            "recovery_percentage": round(recovery_percentage, 2),
            "days_since_workout": days_since_workout,
            "soreness_level": muscle_soreness_level,
            "required_recovery_days": required_recovery_days,
            "recommendation": self._get_recovery_recommendation(recovery_percentage, muscle_soreness_level)
        }
    
    def _get_recovery_recommendation(
        self,
        recovery_percentage: float,
        soreness_level: int
    ) -> str:
        """
        Get recovery recommendation based on status.
        
        Args:
            recovery_percentage: Recovery percentage (0.0 - 1.0)
            soreness_level: Soreness level (1-10)
            
        Returns:
            Recommendation string
        """
        if recovery_percentage >= 0.9 and soreness_level <= 2:
            return "Fully recovered - ready for intense training"
        elif recovery_percentage >= 0.7 and soreness_level <= 4:
            return "Mostly recovered - can train with moderate intensity"
        elif recovery_percentage >= 0.5 and soreness_level <= 6:
            return "Partially recovered - light training recommended"
        else:
            return "Not recovered - rest or very light work only"
    
    def calculate_cumulative_fatigue(
        self,
        athlete_id: int,
        days_lookback: int = 14
    ) -> Dict:
        """
        Calculate cumulative fatigue over a period.
        
        Uses simplified fitness-fatigue model approach.
        
        Args:
            athlete_id: Athlete ID
            days_lookback: Days to analyze
            
        Returns:
            Dict with fatigue metrics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Get recent workouts
        sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .order_by(WorkoutSession.session_date.desc())
            .all()
        )
        
        # Get recent recovery metrics
        recovery_metrics = (
            self.db.query(RecoveryMetrics)
            .filter(
                RecoveryMetrics.athlete_id == athlete_id,
                RecoveryMetrics.date >= cutoff_date
            )
            .order_by(RecoveryMetrics.date.desc())
            .all()
        )
        
        if not sessions:
            return {
                "fatigue_level": "low",
                "fatigue_score": 0.0,
                "recommendation": "Ready to train",
                "needs_deload": False
            }
        
        # Calculate training load (volume * average RPE)
        training_loads = []
        days_ago = []
        
        for session in sessions:
            current_time = datetime.now(timezone.utc)
            session_time = session.session_date
            if session_time.tzinfo is None:
                session_time = session_time.replace(tzinfo=timezone.utc)
            
            days_since = (current_time - session_time).days
            load = 0
            
            if session.total_volume and session.overall_rpe:
                # Normalize load: volume/1000 * RPE
                load = (session.total_volume / 1000) * session.overall_rpe
            elif session.overall_rpe:
                # Use RPE only if volume not available
                load = session.overall_rpe
            
            training_loads.append(load)
            days_ago.append(days_since)
        
        # Calculate average recovery score
        avg_recovery_score = 0.7  # Default
        if recovery_metrics:
            recovery_scores = [rm.readiness_score for rm in recovery_metrics if rm.readiness_score]
            if recovery_scores:
                avg_recovery_score = sum(recovery_scores) / len(recovery_scores)
        
        # Simple fatigue calculation
        # Recent loads have more impact (exponential decay)
        weighted_fatigue = 0.0
        for load, day in zip(training_loads, days_ago):
            # Fatigue decays with ~7 day half-life
            decay_factor = 2 ** (-day / 7)
            weighted_fatigue += load * decay_factor
        
        # Normalize fatigue score (0-1)
        # High training load with low recovery = high fatigue
        fatigue_score = min(weighted_fatigue / 10, 1.0)
        fatigue_score = fatigue_score * (1.5 - avg_recovery_score)  # Amplify if poor recovery
        fatigue_score = min(fatigue_score, 1.0)
        
        # Determine fatigue level
        if fatigue_score < 0.3:
            fatigue_level = "low"
            recommendation = "Ready for high-intensity training"
            needs_deload = False
        elif fatigue_score < 0.6:
            fatigue_level = "moderate"
            recommendation = "Continue training with awareness"
            needs_deload = False
        elif fatigue_score < 0.8:
            fatigue_level = "high"
            recommendation = "Consider reducing volume or intensity"
            needs_deload = False
        else:
            fatigue_level = "very_high"
            recommendation = "Deload week strongly recommended"
            needs_deload = True
        
        return {
            "fatigue_level": fatigue_level,
            "fatigue_score": round(fatigue_score, 3),
            "recommendation": recommendation,
            "needs_deload": needs_deload,
            "average_recovery_score": round(avg_recovery_score, 3),
            "workouts_analyzed": len(sessions)
        }
    
    def get_recovery_recommendations(
        self,
        readiness_score: float,
        fatigue_level: str,
        sleep_quality: SleepQuality
    ) -> List[str]:
        """
        Generate actionable recovery recommendations.
        
        Args:
            readiness_score: Overall readiness (0-1)
            fatigue_level: Fatigue level string
            sleep_quality: Sleep quality
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Readiness-based recommendations
        if readiness_score < 0.5:
            recommendations.append("Consider skipping or significantly reducing today's training")
            recommendations.append("Focus on recovery: sleep, nutrition, stress management")
        elif readiness_score < 0.7:
            recommendations.append("Reduce training volume by 20-30%")
            recommendations.append("Focus on technique and lighter loads")
        
        # Sleep-based recommendations
        if sleep_quality in [SleepQuality.POOR, SleepQuality.NOT_BAD]:
            recommendations.append("Prioritize sleep quality and duration (aim for 7-9 hours)")
            recommendations.append("Consider sleep hygiene improvements: dark room, cool temperature, no screens before bed")
        
        # Fatigue-based recommendations
        if fatigue_level in ["high", "very_high"]:
            recommendations.append("Consider implementing a deload week (50% volume, 90% intensity)")
            recommendations.append("Increase rest days or active recovery sessions")
            recommendations.append("Ensure adequate protein intake (1.6-2.2g/kg bodyweight)")
        
        # General wellness
        if not recommendations:
            recommendations.append("Recovery status is good - maintain current practices")
            recommendations.append("Continue monitoring sleep, nutrition, and stress")
        
        return recommendations

