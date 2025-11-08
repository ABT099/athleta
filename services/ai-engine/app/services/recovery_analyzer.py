"""
Recovery assessment and readiness scoring service.

Evaluates athlete readiness based on sleep, soreness, stress, and other wellness markers.
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import RecoveryMetrics, WorkoutSession, Athlete
from app.utils.constants import (
    SleepQuality, SLEEP_QUALITY_MULTIPLIERS, MuscleGroup, 
    Gender, AGE_PROGRESSION_MODIFIERS, GENDER_RECOVERY_MODIFIERS
)


class RecoveryAnalyzer:
    """
    Analyzes recovery status and calculates readiness scores.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def calculate_gender_recovery_modifier(gender: Gender, age: int) -> float:
        """
        Calculate gender-specific recovery modifier.
        
        Women generally recover faster from volume training than men.
        This is adjusted further by age, especially during peak reproductive years.
        
        References:
        - Kraemer et al. (2001): Gender differences in recovery from resistance training
        - Hunter (2014): Sex differences in muscle recovery
        
        Args:
            gender: Athlete gender
            age: Athlete age
            
        Returns:
            Recovery multiplier (1.0 = baseline)
        """
        base_modifier = GENDER_RECOVERY_MODIFIERS[gender]
        
        # Additional boost for women in peak reproductive years
        if gender == Gender.FEMALE and 18 <= age <= 35:
            base_modifier *= 1.05  # Additional 5% boost
        
        # Age-related decline applies to all
        if age > 40:
            base_modifier *= 0.95  # 5% reduction after 40
        
        if age > 50:
            base_modifier *= 0.90  # Additional 10% reduction after 50
        
        return round(base_modifier, 3)
    
    @staticmethod
    def calculate_age_progression_modifier(age: int) -> float:
        """
        Calculate age-based progression rate modifier.
        
        Younger athletes can handle higher training volumes and progress faster.
        Older athletes need more recovery time but can still progress effectively.
        
        References:
        - Schoenfeld et al. (2016): Effects of age on muscle hypertrophy
        - Ahtiainen et al. (2016): Training adaptations across age groups
        
        Args:
            age: Athlete age
            
        Returns:
            Progression multiplier (1.0 = baseline)
        """
        for (min_age, max_age), modifier in AGE_PROGRESSION_MODIFIERS.items():
            if min_age <= age <= max_age:
                return modifier
        
        # Default to baseline if age not in ranges
        return 1.0
    
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
        cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)
        
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
            days_since_workout = (datetime.utcnow() - last_workout.session_date).days
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
            except:
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
        cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)
        
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
            days_since = (datetime.utcnow() - session.session_date).days
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

