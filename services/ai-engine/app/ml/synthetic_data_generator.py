"""
Synthetic data generator for ML model testing and validation.

Generates realistic workout progressions with varied athlete profiles,
progressive overload patterns, fatigue accumulation, and recovery cycles.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import (
    Athlete, WorkoutSession, PerformanceTrend, RecoveryMetrics,
    ExerciseSet, Exercise, WorkoutDay, WorkoutPlan
)
from app.utils.constants import (
    Gender, TrainingExperience, TrainingType, SleepQuality,
    PeriodizationModel, TrainingPhase
)


class SyntheticDataGenerator:
    """
    Generate realistic synthetic workout data for testing ML models.
    """
    
    def __init__(self, db: Session):
        """
        Initialize synthetic data generator.
        
        Args:
            db: Database session
        """
        self.db = db
        self.rng = np.random.RandomState(42)  # Reproducible randomness
    
    def generate_athletes(
        self,
        n_athletes: int = 50,
        age_range: Tuple[int, int] = (18, 50),
        gender_split: float = 0.7  # 70% male
    ) -> List[Athlete]:
        """
        Generate synthetic athletes with varied profiles.
        
        Args:
            n_athletes: Number of athletes to generate
            age_range: (min_age, max_age)
            gender_split: Proportion of male athletes
            
        Returns:
            List of created Athlete objects
        """
        athletes = []
        
        for i in range(n_athletes):
            # Random age
            age = self.rng.randint(age_range[0], age_range[1] + 1)
            
            # Gender
            gender = Gender.MALE if self.rng.random() < gender_split else Gender.FEMALE
            
            # Experience level (weighted toward intermediate)
            exp_weights = [0.2, 0.5, 0.3]  # beginner, intermediate, advanced
            experience = self.rng.choice([
                TrainingExperience.BEGINNER,
                TrainingExperience.INTERMEDIATE,
                TrainingExperience.ADVANCED
            ], p=exp_weights)
            
            # RPE calibration factor (some athletes over/underestimate)
            rpe_calibration = self.rng.normal(1.0, 0.15)
            rpe_calibration = np.clip(rpe_calibration, 0.7, 1.3)
            
            athlete = Athlete(
                id=i + 1,  # Assuming starting from 1
                age=age,
                gender=gender,
                training_experience=experience,
                rpe_calibration_factor=rpe_calibration
            )
            
            athletes.append(athlete)
            self.db.add(athlete)
        
        self.db.flush()
        return athletes
    
    def generate_workout_progression(
        self,
        athlete: Athlete,
        n_sessions: int = 50,
        start_date: Optional[datetime] = None,
        progression_type: str = "normal"  # "normal", "aggressive", "conservative", "plateau"
    ) -> Tuple[List[WorkoutSession], List[PerformanceTrend], List[RecoveryMetrics]]:
        """
        Generate realistic workout progression for an athlete.
        
        Args:
            athlete: Athlete to generate data for
            n_sessions: Number of workout sessions
            start_date: Starting date (defaults to 3 months ago)
            progression_type: Type of progression pattern
            
        Returns:
            Tuple of (sessions, trends, recovery_metrics)
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=90)
        
        sessions = []
        trends = []
        recovery_metrics = []
        
        # Base parameters based on athlete profile
        base_volume = self._get_base_volume(athlete)
        base_intensity = self._get_base_intensity(athlete)
        
        # Progression rates
        progression_rates = {
            "normal": (0.02, 0.01),  # 2% volume, 1% intensity per week
            "aggressive": (0.04, 0.02),
            "conservative": (0.01, 0.005),
            "plateau": (0.0, 0.0)  # No progression
        }
        vol_rate, int_rate = progression_rates.get(progression_type, progression_rates["normal"])
        
        # Current state
        current_volume = base_volume
        current_intensity = base_intensity
        fatigue_accumulation = 0.0
        week_number = 0
        
        # Generate sessions
        for session_num in range(n_sessions):
            session_date = start_date + timedelta(days=session_num * 2)  # Every 2 days
            
            # Deload every 4 weeks
            is_deload = (session_num > 0 and session_num % 14 == 0)
            
            if is_deload:
                current_volume *= 0.6
                current_intensity *= 0.9
                fatigue_accumulation *= 0.3
                week_number += 1
            else:
                # Weekly progression
                if session_num % 3 == 0:  # Every week (3 sessions)
                    current_volume *= (1 + vol_rate)
                    current_intensity *= (1 + int_rate)
                    week_number += 1
            
            # Add noise and variation
            volume_noise = self.rng.normal(1.0, 0.1)
            intensity_noise = self.rng.normal(1.0, 0.05)
            
            session_volume = current_volume * volume_noise
            session_intensity = current_intensity * intensity_noise
            
            # Fatigue affects performance
            fatigue_penalty = 1.0 - (fatigue_accumulation * 0.1)
            session_volume *= max(0.7, fatigue_penalty)
            session_intensity *= max(0.85, fatigue_penalty)
            
            # Generate RPE (affected by actual difficulty and calibration)
            actual_difficulty = session_intensity * (1.0 + fatigue_accumulation * 0.2)
            reported_rpe = self._calculate_rpe(actual_difficulty, athlete.rpe_calibration_factor)
            
            # Generate recovery metrics
            recovery = self._generate_recovery_metrics(
                athlete, session_date, fatigue_accumulation, is_deload
            )
            recovery_metrics.append(recovery)
            
            # Create workout session
            session = WorkoutSession(
                athlete_id=athlete.id,
                workout_day_id=1,  # Placeholder
                session_date=session_date,
                duration_minutes=self.rng.randint(45, 90),
                overall_rpe=reported_rpe,
                overall_feeling=self._get_feeling_from_rpe(reported_rpe),
                total_volume=session_volume,
                estimated_fatigue=fatigue_accumulation
            )
            sessions.append(session)
            self.db.add(session)
            self.db.flush()
            
            # Generate performance trend
            readiness = recovery.readiness_score
            performance_score = self._calculate_performance_score(
                session_volume, session_intensity, readiness, fatigue_accumulation
            )
            
            trend = PerformanceTrend(
                athlete_id=athlete.id,
                workout_session_id=session.id,
                session_date=session_date,
                total_volume=session_volume,
                average_intensity=session_intensity,
                average_rpe=reported_rpe,
                readiness_score=readiness,
                performance_score=performance_score,
                fatigue_index=fatigue_accumulation,
                volume_load=session_volume * session_intensity,
                training_monotony=self.rng.uniform(0.5, 1.5),
                training_strain=session_volume * fatigue_accumulation,
                acute_load=self._calculate_acute_load(sessions[-7:] if len(sessions) >= 7 else sessions),
                chronic_load=self._calculate_chronic_load(sessions[-28:] if len(sessions) >= 28 else sessions),
                acwr=self._calculate_acwr(sessions[-7:] if len(sessions) >= 7 else sessions,
                                         sessions[-28:] if len(sessions) >= 28 else sessions)
            )
            trends.append(trend)
            self.db.add(trend)
            
            # Update fatigue (accumulates, recovers)
            fatigue_accumulation += session_volume * 0.001
            fatigue_accumulation *= 0.85  # Daily recovery
            fatigue_accumulation = max(0.0, min(1.0, fatigue_accumulation))
        
        self.db.flush()
        return sessions, trends, recovery_metrics
    
    def _get_base_volume(self, athlete: Athlete) -> float:
        """Get base volume based on athlete profile."""
        base = 2000.0  # kg
        
        # Age adjustment
        if athlete.age < 25:
            base *= 1.1
        elif athlete.age > 40:
            base *= 0.9
        
        # Experience adjustment
        if athlete.training_experience == TrainingExperience.BEGINNER:
            base *= 0.7
        elif athlete.training_experience == TrainingExperience.ADVANCED:
            base *= 1.3
        
        # Gender adjustment (women typically lift less absolute weight)
        if athlete.gender == Gender.FEMALE:
            base *= 0.7
        
        return base
    
    def _get_base_intensity(self, athlete: Athlete) -> float:
        """Get base intensity based on athlete profile."""
        base = 0.75  # 75% of 1RM
        
        # Experience adjustment
        if athlete.training_experience == TrainingExperience.BEGINNER:
            base = 0.65
        elif athlete.training_experience == TrainingExperience.ADVANCED:
            base = 0.85
        
        return base
    
    def _calculate_rpe(self, actual_difficulty: float, calibration_factor: float) -> float:
        """Calculate reported RPE from actual difficulty."""
        # Actual difficulty 0-1 maps to RPE 6-10
        base_rpe = 6.0 + (actual_difficulty * 4.0)
        
        # Apply calibration (athlete's bias)
        reported_rpe = base_rpe * calibration_factor
        
        # Add noise
        reported_rpe += self.rng.normal(0, 0.3)
        
        return np.clip(reported_rpe, 6.0, 10.0)
    
    def _generate_recovery_metrics(
        self,
        athlete: Athlete,
        date: datetime,
        fatigue: float,
        is_deload: bool
    ) -> RecoveryMetrics:
        """Generate realistic recovery metrics."""
        # Base sleep (7-9 hours)
        sleep_hours = self.rng.uniform(7.0, 9.0)
        if fatigue > 0.7:
            sleep_hours -= 0.5  # Poor sleep when fatigued
        
        # Sleep quality (affected by fatigue)
        if is_deload or fatigue < 0.3:
            sleep_quality = self.rng.choice([
                SleepQuality.GOOD, SleepQuality.EXCELLENT
            ], p=[0.3, 0.7])
        elif fatigue > 0.7:
            sleep_quality = self.rng.choice([
                SleepQuality.POOR, SleepQuality.NOT_BAD
            ], p=[0.6, 0.4])
        else:
            sleep_quality = self.rng.choice(list(SleepQuality), p=[0.1, 0.3, 0.4, 0.2])
        
        # Soreness (1-10, higher with fatigue)
        base_soreness = 3.0
        soreness = base_soreness + (fatigue * 4.0) + self.rng.normal(0, 1.0)
        soreness = int(np.clip(soreness, 1.0, 10.0))
        
        # Stress (1-10)
        stress = self.rng.uniform(2.0, 6.0) + (fatigue * 2.0)
        stress = int(np.clip(stress, 1.0, 10.0))
        
        # Energy (1-10, inverse of fatigue)
        energy = 8.0 - (fatigue * 4.0) + self.rng.normal(0, 1.0)
        energy = int(np.clip(energy, 1.0, 10.0))
        
        # Calculate readiness score (0.0-1.0)
        # Based on sleep, soreness, stress, and energy
        # Sleep component (40% weight)
        sleep_score = self._calculate_sleep_score_simple(sleep_quality, sleep_hours)
        # Soreness component (30% weight) - inverse scale
        soreness_score = (10.0 - soreness) / 10.0
        # Stress component (15% weight) - inverse scale
        stress_score = (10.0 - stress) / 10.0
        # Energy component (15% weight)
        energy_score = energy / 10.0
        
        readiness_score = (
            sleep_score * 0.40 +
            soreness_score * 0.30 +
            stress_score * 0.15 +
            energy_score * 0.15
        )
        readiness_score = float(np.clip(readiness_score, 0.0, 1.0))
        
        recovery = RecoveryMetrics(
            athlete_id=athlete.id,
            date=date,
            sleep_hours=sleep_hours,
            sleep_quality=sleep_quality,
            overall_soreness=soreness,
            stress_level=stress,
            energy_level=energy,
            readiness_score=readiness_score
        )
        
        return recovery
    
    def _calculate_sleep_score_simple(self, sleep_quality: SleepQuality, sleep_hours: float) -> float:
        """Simple sleep score calculation for synthetic data."""
        # Quality multiplier
        quality_multipliers = {
            SleepQuality.POOR: 0.5,
            SleepQuality.NOT_BAD: 0.7,
            SleepQuality.GOOD: 0.85,
            SleepQuality.EXCELLENT: 1.0
        }
        quality_score = quality_multipliers.get(sleep_quality, 0.7)
        
        # Hours score (optimal 7-9 hours)
        if 7.0 <= sleep_hours <= 9.0:
            hours_score = 1.0
        elif sleep_hours < 7.0:
            hours_score = max(0.5, sleep_hours / 7.0)
        else:
            hours_score = max(0.7, 1.0 - (sleep_hours - 9.0) * 0.1)
        
        return (quality_score + hours_score) / 2.0
    
    def _get_feeling_from_rpe(self, rpe: float) -> str:
        """Convert RPE to feeling description."""
        if rpe <= 7.0:
            return "great"
        elif rpe <= 8.0:
            return "good"
        elif rpe <= 9.0:
            return "okay"
        else:
            return "poor"
    
    def _calculate_performance_score(
        self,
        volume: float,
        intensity: float,
        readiness: float,
        fatigue: float
    ) -> float:
        """Calculate performance score (0-1)."""
        # Base score from volume and intensity
        base_score = (volume / 3000.0) * 0.4 + intensity * 0.4
        
        # Adjust for readiness and fatigue
        adjusted = base_score * readiness * (1.0 - fatigue * 0.3)
        
        return np.clip(adjusted, 0.0, 1.0)
    
    def _calculate_acute_load(self, sessions: List[WorkoutSession]) -> float:
        """Calculate acute training load (last 7 days)."""
        if not sessions:
            return 0.0
        return sum(s.total_volume or 0 for s in sessions)
    
    def _calculate_chronic_load(self, sessions: List[WorkoutSession]) -> float:
        """Calculate chronic training load (last 28 days)."""
        if not sessions:
            return 0.0
        return sum(s.total_volume or 0 for s in sessions) / 4.0  # Average per week
    
    def _calculate_acwr(
        self,
        acute_sessions: List[WorkoutSession],
        chronic_sessions: List[WorkoutSession]
    ) -> float:
        """Calculate ACWR (Acute:Chronic Workload Ratio)."""
        acute = self._calculate_acute_load(acute_sessions)
        chronic = self._calculate_chronic_load(chronic_sessions)
        
        if chronic == 0:
            return 1.0
        
        return acute / chronic
    
    def generate_complete_dataset(
        self,
        n_athletes: int = 50,
        sessions_per_athlete: int = 50,
        progression_types: Optional[List[str]] = None
    ) -> Dict:
        """
        Generate complete synthetic dataset.
        
        Args:
            n_athletes: Number of athletes
            sessions_per_athlete: Sessions per athlete
            progression_types: List of progression types to use (cycles through)
            
        Returns:
            Dict with summary statistics
        """
        if progression_types is None:
            progression_types = ["normal", "aggressive", "conservative", "plateau"]
        
        athletes = self.generate_athletes(n_athletes)
        
        all_sessions = []
        all_trends = []
        all_recovery = []
        
        for i, athlete in enumerate(athletes):
            # Cycle through progression types
            prog_type = progression_types[i % len(progression_types)]
            
            sessions, trends, recovery = self.generate_workout_progression(
                athlete,
                n_sessions=sessions_per_athlete,
                progression_type=prog_type
            )
            
            all_sessions.extend(sessions)
            all_trends.extend(trends)
            all_recovery.extend(recovery)
        
        self.db.commit()
        
        return {
            "athletes_created": len(athletes),
            "sessions_created": len(all_sessions),
            "trends_created": len(all_trends),
            "recovery_metrics_created": len(all_recovery),
            "total_volume": sum(s.total_volume or 0 for s in all_sessions),
            "average_sessions_per_athlete": len(all_sessions) / len(athletes)
        }
    
    def generate_athlete_with_sessions(
        self,
        athlete_id: int,
        n_sessions: int = 50,
        progression_type: str = "normal"
    ) -> Dict:
        """
        Generate sessions for existing athlete.
        
        Args:
            athlete_id: Existing athlete ID
            n_sessions: Number of sessions to generate
            progression_type: Type of progression
            
        Returns:
            Dict with generated data summary
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")
        
        sessions, trends, recovery = self.generate_workout_progression(
            athlete,
            n_sessions=n_sessions,
            progression_type=progression_type
        )
        
        self.db.commit()
        
        return {
            "athlete_id": athlete_id,
            "sessions_created": len(sessions),
            "trends_created": len(trends),
            "recovery_metrics_created": len(recovery)
        }

