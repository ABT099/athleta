"""
Progressive Overload AI Engine

The core intelligence that analyzes workouts and calculates optimal progression.
Respects plan context, periodization, recovery, and injury prevention.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from app.models import (
    Athlete, WorkoutPlan, PlanEntry, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, Exercise, RecoveryMetrics, PerformanceTrend
)
from app.services.training_calculations import TrainingCalculations
from app.services.recovery_analyzer import RecoveryAnalyzer
from app.services.injury_prevention import InjuryPreventionService
from app.services.exercise_progression import ExerciseProgressionService
from app.services.periodization import PeriodizationService
from app.services.rpe_calibration import RPECalibrationService
from app.utils.constants import (
    TrainingType, TrainingPhase, TrainingExperience,
    PROGRESSION_RATES, REP_RANGES, INTENSITY_ZONES, DELOAD_THRESHOLDS
)

# Import ML services with graceful degradation
try:
    from app.ml.workout_predictor import WorkoutPredictorService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    WorkoutPredictorService = None


class ProgressiveOverloadEngine:
    """
    AI engine for intelligent training progression.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.calc = TrainingCalculations()
        self.recovery_analyzer = RecoveryAnalyzer(db)
        self.injury_prevention = InjuryPreventionService(db)
        self.exercise_progression = ExerciseProgressionService(db)
        self.periodization = PeriodizationService()
        self.rpe_calibration = RPECalibrationService(db)
        
        # ML services (optional)
        if ML_AVAILABLE:
            self.ml_predictor = WorkoutPredictorService(db)
        else:
            self.ml_predictor = None
    
    def process_workout_completion(
        self,
        athlete_id: int,
        workout_day_id: int,
        session_data: Dict,
        recovery_data: Dict
    ) -> Dict:
        """
        Main entry point: process completed workout and generate next workout adjustments.
        
        Args:
            athlete_id: Athlete ID
            workout_day_id: Workout day that was completed
            session_data: Completed workout data
            recovery_data: Recovery metrics
            
        Returns:
            Dict with analysis, adjustments, and recommendations
        """
        # Get athlete and current plan
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")
        
        # Step 1: Analyze plan context
        plan_context = self.analyze_plan_context(athlete_id)
        
        # Step 2: Analyze workout performance
        performance_analysis = self.analyze_workout_performance(
            athlete, workout_day_id, session_data, plan_context
        )
        
        # Step 3: Assess recovery
        recovery_status = self.assess_recovery_status(
            athlete_id, recovery_data, plan_context
        )
        
        # Step 4: Run injury prevention checks
        proposed_volume = performance_analysis.get("total_volume", 0) * 1.05  # Estimate next volume
        proposed_exercises = [s["exercise_id"] for s in session_data.get("exercise_sets", [])]
        
        injury_risk = self.injury_prevention.check_all_injury_risks(
            athlete_id, proposed_volume, proposed_exercises
        )
        
        # Step 5: Try ML prediction first, fallback to rules
        adjustments, prediction_source = self.calculate_next_workout_parameters_hybrid(
            athlete,
            plan_context,
            performance_analysis,
            recovery_status,
            injury_risk
        )
        
        # Step 6: Generate insights and recommendations
        ai_insights = self._generate_ai_insights(
            performance_analysis,
            recovery_status,
            injury_risk,
            adjustments,
            prediction_source
        )
        
        return {
            "plan_context": plan_context,
            "performance_analysis": performance_analysis,
            "recovery_status": recovery_status,
            "injury_risk": injury_risk,
            "adjustments": adjustments,
            "ai_insights": ai_insights
        }
    
    def analyze_plan_context(self, athlete_id: int) -> Dict:
        """
        Analyze current training plan context.
        
        Critical for respecting periodization and plan structure.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with plan context information
        """
        # Get active workout plan
        plan = (
            self.db.query(WorkoutPlan)
            .filter(
                WorkoutPlan.athlete_id == athlete_id,
                WorkoutPlan.is_active == 1
            )
            .first()
        )
        
        if not plan:
            return {
                "has_plan": False,
                "training_type": TrainingType.HYPERTROPHY,
                "current_phase": TrainingPhase.ACCUMULATION,
                "week_number": 1,
                "is_deload_week": False,
            }
        
        # Get current plan entry (this week)
        current_entry = (
            self.db.query(PlanEntry)
            .filter(
                PlanEntry.workout_plan_id == plan.id,
                PlanEntry.start_date <= datetime.utcnow(),
                PlanEntry.end_date >= datetime.utcnow()
            )
            .first()
        )
        
        if not current_entry:
            # Create default entry if none exists
            week_number = self._calculate_current_week(plan)
            current_phase = self._determine_phase_from_week(
                week_number, plan.duration_weeks
            )
            is_deload = (week_number % 4 == 0)  # Every 4th week
            
            return {
                "has_plan": True,
                "plan_id": plan.id,
                "training_type": plan.training_type,
                "periodization_model": plan.periodization_model,
                "current_phase": current_phase,
                "week_number": week_number,
                "is_deload_week": is_deload,
                "target_volume_multiplier": 0.5 if is_deload else 1.0,
                "target_intensity_multiplier": 0.9 if is_deload else 1.0,
            }
        
        return {
            "has_plan": True,
            "plan_id": plan.id,
            "plan_entry_id": current_entry.id,
            "training_type": plan.training_type,
            "periodization_model": plan.periodization_model,
            "current_phase": current_entry.training_phase,
            "week_number": current_entry.week_number,
            "is_deload_week": bool(current_entry.is_deload_week),
            "target_volume_multiplier": current_entry.target_volume_multiplier,
            "target_intensity_multiplier": current_entry.target_intensity_multiplier,
            "planned_adjustments": current_entry.ai_adjustments or {}
        }
    
    def analyze_workout_performance(
        self,
        athlete: Athlete,
        workout_day_id: int,
        session_data: Dict,
        plan_context: Dict
    ) -> Dict:
        """
        Analyze workout performance vs prescribed parameters.
        
        Args:
            athlete: Athlete model
            workout_day_id: Workout day ID
            session_data: Session data with sets
            plan_context: Current plan context
            
        Returns:
            Dict with performance analysis
        """
        workout_day = self.db.query(WorkoutDay).filter(
            WorkoutDay.id == workout_day_id
        ).first()
        
        if not workout_day:
            return {}
        
        # Analyze each exercise
        exercise_analyses = []
        total_volume = 0
        rpe_values = []
        
        # Group sets by exercise
        exercise_sets = {}
        for set_data in session_data.get("exercise_sets", []):
            ex_id = set_data["exercise_id"]
            if ex_id not in exercise_sets:
                exercise_sets[ex_id] = []
            exercise_sets[ex_id].append(set_data)
        
        # Analyze each exercise
        for ex_id, sets in exercise_sets.items():
            # Get prescribed parameters
            prescribed = (
                self.db.query(WorkoutDayExercise)
                .filter(
                    WorkoutDayExercise.workout_day_id == workout_day_id,
                    WorkoutDayExercise.exercise_id == ex_id
                )
                .first()
            )
            
            if not prescribed:
                continue
            
            # Calculate volume for this exercise
            ex_volume = sum(s["weight"] * s["reps"] for s in sets)
            total_volume += ex_volume
            
            # Average RPE
            ex_rpe_values = [s["rpe"] for s in sets if s.get("rpe")]
            avg_rpe = sum(ex_rpe_values) / len(ex_rpe_values) if ex_rpe_values else None
            if avg_rpe:
                rpe_values.append(avg_rpe)
            
            # Estimate 1RM from best set
            best_set = max(sets, key=lambda s: s["weight"] * s["reps"])
            estimated_1rm = self.calc.estimate_1rm_average(
                best_set["weight"], best_set["reps"]
            )
            
            # Compare to prescribed
            actual_sets = len(sets)
            avg_reps = sum(s["reps"] for s in sets) / len(sets)
            
            sets_diff = actual_sets - prescribed.target_sets
            reps_in_range = prescribed.target_reps_min <= avg_reps <= prescribed.target_reps_max
            
            # RPE comparison
            rpe_diff = None
            if avg_rpe and prescribed.target_rpe:
                rpe_diff = avg_rpe - prescribed.target_rpe
            
            exercise_analyses.append({
                "exercise_id": ex_id,
                "prescribed_sets": prescribed.target_sets,
                "actual_sets": actual_sets,
                "sets_difference": sets_diff,
                "prescribed_reps_range": f"{prescribed.target_reps_min}-{prescribed.target_reps_max}",
                "actual_avg_reps": round(avg_reps, 1),
                "reps_in_range": reps_in_range,
                "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
                "target_rpe": prescribed.target_rpe,
                "rpe_difference": round(rpe_diff, 1) if rpe_diff else None,
                "estimated_1rm": round(estimated_1rm, 1),
                "volume": round(ex_volume, 1),
                "is_primary": bool(prescribed.is_primary)
            })
        
        # Overall performance metrics
        avg_workout_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
        
        # Determine overall performance level
        performance_level = self._assess_performance_level(
            exercise_analyses, avg_workout_rpe, plan_context
        )
        
        return {
            "workout_day_id": workout_day_id,
            "total_volume": round(total_volume, 1),
            "average_rpe": round(avg_workout_rpe, 1) if avg_workout_rpe else None,
            "exercise_analyses": exercise_analyses,
            "performance_level": performance_level,
            "exercises_completed": len(exercise_analyses)
        }
    
    def assess_recovery_status(
        self,
        athlete_id: int,
        recovery_data: Dict,
        plan_context: Dict
    ) -> Dict:
        """
        Assess recovery status using recovery analyzer.
        
        Args:
            athlete_id: Athlete ID
            recovery_data: Recovery metrics data
            plan_context: Plan context
            
        Returns:
            Dict with recovery assessment
        """
        # Calculate readiness score
        readiness_score = self.recovery_analyzer.calculate_readiness_score(
            sleep_quality=recovery_data["sleep_quality"],
            sleep_hours=recovery_data.get("sleep_hours"),
            overall_soreness=recovery_data.get("overall_soreness"),
            stress_level=recovery_data.get("stress_level"),
            energy_level=recovery_data.get("energy_level"),
            muscle_soreness=recovery_data.get("muscle_soreness")
        )
        
        # Calculate cumulative fatigue
        fatigue_status = self.recovery_analyzer.calculate_cumulative_fatigue(
            athlete_id, days_lookback=14
        )
        
        # Get recommendations
        recommendations = self.recovery_analyzer.get_recovery_recommendations(
            readiness_score,
            fatigue_status["fatigue_level"],
            recovery_data["sleep_quality"]
        )
        
        return {
            "readiness_score": readiness_score,
            "fatigue_status": fatigue_status,
            "recommendations": recommendations,
            "needs_deload": fatigue_status["needs_deload"]
        }
    
    def should_deload(
        self,
        athlete_id: int,
        current_readiness: float,
        lookback_sessions: int = 6
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if athlete should deload based on performance trends.
        
        Uses autoregulated logic instead of fixed time-based deloads:
        - Performance drop >10% over last 2+ sessions
        - Readiness score <0.5 for 3+ consecutive days
        - RPE spike >1.5 points at same or lower weight
        
        References:
        - Zourdos et al. (2016): RPE-based autoregulation
        - Mann et al. (2010): Autoregulatory progressive resistance
        
        Args:
            athlete_id: Athlete ID
            current_readiness: Current readiness score
            lookback_sessions: Number of recent sessions to analyze
            
        Returns:
            Tuple of (should_deload, reason)
        """
        thresholds = DELOAD_THRESHOLDS
        
        # Get recent performance trends
        recent_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        ).order_by(desc(PerformanceTrend.session_date)).limit(lookback_sessions).all()
        
        if len(recent_trends) < 3:
            # Not enough data for autoregulated deload
            return False, None
        
        # Check 1: Performance drop
        performance_scores = [t.performance_score for t in recent_trends]
        if len(performance_scores) >= 3:
            recent_avg = sum(performance_scores[:2]) / 2
            previous_avg = sum(performance_scores[2:4]) / 2 if len(performance_scores) >= 4 else performance_scores[2]
            
            if previous_avg > 0:
                performance_drop = (previous_avg - recent_avg) / previous_avg
                
                if performance_drop >= thresholds["performance_drop_percent"]:
                    return True, f"Performance dropped {performance_drop*100:.1f}% over last {lookback_sessions} sessions"
        
        # Check 2: Consecutive low readiness
        readiness_scores = [t.readiness_score for t in recent_trends[:thresholds["low_readiness_days"]]]
        low_readiness_count = sum(1 for score in readiness_scores if score < thresholds["low_readiness_threshold"])
        
        if low_readiness_count >= thresholds["low_readiness_days"]:
            return True, f"Readiness below {thresholds['low_readiness_threshold']} for {low_readiness_count} consecutive days"
        
        # Check 3: RPE spike with same/lower volume
        if len(recent_trends) >= 3:
            recent_rpe = recent_trends[0].average_rpe
            previous_rpe = recent_trends[2].average_rpe
            recent_volume = recent_trends[0].total_volume
            previous_volume = recent_trends[2].total_volume
            
            rpe_increase = recent_rpe - previous_rpe
            volume_ratio = recent_volume / previous_volume if previous_volume > 0 else 1.0
            
            # RPE spiked significantly while volume stayed same or decreased
            if rpe_increase >= thresholds["rpe_spike_threshold"] and volume_ratio <= 1.0:
                return True, f"RPE increased {rpe_increase:.1f} points with no volume increase - likely accumulated fatigue"
        
        # Check 4: Current readiness extremely low
        if current_readiness < 0.4:
            return True, f"Current readiness critically low: {current_readiness:.2f}"
        
        # No deload needed
        return False, None
    
    def calculate_next_workout_parameters_hybrid(
        self,
        athlete: Athlete,
        plan_context: Dict,
        performance: Dict,
        recovery: Dict,
        injury_risk: Dict
    ) -> Tuple[Dict, str]:
        """
        Calculate workout parameters using hybrid ML + rule-based approach.
        
        Tries ML prediction first, falls back to rule-based if:
        - ML not available
        - Model not trained
        - Confidence too low (<0.5)
        
        Args:
            athlete: Athlete model
            plan_context: Plan context
            performance: Performance analysis
            recovery: Recovery status
            injury_risk: Injury risk assessment
            
        Returns:
            Tuple of (adjustments_dict, source)
            - source: "ml", "hybrid", "rules"
        """
        ml_predictions = None
        ml_confidence = 0.0
        
        # Try ML prediction
        if self.ml_predictor and ML_AVAILABLE:
            try:
                ml_result, ml_source = self.ml_predictor.predict_workout_parameters(
                    athlete.id, fallback_to_rules=True
                )
                
                if ml_result and ml_source == "ml":
                    ml_predictions = ml_result
                    ml_confidence = ml_result.get("confidence", 0.0)
            except Exception as e:
                print(f"ML prediction error: {e}")
                ml_predictions = None
        
        # Get rule-based prediction
        rule_adjustments = self.calculate_next_workout_parameters(
            athlete, plan_context, performance, recovery, injury_risk
        )
        
        # Decide on prediction strategy
        if ml_predictions and ml_confidence >= 0.7:
            # High confidence ML - use 80% ML, 20% rules
            final_volume = (ml_predictions["volume_multiplier"] * 0.8) + (rule_adjustments["volume_multiplier"] * 0.2)
            final_intensity = (ml_predictions["intensity_multiplier"] * 0.8) + (rule_adjustments["intensity_multiplier"] * 0.2)
            
            return {
                "volume_multiplier": round(final_volume, 3),
                "intensity_multiplier": round(final_intensity, 3),
                "reasoning": f"Hybrid prediction (80% ML, 20% rules). ML confidence: {ml_confidence:.2f}",
                "exercise_adjustments": rule_adjustments.get("exercise_adjustments", {}),
                "ml_confidence": ml_confidence,
                "ml_feature_importance": ml_predictions.get("feature_importance", {})
            }, "hybrid_ml_dominant"
        
        elif ml_predictions and ml_confidence >= 0.5:
            # Medium confidence ML - use 50% ML, 50% rules
            final_volume = (ml_predictions["volume_multiplier"] * 0.5) + (rule_adjustments["volume_multiplier"] * 0.5)
            final_intensity = (ml_predictions["intensity_multiplier"] * 0.5) + (rule_adjustments["intensity_multiplier"] * 0.5)
            
            return {
                "volume_multiplier": round(final_volume, 3),
                "intensity_multiplier": round(final_intensity, 3),
                "reasoning": f"Hybrid prediction (50% ML, 50% rules). ML confidence: {ml_confidence:.2f}",
                "exercise_adjustments": rule_adjustments.get("exercise_adjustments", {}),
                "ml_confidence": ml_confidence
            }, "hybrid_balanced"
        
        else:
            # Low/no ML confidence - use pure rules
            rule_adjustments["ml_confidence"] = ml_confidence if ml_predictions else 0.0
            return rule_adjustments, "rules"
    
    def calculate_next_workout_parameters(
        self,
        athlete: Athlete,
        plan_context: Dict,
        performance: Dict,
        recovery: Dict,
        injury_risk: Dict
    ) -> Dict:
        """
        Calculate adjustments for next workout based on all factors.
        
        This is where the magic happens - intelligent progression!
        
        Args:
            athlete: Athlete model
            plan_context: Plan context
            performance: Performance analysis
            recovery: Recovery status
            injury_risk: Injury risk assessment
            
        Returns:
            Dict with adjustment parameters
        """
        training_type = plan_context.get("training_type", TrainingType.HYPERTROPHY)
        current_phase = plan_context.get("current_phase", TrainingPhase.ACCUMULATION)
        is_deload = plan_context.get("is_deload_week", False)
        
        # Base adjustment multipliers
        volume_adjustment = 1.0
        intensity_adjustment = 1.0
        
        # === Priority 1: Deload week overrides everything ===
        if is_deload:
            return {
                "volume_multiplier": 0.5,
                "intensity_multiplier": 0.9,
                "reasoning": "Planned deload week - reducing volume and intensity for recovery",
                "exercise_adjustments": {}
            }
        
        # === Priority 2: Injury risk ===
        if injury_risk["risk_level"] == "high":
            return {
                "volume_multiplier": 0.5,
                "intensity_multiplier": 0.85,
                "reasoning": "High injury risk detected - implementing immediate deload",
                "exercise_adjustments": {},
                "warnings": injury_risk["warnings"]
            }
        elif injury_risk["risk_level"] == "moderate":
            volume_adjustment *= 0.8
            intensity_adjustment *= 0.95
        
        # === Priority 3: Recovery status ===
        readiness = recovery["readiness_score"]
        if readiness < 0.5:
            volume_adjustment *= 0.7
            intensity_adjustment *= 0.9
        elif readiness < 0.7:
            volume_adjustment *= 0.85
            intensity_adjustment *= 0.95
        elif readiness > 0.9:
            # Great recovery allows normal progression
            pass
        
        # Check for fatigue-induced deload need
        if recovery.get("needs_deload"):
            return {
                "volume_multiplier": 0.5,
                "intensity_multiplier": 0.9,
                "reasoning": "Cumulative fatigue requires deload",
                "exercise_adjustments": {}
            }
        
        # === Priority 4: Performance-based adjustments ===
        performance_level = performance.get("performance_level", "on_target")
        
        # Get progression rates for athlete's experience
        progression_data = PROGRESSION_RATES[athlete.training_experience]
        
        # Adjust based on performance and training type
        if performance_level == "exceeding":
            # Performance was too easy - increase load
            if training_type == TrainingType.STRENGTH:
                intensity_adjustment *= (1 + progression_data["load_increase"])
            elif training_type == TrainingType.HYPERTROPHY:
                if current_phase == TrainingPhase.ACCUMULATION:
                    volume_adjustment *= 1.05  # Add volume
                else:
                    intensity_adjustment *= 1.025  # Add intensity
            elif training_type == TrainingType.HYBRID:
                intensity_adjustment *= 1.025
                volume_adjustment *= 1.025
        
        elif performance_level == "on_target":
            # Perfect - small progressive increase
            if training_type == TrainingType.STRENGTH:
                intensity_adjustment *= (1 + progression_data["load_increase"] * 0.5)
            elif training_type == TrainingType.HYPERTROPHY:
                volume_adjustment *= 1.025
            elif training_type == TrainingType.HYBRID:
                intensity_adjustment *= 1.015
                volume_adjustment *= 1.015
        
        elif performance_level == "struggling":
            # Performance was too hard - maintain or reduce
            volume_adjustment *= 0.95
            intensity_adjustment *= 0.98
        
        elif performance_level == "failed":
            # Significant struggle - reduce load
            volume_adjustment *= 0.85
            intensity_adjustment *= 0.90
        
        # === Priority 5: Phase-specific adjustments ===
        if current_phase == TrainingPhase.ACCUMULATION:
            # Volume phase - prioritize volume over intensity
            volume_adjustment *= 1.02
        elif current_phase == TrainingPhase.INTENSIFICATION:
            # Intensity phase - prioritize intensity, reduce volume
            intensity_adjustment *= 1.02
            volume_adjustment *= 0.95
        elif current_phase == TrainingPhase.REALIZATION:
            # Peaking phase - high intensity, low volume
            intensity_adjustment *= 1.01
            volume_adjustment *= 0.90
        
        # Cap adjustments for safety
        volume_adjustment = min(volume_adjustment, 1.15)
        intensity_adjustment = min(intensity_adjustment, 1.05)
        volume_adjustment = max(volume_adjustment, 0.80)
        intensity_adjustment = max(intensity_adjustment, 0.85)
        
        # Calculate exercise-specific adjustments
        exercise_adjustments = self._calculate_exercise_specific_adjustments(
            performance.get("exercise_analyses", []),
            intensity_adjustment,
            volume_adjustment,
            athlete.training_experience,
            training_type
        )
        
        # Generate reasoning
        reasoning = self._generate_adjustment_reasoning(
            performance_level,
            readiness,
            injury_risk["risk_level"],
            training_type,
            current_phase
        )
        
        return {
            "volume_multiplier": round(volume_adjustment, 3),
            "intensity_multiplier": round(intensity_adjustment, 3),
            "reasoning": reasoning,
            "exercise_adjustments": exercise_adjustments
        }
    
    def _calculate_exercise_specific_adjustments(
        self,
        exercise_analyses: List[Dict],
        base_intensity_adj: float,
        base_volume_adj: float,
        experience: TrainingExperience,
        training_type: TrainingType
    ) -> Dict:
        """
        Calculate adjustments for each specific exercise.
        
        Args:
            exercise_analyses: List of exercise performance analyses
            base_intensity_adj: Base intensity adjustment
            base_volume_adj: Base volume adjustment
            experience: Training experience
            training_type: Training type
            
        Returns:
            Dict mapping exercise_id to adjustments
        """
        adjustments = {}
        
        for analysis in exercise_analyses:
            ex_id = analysis["exercise_id"]
            rpe_diff = analysis.get("rpe_difference")
            
            # Start with base adjustments
            intensity_adj = base_intensity_adj
            volume_adj = base_volume_adj
            
            # Fine-tune based on RPE
            if rpe_diff is not None:
                if rpe_diff < -1.5:
                    # Too easy (actual RPE much lower than target)
                    intensity_adj *= 1.05
                elif rpe_diff < -0.5:
                    # Slightly too easy
                    intensity_adj *= 1.025
                elif rpe_diff > 1.5:
                    # Too hard
                    intensity_adj *= 0.95
                    volume_adj *= 0.95
                elif rpe_diff > 0.5:
                    # Slightly too hard
                    intensity_adj *= 0.98
            
            # Primary exercises get more conservative adjustments
            if analysis.get("is_primary"):
                intensity_adj = 1.0 + (intensity_adj - 1.0) * 0.8
            
            # Calculate actual weight suggestion
            # (Would need current weight from database in real implementation)
            
            adjustments[ex_id] = {
                "intensity_multiplier": round(intensity_adj, 3),
                "volume_multiplier": round(volume_adj, 3),
                "reason": self._get_exercise_adjustment_reason(rpe_diff)
            }
        
        return adjustments
    
    def _assess_performance_level(
        self,
        exercise_analyses: List[Dict],
        avg_rpe: Optional[float],
        plan_context: Dict
    ) -> str:
        """
        Assess overall performance level.
        
        Returns: "exceeding", "on_target", "struggling", or "failed"
        """
        if not exercise_analyses or avg_rpe is None:
            return "on_target"
        
        # Count exercises that hit/missed targets
        exceeded_count = 0
        on_target_count = 0
        struggled_count = 0
        
        for analysis in exercise_analyses:
            rpe_diff = analysis.get("rpe_difference")
            if rpe_diff is None:
                continue
            
            if rpe_diff < -1.0:
                exceeded_count += 1
            elif -1.0 <= rpe_diff <= 1.0:
                on_target_count += 1
            else:
                struggled_count += 1
        
        total = exceeded_count + on_target_count + struggled_count
        if total == 0:
            return "on_target"
        
        # Determine overall level
        if struggled_count / total > 0.5:
            return "failed"
        elif struggled_count / total > 0.3:
            return "struggling"
        elif exceeded_count / total > 0.6:
            return "exceeding"
        else:
            return "on_target"
    
    def _generate_adjustment_reasoning(
        self,
        performance_level: str,
        readiness: float,
        injury_risk: str,
        training_type: TrainingType,
        phase: TrainingPhase
    ) -> str:
        """Generate human-readable reasoning for adjustments."""
        reasons = []
        
        if performance_level == "exceeding":
            reasons.append("Performance exceeded targets - increasing load")
        elif performance_level == "struggling":
            reasons.append("Performance below targets - reducing load")
        elif performance_level == "on_target":
            reasons.append("Performance on target - progressive increase")
        
        if readiness < 0.7:
            reasons.append("Recovery not optimal - conservative adjustment")
        
        if injury_risk != "low":
            reasons.append(f"Injury risk {injury_risk} - safety priority")
        
        if phase == TrainingPhase.ACCUMULATION:
            reasons.append("Accumulation phase - volume focus")
        elif phase == TrainingPhase.INTENSIFICATION:
            reasons.append("Intensification phase - intensity focus")
        
        return " | ".join(reasons)
    
    def _get_exercise_adjustment_reason(self, rpe_diff: Optional[float]) -> str:
        """Get reason for exercise-specific adjustment."""
        if rpe_diff is None:
            return "Standard progression"
        elif rpe_diff < -1.0:
            return "Too easy - increasing load"
        elif rpe_diff > 1.0:
            return "Too challenging - reducing load"
        else:
            return "On target - maintaining progression"
    
    def _generate_ai_insights(
        self,
        performance: Dict,
        recovery: Dict,
        injury_risk: Dict,
        adjustments: Dict,
        prediction_source: str = "rules"
    ) -> List[str]:
        """Generate actionable AI insights."""
        insights = []
        
        # Prediction method insight
        if prediction_source.startswith("hybrid"):
            ml_conf = adjustments.get("ml_confidence", 0.0)
            insights.append(f"🤖 Using hybrid AI prediction (ML confidence: {ml_conf:.1%})")
        elif prediction_source == "ml":
            insights.append("🤖 Using pure ML prediction (high confidence)")
        else:
            insights.append("📊 Using rule-based prediction")
        
        # Performance insights
        perf_level = performance.get("performance_level")
        if perf_level == "exceeding":
            insights.append("💪 Excellent performance! Your strength is increasing consistently.")
        elif perf_level == "struggling":
            insights.append("⚠️ Performance below expectations. Consider reviewing recovery and nutrition.")
        
        # Recovery insights
        readiness = recovery.get("readiness_score", 0.7)
        if readiness < 0.6:
            insights.append("😴 Recovery is suboptimal. Prioritize sleep and rest days.")
        elif readiness > 0.9:
            insights.append("✅ Recovery is excellent. Your body is adapting well to training.")
        
        # Injury risk insights
        if injury_risk["risk_level"] == "high":
            insights.append("🚨 High injury risk detected. Immediate deload recommended.")
        elif injury_risk["risk_level"] == "moderate":
            insights.append("⚠️ Moderate injury risk. Monitor closely and reduce volume if needed.")
        
        # Progression insights
        volume_mult = adjustments.get("volume_multiplier", 1.0)
        intensity_mult = adjustments.get("intensity_multiplier", 1.0)
        
        if volume_mult > 1.05 or intensity_mult > 1.03:
            insights.append("📈 Progressive overload applied. Continue pushing forward!")
        elif volume_mult < 0.9 or intensity_mult < 0.95:
            insights.append("🔄 Backing off this week for recovery and adaptation.")
        
        return insights
    
    def _calculate_current_week(self, plan: WorkoutPlan) -> int:
        """Calculate current week number in plan."""
        days_since_start = (datetime.utcnow() - plan.start_date).days
        return max(1, days_since_start // 7 + 1)
    
    def _determine_phase_from_week(self, week: int, total_weeks: int) -> TrainingPhase:
        """Determine training phase from week number."""
        progress = week / total_weeks
        
        if progress < 0.6:
            return TrainingPhase.ACCUMULATION
        elif progress < 0.9:
            return TrainingPhase.INTENSIFICATION
        else:
            return TrainingPhase.REALIZATION


