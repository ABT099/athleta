"""
Injury prevention and risk assessment service.

Monitors training load, volume spikes, intensity limits, and joint stress.
Based on ACWR and evidence-based guidelines.
"""
from typing import Dict, List, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import WorkoutSession, ExerciseSet, Exercise, Athlete
from app.services.training_calculations import TrainingCalculations
from app.services.form_quality_service import FormQualityService
from app.utils.constants import TrainingExperience, PROGRESSION_RATES


class InjuryPreventionService:
    """
    Monitors training for injury risk factors.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.calc = TrainingCalculations()
        self.form_service = FormQualityService(db)
    
    def check_all_injury_risks(
        self,
        athlete_id: int,
        proposed_workout_volume: float,
        proposed_exercises: List[int]
    ) -> Dict:
        """
        Comprehensive injury risk check.
        
        Args:
            athlete_id: Athlete ID
            proposed_workout_volume: Proposed volume for next workout
            proposed_exercises: List of exercise IDs
            
        Returns:
            Dict with warnings and risk assessment
        """
        warnings = []
        risk_level = "low"
        
        # Check 1: Volume spike
        volume_check = self.check_volume_spike(athlete_id, proposed_workout_volume)
        if volume_check["is_spike"]:
            warnings.append(volume_check["warning"])
            risk_level = "moderate" if risk_level == "low" else "high"
        
        # Check 2: ACWR (Acute:Chronic Workload Ratio)
        acwr_check = self.check_acwr(athlete_id)
        if acwr_check["risk_level"] != "low":
            warnings.append(acwr_check["warning"])
            if acwr_check["risk_level"] == "high":
                risk_level = "high"
        
        # Check 3: Training monotony
        monotony_check = self.check_training_monotony(athlete_id)
        if monotony_check["is_high"]:
            warnings.append(monotony_check["warning"])
            risk_level = "moderate" if risk_level == "low" else risk_level
        
        # Check 4: Joint stress accumulation
        joint_check = self.check_joint_stress(athlete_id, proposed_exercises)
        if joint_check["warnings"]:
            warnings.extend(joint_check["warnings"])
            risk_level = "high" if joint_check["high_risk"] else risk_level
        
        # Check 5: Form degradation
        form_check = self.check_form_degradation(athlete_id)
        if form_check["warnings"]:
            warnings.extend(form_check["warnings"])
            risk_level = "moderate" if risk_level == "low" else risk_level
        
        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "volume_status": volume_check,
            "acwr_status": acwr_check,
            "monotony_status": monotony_check,
            "joint_stress_status": joint_check,
            "form_status": form_check,
            "recommendations": self._generate_injury_prevention_recommendations(
                risk_level, warnings
            )
        }
    
    def check_volume_spike(
        self,
        athlete_id: int,
        proposed_volume: float,
        weeks_to_compare: int = 4
    ) -> Dict:
        """
        Check for dangerous volume spikes.
        
        The 10% rule: weekly volume shouldn't increase by more than 10%.
        Beginners can handle slightly more (15%).
        
        Args:
            athlete_id: Athlete ID
            proposed_volume: Proposed volume for upcoming week
            weeks_to_compare: Number of weeks to average
            
        Returns:
            Dict with spike status and details
        """
        # Get athlete's training experience
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"is_spike": False, "warning": None}
        
        # Get max weekly volume increase for experience level
        progression_data = PROGRESSION_RATES.get(athlete.training_experience)
        max_increase = progression_data["max_weekly_volume_increase"]
        
        # Get recent weekly volumes
        cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=weeks_to_compare)
        
        recent_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .all()
        )
        
        if not recent_sessions:
            return {"is_spike": False, "warning": None, "average_volume": 0}
        
        # Calculate average weekly volume
        total_volume = sum(s.total_volume or 0 for s in recent_sessions)
        weeks_elapsed = min(weeks_to_compare, 
                          (datetime.now(timezone.utc) - recent_sessions[-1].session_date).days / 7)
        avg_weekly_volume = total_volume / max(weeks_elapsed, 1)
        
        if avg_weekly_volume == 0:
            return {"is_spike": False, "warning": None, "average_volume": 0}
        
        # Calculate percentage increase
        volume_increase = (proposed_volume - avg_weekly_volume) / avg_weekly_volume
        
        is_spike = volume_increase > max_increase
        
        warning = None
        if is_spike:
            warning = (
                f"Volume spike detected: {volume_increase*100:.1f}% increase. "
                f"Recommended max: {max_increase*100:.0f}%. "
                f"Consider reducing volume to {avg_weekly_volume * (1 + max_increase):.0f}kg."
            )
        
        return {
            "is_spike": is_spike,
            "volume_increase_percent": round(volume_increase * 100, 1),
            "max_recommended_percent": max_increase * 100,
            "average_volume": round(avg_weekly_volume, 1),
            "proposed_volume": proposed_volume,
            "warning": warning
        }
    
    def check_acwr(self, athlete_id: int) -> Dict:
        """
        Check Acute:Chronic Workload Ratio.
        
        ACWR = Acute Load (7 days) / Chronic Load (28 days)
        Safe zone: 0.8 - 1.3
        Elevated risk: < 0.8 or > 1.5
        
        Reference: Gabbett, T.J. (2016)
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with ACWR status
        """
        # Get loads for last 7 days (acute)
        acute_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        acute_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= acute_cutoff
            )
            .all()
        )
        
        # Get loads for last 28 days (chronic)
        chronic_cutoff = datetime.now(timezone.utc) - timedelta(days=28)
        chronic_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= chronic_cutoff
            )
            .all()
        )
        
        if not chronic_sessions:
            return {
                "acwr": 0.0,
                "risk_level": "low",
                "warning": None
            }
        
        # Calculate daily training loads (using volume * RPE as proxy)
        acute_loads = []
        for session in acute_sessions:
            load = 0
            if session.total_volume and session.overall_rpe:
                load = (session.total_volume / 1000) * session.overall_rpe
            acute_loads.append(load)
        
        chronic_loads = []
        for session in chronic_sessions:
            load = 0
            if session.total_volume and session.overall_rpe:
                load = (session.total_volume / 1000) * session.overall_rpe
            chronic_loads.append(load)
        
        # Calculate ACWR
        acwr = self.calc.calculate_acute_chronic_workload_ratio(
            acute_loads, chronic_loads
        )
        
        # Assess risk
        if 0.8 <= acwr <= 1.3:
            risk_level = "low"
            warning = None
        elif 1.3 < acwr <= 1.5:
            risk_level = "moderate"
            warning = f"ACWR slightly elevated at {acwr:.2f}. Monitor for overtraining signs."
        elif acwr > 1.5:
            risk_level = "high"
            warning = (
                f"ACWR dangerously high at {acwr:.2f}. "
                f"Significant injury risk - reduce training volume immediately."
            )
        elif 0.5 <= acwr < 0.8:
            risk_level = "moderate"
            warning = f"ACWR low at {acwr:.2f}. Undertraining may lead to deconditioning."
        else:
            risk_level = "low"
            warning = None
        
        return {
            "acwr": round(acwr, 2),
            "risk_level": risk_level,
            "warning": warning,
            "acute_load": round(sum(acute_loads), 1),
            "chronic_load": round(sum(chronic_loads), 1)
        }
    
    def check_training_monotony(self, athlete_id: int, days: int = 14) -> Dict:
        """
        Check training monotony index.
        
        High monotony (>2.0) combined with high volume increases injury risk.
        
        Args:
            athlete_id: Athlete ID
            days: Days to analyze
            
        Returns:
            Dict with monotony status
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .order_by(WorkoutSession.session_date)
            .all()
        )
        
        if len(sessions) < 3:
            return {"is_high": False, "monotony": 0.0, "warning": None}
        
        # Calculate daily loads
        daily_loads = []
        for session in sessions:
            load = 0
            if session.total_volume and session.overall_rpe:
                load = (session.total_volume / 1000) * session.overall_rpe
            elif session.overall_rpe:
                load = session.overall_rpe
            daily_loads.append(load)
        
        monotony = self.calc.calculate_training_monotony(daily_loads)
        
        is_high = monotony > 2.0
        warning = None
        if is_high:
            warning = (
                f"Training monotony high ({monotony:.2f}). "
                f"Add variety to training: different exercises, rep ranges, or intensities."
            )
        
        return {
            "is_high": is_high,
            "monotony": round(monotony, 2),
            "warning": warning,
            "recommendation": "Incorporate more variation in training" if is_high else None
        }
    
    def check_joint_stress(
        self,
        athlete_id: int,
        proposed_exercise_ids: List[int],
        days_lookback: int = 7
    ) -> Dict:
        """
        Check for joint stress accumulation.
        
        Monitors frequency of high-stress exercises (overhead, maximal loads).
        
        Args:
            athlete_id: Athlete ID
            proposed_exercise_ids: Exercises planned for next workout
            days_lookback: Days to analyze
            
        Returns:
            Dict with joint stress warnings
        """
        warnings = []
        high_risk = False
        
        # Get proposed exercises
        proposed_exercises = (
            self.db.query(Exercise)
            .filter(Exercise.id.in_(proposed_exercise_ids))
            .all()
        )
        
        # Check for high-risk exercises
        high_risk_exercises = [
            ex for ex in proposed_exercises 
            if ex.injury_risk_level >= 2.5
        ]
        
        if len(high_risk_exercises) > 3:
            warnings.append(
                f"Workout contains {len(high_risk_exercises)} high-risk exercises. "
                f"Consider substituting some with lower-risk alternatives."
            )
            high_risk = True
        
        # Check for joint stress concentration
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        recent_sets = (
            self.db.query(ExerciseSet, Exercise)
            .join(WorkoutSession)
            .join(Exercise)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= cutoff_date
            )
            .all()
        )
        
        # Count exercises by joint stress area
        joint_stress_count = {}
        for ex_set, exercise in recent_sets:
            if exercise.joint_stress_areas:
                for joint in exercise.joint_stress_areas:
                    joint_stress_count[joint] = joint_stress_count.get(joint, 0) + 1
        
        # Check proposed exercises' joints
        for exercise in proposed_exercises:
            if exercise.joint_stress_areas:
                for joint in exercise.joint_stress_areas:
                    current_count = joint_stress_count.get(joint, 0)
                    
                    # Warning thresholds
                    if current_count > 20:  # Heavy recent loading
                        warnings.append(
                            f"High {joint} stress detected ({current_count} sets this week). "
                            f"Exercise '{exercise.name}' may increase injury risk."
                        )
                        high_risk = True
        
        return {
            "warnings": warnings,
            "high_risk": high_risk,
            "high_risk_exercise_count": len(high_risk_exercises),
            "joint_stress_distribution": joint_stress_count
        }
    
    def check_form_degradation(self, athlete_id: int, sessions_to_check: int = 3) -> Dict:
        """
        Check for form degradation patterns with enhanced analysis.
        
        Now includes:
        - Per-exercise form tracking (not just aggregate)
        - Within-session form degradation (set 1 vs final sets)
        - Chronic poor form detection across multiple sessions
        - Integration with joint stress monitoring
        
        Args:
            athlete_id: Athlete ID
            sessions_to_check: Number of recent sessions to analyze
            
        Returns:
            Dict with form degradation warnings and detailed analysis
        """
        warnings = []
        exercise_analysis = {}
        
        # Get recent sessions
        recent_sessions = (
            self.db.query(WorkoutSession)
            .filter(WorkoutSession.athlete_id == athlete_id)
            .order_by(WorkoutSession.session_date.desc())
            .limit(sessions_to_check)
            .all()
        )
        
        if not recent_sessions:
            return {
                "warnings": [],
                "poor_form_percentage": 0.0,
                "exercise_analysis": {},
                "chronic_issues": {}
            }
        
        # Analyze form quality per exercise
        total_sets = 0
        poor_form_sets = 0
        high_rpe_poor_form_sets = 0
        
        for session in recent_sessions:
            # Get form quality metrics for this session
            session_metrics = self.form_service.track_session_form_quality(session.id)
            
            for exercise_id, metrics in session_metrics.items():
                if exercise_id not in exercise_analysis:
                    exercise_analysis[exercise_id] = {
                        "total_sets": 0,
                        "poor_form_sets": 0,
                        "high_rpe_poor_form_sets": 0,
                        "degradation_events": 0,
                        "average_score": []
                    }
                
                ex_analysis = exercise_analysis[exercise_id]
                ex_analysis["total_sets"] += metrics["sets_analyzed"]
                ex_analysis["average_score"].append(metrics["average_form_score"])
                
                # Count poor form sets (score < 0.6 = below "good")
                poor_count = sum(
                    1 for _ in range(metrics["sets_analyzed"])
                    if metrics["average_form_score"] < 0.6
                )
                ex_analysis["poor_form_sets"] += poor_count
                
                ex_analysis["high_rpe_poor_form_sets"] += metrics["high_rpe_poor_form_count"]
                
                # Track degradation events
                from app.utils.constants import FORM_DEGRADATION_THRESHOLD
                if metrics["degradation_rate"] and metrics["degradation_rate"] >= FORM_DEGRADATION_THRESHOLD:
                    ex_analysis["degradation_events"] += 1
                
                total_sets += metrics["sets_analyzed"]
                poor_form_sets += poor_count
                high_rpe_poor_form_sets += metrics["high_rpe_poor_form_count"]
        
        if total_sets == 0:
            return {
                "warnings": [],
                "poor_form_percentage": 0.0,
                "exercise_analysis": {},
                "chronic_issues": {}
            }
        
        poor_form_percentage = (poor_form_sets / total_sets) * 100
        
        # Generate aggregate warnings
        if poor_form_percentage > 30:
            warnings.append(
                f"Form quality concerning: {poor_form_percentage:.1f}% of sets rated fair/poor. "
                f"Reduce loads and focus on technique."
            )
        
        if high_rpe_poor_form_sets > 0:
            warnings.append(
                f"{high_rpe_poor_form_sets} sets with poor form at RPE 9+. "
                f"This combination significantly increases injury risk. "
                f"Reduce intensity immediately."
            )
        
        # Generate per-exercise warnings
        for exercise_id, ex_analysis in exercise_analysis.items():
            if ex_analysis["total_sets"] == 0:
                continue
            
            exercise = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
            exercise_name = exercise.name if exercise else f"Exercise {exercise_id}"
            
            ex_poor_percentage = (ex_analysis["poor_form_sets"] / ex_analysis["total_sets"]) * 100
            avg_score = sum(ex_analysis["average_score"]) / len(ex_analysis["average_score"])
            
            # Exercise-specific warnings
            if ex_poor_percentage > 40:
                warnings.append(
                    f"{exercise_name}: {ex_poor_percentage:.1f}% of sets with poor form. "
                    f"Consider reducing loads or deloading."
                )
            
            if ex_analysis["degradation_events"] > 0:
                warnings.append(
                    f"{exercise_name}: Form degrading within sessions detected. "
                    f"Reduce volume or increase rest periods."
                )
            
            # Check joint stress + poor form combination
            if exercise:
                joint_stress_areas = exercise.joint_stress_areas or []
                if joint_stress_areas and avg_score < 0.6:
                    warnings.append(
                        f"{exercise_name}: Poor form on high joint-stress exercise. "
                        f"Injury risk elevated. Reduce intensity immediately."
                    )
        
        # Check for chronic issues
        chronic_issues = self.form_service.detect_chronic_form_issues(athlete_id, days_lookback=14)
        
        return {
            "warnings": warnings,
            "poor_form_percentage": round(poor_form_percentage, 1),
            "high_risk_sets": high_rpe_poor_form_sets,
            "total_sets_analyzed": total_sets,
            "exercise_analysis": {
                ex_id: {
                    "exercise_name": self.db.query(Exercise).filter(Exercise.id == ex_id).first().name if self.db.query(Exercise).filter(Exercise.id == ex_id).first() else f"Exercise {ex_id}",
                    "poor_form_percentage": round((ex_data["poor_form_sets"] / ex_data["total_sets"] * 100) if ex_data["total_sets"] > 0 else 0, 1),
                    "average_score": round(sum(ex_data["average_score"]) / len(ex_data["average_score"]), 3) if ex_data["average_score"] else None,
                    "degradation_events": ex_data["degradation_events"]
                }
                for ex_id, ex_data in exercise_analysis.items()
            },
            "chronic_issues": chronic_issues
        }
    
    def analyze_form_degradation_patterns(
        self,
        athlete_id: int,
        days_lookback: int = 14
    ) -> Dict:
        """
        Analyze form degradation patterns to identify exercises with consistent form breakdown.
        
        Correlates form quality with fatigue accumulation and generates
        exercise-specific technique warnings.
        
        Args:
            athlete_id: Athlete ID
            days_lookback: Number of days to analyze
            
        Returns:
            Dict with pattern analysis and recommendations
        """
        # Get form quality alerts
        alerts = self.form_service.generate_form_alerts(athlete_id, days_lookback=days_lookback)
        
        # Get chronic issues
        chronic_issues = self.form_service.detect_chronic_form_issues(athlete_id, days_lookback=days_lookback)
        
        # Identify exercises with consistent form breakdown
        problem_exercises = []
        
        for issue in chronic_issues.get("issues", []):
            exercise = self.db.query(Exercise).filter(Exercise.id == issue["exercise_id"]).first()
            if not exercise:
                continue
            
            # Get trend for this exercise
            trend = self.form_service.get_form_quality_trend(
                athlete_id, issue["exercise_id"], days_lookback
            )
            
            problem_exercises.append({
                "exercise_id": issue["exercise_id"],
                "exercise_name": issue["exercise_name"],
                "poor_form_percentage": issue["poor_form_percentage"],
                "trend_direction": trend.get("trend_direction"),
                "joint_stress_areas": exercise.joint_stress_areas or [],
                "recommendation": self._generate_exercise_specific_recommendation(
                    exercise, issue, trend
                )
            })
        
        return {
            "problem_exercises": problem_exercises,
            "alerts": alerts,
            "recommendations": self._generate_pattern_based_recommendations(problem_exercises)
        }
    
    def _generate_exercise_specific_recommendation(
        self,
        exercise: Exercise,
        issue: Dict,
        trend: Dict
    ) -> str:
        """Generate exercise-specific recommendation based on form issues."""
        recommendations = []
        
        if issue["poor_form_percentage"] > 50:
            recommendations.append("Consider deloading this exercise")
        
        if trend.get("trend_direction") == "degrading":
            recommendations.append("Form is getting worse - reduce volume or intensity")
        
        joint_stress = exercise.joint_stress_areas or []
        if joint_stress and issue["poor_form_percentage"] > 30:
            recommendations.append(
                f"High joint stress areas ({', '.join(joint_stress)}) at risk - "
                f"reduce loads immediately"
            )
        
        if not recommendations:
            recommendations.append("Focus on technique and consider reducing loads")
        
        return ". ".join(recommendations) + "."
    
    def _generate_pattern_based_recommendations(self, problem_exercises: List[Dict]) -> List[str]:
        """Generate overall recommendations based on patterns."""
        recommendations = []
        
        if len(problem_exercises) > 3:
            recommendations.append(
                "Multiple exercises showing form issues. Consider overall deload week."
            )
        
        high_joint_stress_count = sum(
            1 for ex in problem_exercises
            if ex.get("joint_stress_areas")
        )
        
        if high_joint_stress_count > 2:
            recommendations.append(
                "Multiple high joint-stress exercises with form issues. "
                "Injury risk elevated - reduce training intensity."
            )
        
        return recommendations
    
    def check_intensity_progression(
        self,
        athlete_id: int,
        exercise_id: int,
        proposed_weight: float,
        current_estimated_1rm: float
    ) -> Dict:
        """
        Check if intensity progression is too aggressive.
        
        Max progression: 5% for compound lifts, 10% for accessories.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            proposed_weight: Proposed weight for next session
            current_estimated_1rm: Current estimated 1RM
            
        Returns:
            Dict with intensity check results
        """
        # Get last weight used for this exercise
        last_set = (
            self.db.query(ExerciseSet)
            .join(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                ExerciseSet.exercise_id == exercise_id
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        
        if not last_set:
            return {"is_safe": True, "warning": None}
        
        # Get exercise info
        exercise = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
        
        # Calculate increase
        weight_increase = (proposed_weight - last_set.weight) / last_set.weight
        
        # Set max progression based on exercise type
        max_progression = 0.05 if exercise and exercise.exercise_type == 'compound' else 0.10
        
        is_safe = weight_increase <= max_progression
        
        warning = None
        if not is_safe:
            recommended_weight = last_set.weight * (1 + max_progression)
            warning = (
                f"Weight increase too aggressive for {exercise.name if exercise else 'exercise'}: "
                f"{weight_increase*100:.1f}%. Max recommended: {max_progression*100:.0f}%. "
                f"Suggested weight: {recommended_weight:.1f}kg"
            )
        
        return {
            "is_safe": is_safe,
            "weight_increase_percent": round(weight_increase * 100, 1),
            "max_recommended_percent": max_progression * 100,
            "warning": warning,
            "recommended_weight": round(last_set.weight * (1 + max_progression), 1)
        }
    
    def _generate_injury_prevention_recommendations(
        self,
        risk_level: str,
        warnings: List[str]
    ) -> List[str]:
        """
        Generate actionable injury prevention recommendations.
        
        Args:
            risk_level: Overall risk level
            warnings: List of warnings
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if risk_level == "high":
            recommendations.append("URGENT: Implement deload week immediately (50% volume, 90% intensity)")
            recommendations.append("Consult with a healthcare professional if experiencing pain")
            recommendations.append("Focus on mobility, recovery, and technique work")
        elif risk_level == "moderate":
            recommendations.append("Reduce training volume by 20-30% for next 1-2 weeks")
            recommendations.append("Increase attention to warm-up and mobility work")
            recommendations.append("Monitor for any pain or discomfort closely")
        else:
            recommendations.append("Continue current training approach")
            recommendations.append("Maintain proper warm-up and recovery practices")
        
        # Add specific recommendations based on warnings
        if any("monotony" in w.lower() for w in warnings):
            recommendations.append("Add exercise variation: try different grips, angles, or rep ranges")
        
        if any("form" in w.lower() for w in warnings):
            recommendations.append("Include technique-focused sessions with lighter loads (50-60% 1RM)")
            recommendations.append("Consider working with a coach for form assessment")
        
        return recommendations


