"""
Plan Analyzer Service.

Orchestrates all plan analysis modules for real-time feedback.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.utils.constants import (
    TrainingType, TrainingExperience, MAX_FOCUS_AREAS,
    SCORE_DEDUCTION_CRITICAL, SCORE_DEDUCTION_HIGH, SCORE_DEDUCTION_MEDIUM, SCORE_DEDUCTION_LOW,
    SCORE_DEDUCTION_HIGH_IMPACT, SCORE_DEDUCTION_MEDIUM_IMPACT, SCORE_DEDUCTION_LOW_IMPACT,
    SCORE_BONUS_EXCELLENT_ORDER, SCORE_BONUS_GOOD_ORDER,
    SCORE_BONUS_OPTIMAL_PUSH_PULL, SCORE_BONUS_OPTIMAL_UPPER_LOWER,
    ORDER_SCORE_EXCELLENT_THRESHOLD, ORDER_SCORE_GOOD_THRESHOLD
)
from app.services.analyzers.volume_distribution import VolumeDistributionAnalyzer
from app.services.analyzers.muscle_balance import MuscleGroupBalanceAnalyzer
from app.services.analyzers.exercise_order import ExerciseOrderAnalyzer
from app.services.analyzers.recovery_window import RecoveryWindowAnalyzer
from app.services.analyzers.prescription_quality import PrescriptionQualityAnalyzer
from app.services.analyzers.duration_estimator import WorkoutDurationEstimator
from app.services.analyzers.auto_suggester import AutoSuggestionService
from app.services.analyzers.ml_recommender import MLRecommendationService
from app.services.analyzers.history_analyzer import AthleteHistoryAnalyzer
from app.services.analyzers.periodization_validator import PeriodizationValidator


class PlanAnalyzerService:
    """
    Main orchestrator for plan analysis.
    
    Coordinates all analyzer modules and aggregates results.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.volume_analyzer = VolumeDistributionAnalyzer(db)
        self.balance_analyzer = MuscleGroupBalanceAnalyzer(db)
        self.order_analyzer = ExerciseOrderAnalyzer(db)
        self.recovery_analyzer = RecoveryWindowAnalyzer(db)
        self.prescription_analyzer = PrescriptionQualityAnalyzer(db)
        self.duration_estimator = WorkoutDurationEstimator()
        self.auto_suggester = AutoSuggestionService(db)
        self.ml_recommender = MLRecommendationService(db)
        self.history_analyzer = AthleteHistoryAnalyzer(db)
        self.periodization_validator = PeriodizationValidator()
    
    def analyze_plan_draft(
        self,
        plan_data: Dict,
        athlete_id: Optional[int] = None
    ) -> Dict:
        """
        Analyze a plan draft and return comprehensive feedback.
        
        Args:
            plan_data: Plan data dict with:
                - training_type: TrainingType
                - periodization_model: PeriodizationModel
                - duration_weeks: int
                - frequency: int
                - focus_areas: List[str] (optional)
                - current_phase: str (optional, default "accumulation")
                - week_in_phase: int (optional, default 1)
                - workout_days: List[Dict] with exercises
            athlete_id: Optional athlete ID for personalized analysis
            
        Returns:
            Dict with comprehensive analysis results
        """
        # Extract plan parameters with enum conversion and fallbacks
        training_type = plan_data.get("training_type")
        if isinstance(training_type, str):
            try:
                training_type = TrainingType(training_type.lower())
            except (ValueError, AttributeError):
                training_type = TrainingType.HYBRID  # Default fallback
        elif training_type is None:
            training_type = TrainingType.HYBRID  # Default fallback
        
        experience = plan_data.get("experience")
        if experience and isinstance(experience, str):
            try:
                experience = TrainingExperience(experience.lower())
            except (ValueError, AttributeError):
                experience = TrainingExperience.INTERMEDIATE  # Default fallback
        else:
            experience = TrainingExperience.INTERMEDIATE  # Default
        
        periodization_model = plan_data.get("periodization_model")
        duration_weeks = plan_data.get("duration_weeks", 0)
        frequency = plan_data.get("frequency", 0)
        focus_areas = plan_data.get("focus_areas", [])
        
        # Validate focus areas count
        focus_warnings = []
        if len(focus_areas) > MAX_FOCUS_AREAS:
            focus_warnings.append({
                "severity": "medium",
                "category": "focus_areas",
                "message": f"Too many focus areas selected ({len(focus_areas)}). Maximum {MAX_FOCUS_AREAS} recommended for optimal results.",
                "affected_items": focus_areas,
                "recommendation": f"Select {MAX_FOCUS_AREAS} or fewer focus areas to ensure adequate volume distribution"
            })
        
        # Normalize phase string (lowercase, handle variations)
        current_phase = plan_data.get("current_phase", "accumulation")
        if isinstance(current_phase, str):
            current_phase = current_phase.lower()
            # Handle common variations
            phase_map = {
                "accumulation": "accumulation",
                "intensification": "intensification",
                "realization": "realization",
                "deload": "deload",
                "peaking": "realization",  # Alias
                "volume": "accumulation",  # Alias
                "strength": "intensification",  # Alias
            }
            current_phase = phase_map.get(current_phase, "accumulation")
        else:
            current_phase = "accumulation"  # Default
        
        week_in_phase = plan_data.get("week_in_phase", 1)
        if not isinstance(week_in_phase, int) or week_in_phase < 1:
            week_in_phase = 1  # Default to week 1
        workout_days = plan_data.get("workout_days", [])
        
        # Collect all exercises for analysis
        all_exercises = []
        for workout_day in workout_days:
            exercises = workout_day.get("exercises", [])
            all_exercises.extend(exercises)
        
        # Run all analyzers
        volume_analysis = self.volume_analyzer.analyze(
            workout_days=workout_days,
            experience=experience,
            focus_areas=focus_areas
        )
        
        balance_analysis = self.balance_analyzer.analyze(
            workout_days=workout_days,
            focus_areas=focus_areas
        )
        
        order_analysis = self.order_analyzer.analyze(
            workout_days=workout_days,
            training_type=training_type,
            focus_areas=focus_areas
        )
        
        recovery_analysis = self.recovery_analyzer.analyze(
            workout_days=workout_days,
            frequency=frequency,
            focus_areas=focus_areas
        )
        
        prescription_analysis = self.prescription_analyzer.analyze(
            exercises=all_exercises,
            training_type=training_type,
            phase=current_phase,
            week_in_phase=week_in_phase,
            focus_areas=focus_areas
        )
        
        # Duration analysis per workout day
        duration_analyses = []
        for workout_day in workout_days:
            exercises = workout_day.get("exercises", [])
            duration_analyses.append(self.duration_estimator.estimate(exercises))
        
        # Auto-suggestions for missing prescriptions
        auto_suggestions = self.auto_suggester.suggest_missing(
            exercises=all_exercises,
            training_type=training_type,
            phase=current_phase,
            week_in_phase=week_in_phase
        )
        
        # ML recommendations (if athlete has history)
        ml_recommendations = None
        if athlete_id:
            ml_recommendations = self.ml_recommender.recommend(
                athlete_id=athlete_id,
                plan_data=plan_data
            )
        
        # Personalized history analysis
        personalized_analysis = None
        if athlete_id:
            personalized_analysis = self.history_analyzer.analyze(
                athlete_id=athlete_id,
                plan_data=plan_data
            )
        
        # Periodization validation
        periodization_validation = self.periodization_validator.validate(plan_data)
        
        # Aggregate all warnings and suggestions
        all_warnings = []
        all_suggestions = []
        all_strengths = []
        
        # Add focus area validation warnings
        all_warnings.extend(focus_warnings)
        
        all_warnings.extend(volume_analysis.get("warnings", []))
        all_warnings.extend(balance_analysis.get("warnings", []))
        all_warnings.extend(order_analysis.get("violations", []))
        all_warnings.extend(recovery_analysis.get("warnings", []))
        all_warnings.extend(prescription_analysis.get("warnings", []))
        all_warnings.extend(periodization_validation.get("warnings", []))
        
        # Add duration warnings
        for duration_analysis in duration_analyses:
            all_warnings.extend(duration_analysis.get("warnings", []))
        
        all_suggestions.extend(volume_analysis.get("suggestions", []))
        all_suggestions.extend(balance_analysis.get("suggestions", []))
        all_suggestions.extend(order_analysis.get("suggestions", []))
        all_suggestions.extend(prescription_analysis.get("suggestions", []))
        all_suggestions.extend(periodization_validation.get("suggestions", []))
        
        # Add duration suggestions
        for duration_analysis in duration_analyses:
            all_suggestions.extend(duration_analysis.get("suggestions", []))
        
        all_strengths.extend(balance_analysis.get("strengths", []))
        
        # Calculate overall score (0-100)
        overall_score = self._calculate_overall_score(
            warnings=all_warnings,
            suggestions=all_suggestions,
            volume_analysis=volume_analysis,
            order_analysis=order_analysis,
            balance_analysis=balance_analysis
        )
        
        # Calculate total weekly volume estimate
        total_weekly_volume = volume_analysis.get("total_weekly_sets", 0)
        
        # Calculate average workout duration
        avg_duration = sum(d.get("estimated_minutes", 0) for d in duration_analyses) / len(duration_analyses) if duration_analyses else 0
        
        # Calculate focus compliance summary
        focus_compliance = self._calculate_focus_compliance(
            volume_analysis,
            focus_areas
        )
        
        return {
            "overall_score": round(overall_score, 1),
            "warnings": all_warnings,
            "suggestions": all_suggestions,
            "strengths": all_strengths,
            "analysis": {
                "volume_distribution": volume_analysis,
                "muscle_group_balance": balance_analysis,
                "exercise_order": order_analysis,
                "recovery_windows": recovery_analysis,
                "prescription_quality": prescription_analysis,
                "workout_duration": {
                    "average_minutes": round(avg_duration, 1),
                    "workouts": duration_analyses,
                },
            },
            "auto_suggestions": auto_suggestions,
            "ml_recommendations": ml_recommendations,
            "personalized_notes": personalized_analysis.get("personalized_notes", []) if personalized_analysis else [],
            "periodization_validation": periodization_validation,
            "focus_compliance": focus_compliance,
            "total_workouts": len(workout_days),
            "total_exercises": len(all_exercises),
            "estimated_weekly_volume": round(total_weekly_volume, 1),
            "estimated_workout_duration_minutes": round(avg_duration, 1),
        }
    
    def _calculate_focus_compliance(
        self,
        volume_analysis: Dict,
        focus_areas: List[str]
    ) -> Dict:
        """
        Calculate focus area compliance summary.
        
        Args:
            volume_analysis: Volume distribution analysis results
            focus_areas: List of focus areas
            
        Returns:
            Dict with focus compliance summary
        """
        if not focus_areas:
            return {
                "focus_areas": [],
                "compliance_score": None,
                "summary": "No focus areas selected"
            }
        
        from app.utils.constants import FocusArea
        
        # Map focus areas to muscle names
        focus_to_muscles = {
            FocusArea.CHEST: ["upper_chest", "mid_chest", "lower_chest"],
            FocusArea.BACK: ["lats", "upper_traps", "mid_back", "lower_traps"],
            FocusArea.SHOULDERS: ["anterior_delt", "lateral_delt", "posterior_delt"],
            FocusArea.ARMS: ["biceps", "triceps", "forearms"],
            FocusArea.LEGS: ["quadriceps", "hamstrings", "glutes", "hip_flexors", "calves"],
            FocusArea.CORE: ["abs", "erector_spinae"],
        }
        
        # Expand focus areas to muscle groups
        focus_muscle_groups = set()
        for focus_area_str in focus_areas:
            try:
                focus_area = FocusArea(focus_area_str.lower())
                muscles = focus_to_muscles.get(focus_area, [])
                focus_muscle_groups.update(muscles)
            except (ValueError, KeyError):
                continue
        
        # Check volume status for focus muscles
        muscle_volume = volume_analysis.get("muscle_volume", {})
        focus_statuses = []
        optimal_count = 0
        total_focus = 0
        
        for muscle_group in focus_muscle_groups:
            muscle_name = muscle_group  # focus_muscle_groups contains strings, not enum objects
            muscle_data = muscle_volume.get(muscle_name, {})
            status = muscle_data.get("status", "not_trained")
            focus_state = muscle_data.get("focus_state", "maintenance")
            weekly_sets = muscle_data.get("weekly_sets", 0)
            
            if focus_state == "focus":
                total_focus += 1
                if status == "optimal":
                    optimal_count += 1
                
                focus_statuses.append({
                    "muscle_group": muscle_name,
                    "weekly_sets": weekly_sets,
                    "status": status,
                    "target_range": f"{muscle_data.get('mav', 0)}-{muscle_data.get('mrv', 0)} sets"
                })
        
        compliance_score = (optimal_count / total_focus * 100) if total_focus > 0 else None
        
        return {
            "focus_areas": focus_areas,
            "focus_muscle_groups": list(focus_muscle_groups),  # focus_muscle_groups contains strings, not enum objects
            "compliance_score": round(compliance_score, 1) if compliance_score is not None else None,
            "optimal_count": optimal_count,
            "total_focus_muscles": total_focus,
            "muscle_statuses": focus_statuses,
            "summary": f"{optimal_count}/{total_focus} focus muscles in optimal volume range" if total_focus > 0 else "No focus muscles found"
        }
    
    def _calculate_overall_score(
        self,
        warnings: List[Dict],
        suggestions: List[Dict],
        volume_analysis: Dict,
        order_analysis: Dict,
        balance_analysis: Dict
    ) -> float:
        """
        Calculate overall plan quality score (0-100).
        
        Args:
            warnings: List of warnings
            suggestions: List of suggestions
            volume_analysis: Volume distribution analysis
            order_analysis: Exercise order analysis
            balance_analysis: Muscle balance analysis
            
        Returns:
            Score from 0-100
        """
        base_score = 100.0
        
        # Deduct for warnings (severity-based)
        for warning in warnings:
            severity = warning.get("severity", "medium")
            if severity == "critical":
                base_score -= SCORE_DEDUCTION_CRITICAL
            elif severity == "high":
                base_score -= SCORE_DEDUCTION_HIGH
            elif severity == "medium":
                base_score -= SCORE_DEDUCTION_MEDIUM
            else:
                base_score -= SCORE_DEDUCTION_LOW
        
        # Deduct for suggestions (impact-based)
        for suggestion in suggestions:
            impact = suggestion.get("impact", "low")
            if impact == "high":
                base_score -= SCORE_DEDUCTION_HIGH_IMPACT
            elif impact == "medium":
                base_score -= SCORE_DEDUCTION_MEDIUM_IMPACT
            else:
                base_score -= SCORE_DEDUCTION_LOW_IMPACT
        
        # Bonus for good order
        order_score = order_analysis.get("average_score", 100)
        if order_score >= ORDER_SCORE_EXCELLENT_THRESHOLD:
            base_score += SCORE_BONUS_EXCELLENT_ORDER
        elif order_score >= ORDER_SCORE_GOOD_THRESHOLD:
            base_score += SCORE_BONUS_GOOD_ORDER
        
        # Bonus for good balance
        if balance_analysis.get("push_pull", {}).get("status") == "optimal":
            base_score += SCORE_BONUS_OPTIMAL_PUSH_PULL
        if balance_analysis.get("upper_lower", {}).get("status") == "optimal":
            base_score += SCORE_BONUS_OPTIMAL_UPPER_LOWER
        
        # Check volume status
        muscle_volume = volume_analysis.get("muscle_volume", {})
        optimal_count = sum(1 for m in muscle_volume.values() if m.get("status") == "optimal")
        total_muscles = len(muscle_volume)
        if total_muscles > 0:
            optimal_ratio = optimal_count / total_muscles
            if optimal_ratio >= 0.8:
                base_score += 5
            elif optimal_ratio >= 0.6:
                base_score += 2
        
        return max(0.0, min(100.0, base_score))

