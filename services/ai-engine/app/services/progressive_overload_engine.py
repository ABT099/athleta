"""
Progressive Overload AI Engine

The core intelligence that analyzes workouts and calculates optimal progression.
Respects plan context, periodization, recovery, and injury prevention.
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import numpy as np

from app.models import (
    Athlete, WorkoutPlan, PlanEntry, WorkoutDay, WorkoutDayExercise,
    WorkoutSession, ExerciseSet, Exercise, RecoveryMetrics, PerformanceTrend,
    ExerciseMuscle, MuscleGroupModel
)
from app.services.training_calculations import TrainingCalculations
from app.services.recovery_analyzer import RecoveryAnalyzer
from app.services.injury_prevention import InjuryPreventionService
from app.services.exercise_progression import ExerciseProgressionService
from app.services.pr_tracker import PRTrackerService
from app.services.periodization import PeriodizationService
from app.services.rpe_calibration import RPECalibrationService
from app.services.volume_manager import VolumeManager
from app.services.form_quality_service import FormQualityService
from app.services.intensity_technique_service import IntensityTechniqueService
from app.utils.constants import (
    TrainingType, TrainingPhase, TrainingExperience, ExerciseType,
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
        self.volume_manager = VolumeManager(db)
        self.form_service = FormQualityService(db)
        self.intensity_technique = IntensityTechniqueService(db)
        
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
        
        # Step 4.5: Detect and intervene on plateaus (AUTOMATIC)
        from app.services.plateau_intervention import PlateauInterventionService
        plateau_service = PlateauInterventionService(self.db)
        plateau_interventions = plateau_service.detect_and_intervene(
            athlete_id, workout_day_id, session_data, performance_analysis
        )
        
        # Step 5: Try ML prediction first, fallback to rules
        adjustments, prediction_source = self.calculate_next_workout_parameters_hybrid(
            athlete,
            plan_context,
            performance_analysis,
            recovery_status,
            injury_risk
        )
        
        # Step 5.5: Apply constraint-based optimization
        training_type = plan_context.get("training_type", TrainingType.HYPERTROPHY)
        from app.ml.constrained_optimizer import ConstrainedOptimizer
        optimizer = ConstrainedOptimizer(self.db)
        optimized_params = optimizer.optimize(
            athlete_id,
            adjustments.get("volume_multiplier", 1.0),
            adjustments.get("intensity_multiplier", 1.0),
            injury_risk,
            recovery_status,
            training_type,
            athlete.training_experience
        )
        
        # Update adjustments with optimized parameters
        adjustments["volume_multiplier"] = optimized_params["volume_multiplier"]
        adjustments["intensity_multiplier"] = optimized_params["intensity_multiplier"]
        adjustments["constraints_satisfied"] = optimized_params.get("constraints_satisfied", True)
        # Track if adjustments were made to satisfy constraints
        adjustments_made = optimized_params.get("adjustments_made", {})
        if adjustments_made:
            adjustments["constraints_adjusted"] = (
                adjustments_made.get("volume_adjusted", False) or
                adjustments_made.get("intensity_adjusted", False)
            )
        
        # Add plateau interventions to adjustments
        if plateau_interventions.get("plateaus_detected", 0) > 0:
            adjustments["exercise_substitutions"] = plateau_interventions.get("exercise_substitutions", {})
            adjustments["volume_cycle_phase"] = plateau_interventions.get("volume_cycle_phase")
            adjustments["periodization_adjustment"] = plateau_interventions.get("periodization_adjustment")
        
        # Step 6: Generate insights and recommendations
        ai_insights = self._generate_ai_insights(
            performance_analysis,
            recovery_status,
            injury_risk,
            adjustments,
            prediction_source,
            plateau_interventions
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
                PlanEntry.start_date <= datetime.now(timezone.utc),
                PlanEntry.end_date >= datetime.now(timezone.utc)
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
                "duration_weeks": plan.duration_weeks,
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
            "duration_weeks": plan.duration_weeks,
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
            
            # Calculate expected sets (use midpoint of range for comparison)
            expected_sets = (prescribed.target_sets_min + prescribed.target_sets_max) / 2
            sets_diff = actual_sets - expected_sets
            reps_in_range = prescribed.target_reps_min <= avg_reps <= prescribed.target_reps_max
            
            # RPE comparison
            rpe_diff = None
            if avg_rpe and prescribed.target_rpe:
                rpe_diff = avg_rpe - prescribed.target_rpe
            
            # PR comparison
            pr_tracker = PRTrackerService(self.db)
            pr_comparison = pr_tracker.compare_to_pr(
                ex_id, athlete.id, best_set
            )
            
            exercise_analyses.append({
                "exercise_id": ex_id,
                "prescribed_sets_range": f"{prescribed.target_sets_min}-{prescribed.target_sets_max}",
                "expected_sets": round(expected_sets, 1),
                "actual_sets": actual_sets,
                "sets_difference": round(sets_diff, 1),
                "prescribed_reps_range": f"{prescribed.target_reps_min}-{prescribed.target_reps_max}",
                "actual_avg_reps": round(avg_reps, 1),
                "reps_in_range": reps_in_range,
                "average_rpe": round(avg_rpe, 1) if avg_rpe else None,
                "target_rpe": prescribed.target_rpe,
                "rpe_difference": round(rpe_diff, 1) if rpe_diff else None,
                "estimated_1rm": round(estimated_1rm, 1),
                "volume": round(ex_volume, 1),
                "is_primary": bool(prescribed.is_primary),
                "pr_context": pr_comparison
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
        Determine if athlete should deload based on comprehensive fatigue assessment.
        
        Uses autoregulated logic with multiple fatigue indicators:
        - Performance drop >10% over last 2+ sessions
        - Readiness score <0.5 for 3+ consecutive days
        - RPE spike >1.5 points at same or lower weight
        - ACWR (Acute:Chronic Workload Ratio) outside safe zone (0.8-1.3)
        - Session RPE (sRPE) spike: RPE × duration showing high total load
        
        References:
        - Zourdos et al. (2016): RPE-based autoregulation
        - Mann et al. (2010): Autoregulatory progressive resistance
        - Gabbett (2016): The training-injury prevention paradox (ACWR)
        
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
        
        # Check 4: ACWR (Acute:Chronic Workload Ratio)
        acwr_result = self._check_acwr(athlete_id)
        if acwr_result[0]:
            return True, acwr_result[1]
        
        # Check 5: Session RPE (sRPE) spike
        srpe_result = self._check_session_rpe_spike(athlete_id, lookback_sessions)
        if srpe_result[0]:
            return True, srpe_result[1]
        
        # Check 6: Current readiness extremely low
        if current_readiness < 0.4:
            return True, f"Current readiness critically low: {current_readiness:.2f}"
        
        # No deload needed
        return False, None
    
    def _check_acwr(self, athlete_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check Acute:Chronic Workload Ratio (ACWR).
        
        Safe zone: 0.8 - 1.3
        Elevated risk: < 0.8 (undertraining) or > 1.5 (overtraining)
        
        Reference: Gabbett (2016): The training-injury prevention paradox
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Tuple of (should_deload, reason)
        """
        from datetime import datetime, timedelta, timezone
        from app.models import WorkoutSession
        
        # Get recent sessions (last 7 days = acute)
        acute_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        # Get chronic sessions (last 28 days)
        chronic_cutoff = datetime.now(timezone.utc) - timedelta(days=28)
        
        # Calculate acute load (last 7 days)
        acute_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= acute_cutoff
            )
            .all()
        )
        
        acute_loads = []
        for session in acute_sessions:
            if session.total_volume and session.overall_rpe:
                # Normalized load: volume/1000 * RPE
                load = (session.total_volume / 1000) * session.overall_rpe
                acute_loads.append(load)
        
        # Calculate chronic load (last 28 days)
        chronic_sessions = (
            self.db.query(WorkoutSession)
            .filter(
                WorkoutSession.athlete_id == athlete_id,
                WorkoutSession.session_date >= chronic_cutoff
            )
            .all()
        )
        
        chronic_loads = []
        for session in chronic_sessions:
            if session.total_volume and session.overall_rpe:
                load = (session.total_volume / 1000) * session.overall_rpe
                chronic_loads.append(load)
        
        if len(acute_loads) == 0 or len(chronic_loads) == 0:
            return False, None
        
        # Calculate ACWR
        acwr = self.calc.calculate_acute_chronic_workload_ratio(acute_loads, chronic_loads)
        
        # Check if outside safe zone
        if acwr > 1.5:
            return True, f"ACWR {acwr:.2f} exceeds safe zone (>1.5) - high injury risk, deload recommended"
        elif acwr < 0.8:
            # Undertraining, not a deload trigger but worth noting
            return False, None
        
        return False, None
    
    def _check_session_rpe_spike(self, athlete_id: int, lookback_sessions: int) -> Tuple[bool, Optional[str]]:
        """
        Check for Session RPE (sRPE) spike.
        
        sRPE = RPE × duration (minutes)
        High sRPE indicates high total training load.
        
        Args:
            athlete_id: Athlete ID
            lookback_sessions: Number of sessions to look back
            
        Returns:
            Tuple of (should_deload, reason)
        """
        from app.models import WorkoutSession
        
        recent_sessions = (
            self.db.query(WorkoutSession)
            .filter(WorkoutSession.athlete_id == athlete_id)
            .order_by(desc(WorkoutSession.session_date))
            .limit(lookback_sessions)
            .all()
        )
        
        if len(recent_sessions) < 3:
            return False, None
        
        # Calculate sRPE for each session
        srpe_values = []
        for session in recent_sessions:
            if session.overall_rpe and session.duration_minutes:
                srpe = session.overall_rpe * session.duration_minutes
                srpe_values.append(srpe)
        
        if len(srpe_values) < 3:
            return False, None
        
        # Check if recent sRPE is significantly higher than previous
        recent_srpe = sum(srpe_values[:2]) / 2  # Average of last 2
        previous_srpe = sum(srpe_values[2:4]) / 2 if len(srpe_values) >= 4 else srpe_values[2]
        
        if previous_srpe > 0:
            srpe_increase = ((recent_srpe - previous_srpe) / previous_srpe) * 100
            
            # If sRPE increased >20% while volume/intensity stayed similar, suggests fatigue
            if srpe_increase > 20:
                return True, f"Session RPE (sRPE) increased {srpe_increase:.1f}% - high total training load detected"
        
        return False, None
    
    def _detect_extended_break(self, athlete_id: int) -> Tuple[Optional[int], Optional[float], Optional[float]]:
        """
        Detect extended break from training and calculate detraining adjustments.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Tuple of (days_since_last_workout, volume_multiplier, intensity_multiplier)
            Returns (None, None, None) if no break detected or no previous workouts
        """
        from app.models import WorkoutSession
        
        # Get last workout session
        last_session = (
            self.db.query(WorkoutSession)
            .filter(WorkoutSession.athlete_id == athlete_id)
            .order_by(desc(WorkoutSession.session_date))
            .first()
        )
        
        # If no previous workouts, return None (first workout ever)
        if not last_session:
            return None, None, None
        
        # Handle timezone-naive dates from database
        session_date = last_session.session_date
        if session_date.tzinfo is None:
            session_date = session_date.replace(tzinfo=timezone.utc)
        
        # Calculate days since last workout
        days_since = (datetime.now(timezone.utc) - session_date).days
        
        # Only apply adjustments for breaks of 7+ days
        if days_since < 7:
            return None, None, None
        
        # Calculate detraining adjustments based on break duration
        # 7-13 days: 15% reduction
        # 14-20 days: 25% reduction
        # 21+ days: 40% reduction
        if days_since <= 13:
            volume_mult = 0.85
            intensity_mult = 0.85
        elif days_since <= 20:
            volume_mult = 0.75
            intensity_mult = 0.75
        else:
            volume_mult = 0.60
            intensity_mult = 0.60
        
        return days_since, volume_mult, intensity_mult
    
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
        
        # Get uncertainty if available
        uncertainty = ml_predictions.get("uncertainty", 0.0) if ml_predictions else 1.0
        
        # Decide on prediction strategy using confidence and uncertainty
        if ml_predictions and ml_confidence >= 0.7 and uncertainty < 0.1:
            # High confidence, low uncertainty - use 80% ML, 20% rules
            ml_weight = 0.8
            final_volume = (ml_predictions["volume_multiplier"] * ml_weight) + (rule_adjustments["volume_multiplier"] * (1 - ml_weight))
            final_intensity = (ml_predictions["intensity_multiplier"] * ml_weight) + (rule_adjustments["intensity_multiplier"] * (1 - ml_weight))
            
            return {
                "volume_multiplier": round(final_volume, 3),
                "intensity_multiplier": round(final_intensity, 3),
                "reasoning": f"Hybrid prediction ({ml_weight*100:.0f}% ML, {(1-ml_weight)*100:.0f}% rules). ML confidence: {ml_confidence:.2f}, uncertainty: {uncertainty:.3f}",
                "exercise_adjustments": rule_adjustments.get("exercise_adjustments", {}),
                "ml_confidence": ml_confidence,
                "ml_uncertainty": uncertainty,
                "ml_feature_importance": ml_predictions.get("feature_importance", {})
            }, "hybrid_ml_dominant"
        
        elif ml_predictions and ml_confidence >= 0.5 and uncertainty < 0.15:
            # Medium confidence, moderate uncertainty - use 50% ML, 50% rules
            ml_weight = 0.5
            final_volume = (ml_predictions["volume_multiplier"] * ml_weight) + (rule_adjustments["volume_multiplier"] * (1 - ml_weight))
            final_intensity = (ml_predictions["intensity_multiplier"] * ml_weight) + (rule_adjustments["intensity_multiplier"] * (1 - ml_weight))
            
            return {
                "volume_multiplier": round(final_volume, 3),
                "intensity_multiplier": round(final_intensity, 3),
                "reasoning": f"Hybrid prediction ({ml_weight*100:.0f}% ML, {(1-ml_weight)*100:.0f}% rules). ML confidence: {ml_confidence:.2f}, uncertainty: {uncertainty:.3f}",
                "exercise_adjustments": rule_adjustments.get("exercise_adjustments", {}),
                "ml_confidence": ml_confidence,
                "ml_uncertainty": uncertainty
            }, "hybrid_balanced"
        
        elif ml_predictions and ml_confidence >= 0.3 and uncertainty < 0.2:
            # Low confidence or high uncertainty - use 30% ML, 70% rules
            ml_weight = 0.3
            final_volume = (ml_predictions["volume_multiplier"] * ml_weight) + (rule_adjustments["volume_multiplier"] * (1 - ml_weight))
            final_intensity = (ml_predictions["intensity_multiplier"] * ml_weight) + (rule_adjustments["intensity_multiplier"] * (1 - ml_weight))
            
            return {
                "volume_multiplier": round(final_volume, 3),
                "intensity_multiplier": round(final_intensity, 3),
                "reasoning": f"Hybrid prediction ({ml_weight*100:.0f}% ML, {(1-ml_weight)*100:.0f}% rules). ML confidence: {ml_confidence:.2f}, uncertainty: {uncertainty:.3f}",
                "exercise_adjustments": rule_adjustments.get("exercise_adjustments", {}),
                "ml_confidence": ml_confidence,
                "ml_uncertainty": uncertainty
            }, "hybrid_rules_dominant"
        
        else:
            # Very low confidence or very high uncertainty - use pure rules
            rule_adjustments["ml_confidence"] = ml_confidence if ml_predictions else 0.0
            rule_adjustments["ml_uncertainty"] = uncertainty if ml_predictions else 1.0
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
        
        # === Priority 2.5: Extended break detection ===
        # Check for extended break and apply detraining adjustments
        days_since_break, break_volume_mult, break_intensity_mult = self._detect_extended_break(athlete.id)
        break_info = None
        if days_since_break is not None:
            # Apply break adjustments (these are multipliers, so multiply)
            volume_adjustment *= break_volume_mult
            intensity_adjustment *= break_intensity_mult
            break_info = {
                "days_since_break": days_since_break,
                "volume_reduction": round((1 - break_volume_mult) * 100, 0),
                "intensity_reduction": round((1 - break_intensity_mult) * 100, 0)
            }
        
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
        
        # === Priority 4: Form quality gates ===
        # Check form quality trends and apply gates to prevent progression if form is poor
        form_quality_gates = {}
        form_blocked_exercises = []
        
        # Get exercises from performance analysis
        exercise_analyses = performance.get("exercise_analyses", [])
        for analysis in exercise_analyses:
            ex_id = analysis.get("exercise_id")
            if ex_id:
                should_block, reason = self.form_service.should_block_progression(
                    athlete.id, ex_id
                )
                
                if should_block:
                    form_quality_gates[ex_id] = {
                        "blocked": True,
                        "reason": reason
                    }
                    form_blocked_exercises.append(ex_id)
                    # Reduce adjustments for exercises with poor form
                    volume_adjustment *= 0.95
                    intensity_adjustment *= 0.95
        
        # If multiple exercises have form issues, apply broader reduction
        if len(form_blocked_exercises) > 2:
            volume_adjustment *= 0.9
            intensity_adjustment *= 0.95
        
        # === Priority 5: Performance-based adjustments ===
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
        
        # === Priority 6: Phase-specific adjustments ===
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
        
        # === Priority 7: Volume Landmarks (MEV/MAV/MRV) ===
        # Check volume position for primary muscle groups in the workout
        # Get muscle groups from performance analysis if available
        exercise_analyses = performance.get("exercise_analyses", [])
        if exercise_analyses and training_type == TrainingType.HYPERTROPHY:
            # For hypertrophy training, respect volume landmarks
            # Get volume recommendations for primary muscle groups
            
            # Sample a few key muscle groups to check (chest, back, legs)
            key_muscle_names = ["mid_chest", "lats", "quadriceps"]
            volume_adjustments_by_muscle = []
            
            for muscle_name in key_muscle_names:
                try:
                    volume_rec = self.volume_manager.get_volume_adjustment_recommendation(
                        athlete.id,
                        muscle_name,
                        athlete.training_experience,
                        volume_adjustment
                    )
                    if volume_rec["priority"] == "high":
                        # High priority recommendations should influence overall volume
                        volume_adjustments_by_muscle.append(volume_rec["adjustment"])
                except Exception:
                    # If volume calculation fails, continue without it
                    pass
            
            if volume_adjustments_by_muscle:
                # Average the high-priority adjustments
                avg_volume_adj = sum(volume_adjustments_by_muscle) / len(volume_adjustments_by_muscle)
                # Blend with current adjustment (70% current, 30% volume landmarks)
                volume_adjustment = (volume_adjustment * 0.7) + (avg_volume_adj * 0.3)
        
        # Cap adjustments for safety
        volume_adjustment = min(volume_adjustment, 1.15)
        intensity_adjustment = min(intensity_adjustment, 1.05)
        volume_adjustment = max(volume_adjustment, 0.80)
        intensity_adjustment = max(intensity_adjustment, 0.85)
        
        # Calculate exercise-specific adjustments
        exercise_adjustments = self._calculate_exercise_specific_adjustments(
            athlete.id,
            performance.get("exercise_analyses", []),
            intensity_adjustment,
            volume_adjustment,
            athlete.training_experience,
            training_type,
            form_quality_gates,
            plan_context,
            recovery,
            performance_level
        )
        
        # Generate reasoning
        reasoning = self._generate_adjustment_reasoning(
            performance_level,
            readiness,
            injury_risk["risk_level"],
            training_type,
            current_phase,
            form_blocked_exercises,
            break_info
        )
        
        return {
            "volume_multiplier": round(volume_adjustment, 3),
            "intensity_multiplier": round(intensity_adjustment, 3),
            "reasoning": reasoning,
            "exercise_adjustments": exercise_adjustments,
            "form_quality_gates": form_quality_gates
        }
    
    def _calculate_exercise_specific_adjustments(
        self,
        athlete_id: int,
        exercise_analyses: List[Dict],
        base_intensity_adj: float,
        base_volume_adj: float,
        experience: TrainingExperience,
        training_type: TrainingType,
        form_quality_gates: Optional[Dict] = None,
        plan_context: Optional[Dict] = None,
        recovery: Optional[Dict] = None,
        performance_level: Optional[str] = None
    ) -> Dict:
        """
        Calculate adjustments for each specific exercise, including intensity technique recommendations.
        
        Args:
            athlete_id: Athlete ID for intensity technique analysis
            exercise_analyses: List of exercise performance analyses
            base_intensity_adj: Base intensity adjustment
            base_volume_adj: Base volume adjustment
            experience: Training experience
            training_type: Training type
            form_quality_gates: Form quality gate information
            plan_context: Plan context with training phase
            recovery: Recovery status with readiness score
            performance_level: Overall performance level ("exceeding", "on_target", "struggling", "failed")
            
        Returns:
            Dict mapping exercise_id to adjustments
        """
        adjustments = {}
        
        # Get context for intensity technique recommendations
        training_phase = plan_context.get("current_phase", TrainingPhase.ACCUMULATION) if plan_context else TrainingPhase.ACCUMULATION
        readiness_score = recovery.get("readiness_score", 0.7) if recovery else 0.7
        week_number = plan_context.get("week_number") if plan_context else None
        
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
            
            # Apply form quality gates - block or reduce progression if form is poor
            form_gate_reason = None
            if form_quality_gates and ex_id in form_quality_gates:
                gate = form_quality_gates[ex_id]
                if gate.get("blocked"):
                    # Hold or reduce loads, don't progress
                    intensity_adj = min(intensity_adj, 0.95)  # Cap at 95% (slight reduction)
                    volume_adj = min(volume_adj, 0.95)
                    form_gate_reason = gate.get("reason")
            
            # Get exercise details for intensity technique recommendation
            exercise = self.db.query(Exercise).filter(Exercise.id == ex_id).first()
            exercise_type = ExerciseType.COMPOUND if exercise and exercise.exercise_type == "compound" else ExerciseType.ISOLATION
            
            # Get primary muscle group name for volume ceiling check
            muscle_name = None
            if exercise:
                # Get primary muscle (highest activation)
                primary_result = (
                    self.db.query(ExerciseMuscle, MuscleGroupModel)
                    .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
                    .filter(ExerciseMuscle.exercise_id == exercise.id)
                    .order_by(ExerciseMuscle.activation_percent.desc())
                    .first()
                )
                if primary_result:
                    link, muscle = primary_result
                    muscle_name = muscle.name
            
            # Recommend intensity techniques (only if triggers detected)
            technique_recommendation = self.intensity_technique.recommend_techniques(
                athlete_id=athlete_id,
                exercise_id=ex_id,
                training_type=training_type,
                training_phase=training_phase,
                exercise_type=exercise_type,
                experience=experience,
                readiness_score=readiness_score,
                is_primary=analysis.get("is_primary", True),
                order_in_workout=analysis.get("order_in_workout", 1),
                performance_level=performance_level,
                week_number=week_number,
                muscle_name=muscle_name,
            )
            
            # Calculate fatigue impact of technique
            base_vol = analysis.get("volume", 0) or 1000  # Fallback if volume not available
            fatigue_impact = self.intensity_technique.calculate_fatigue_impact(
                technique_recommendation["set_type"],
                technique_recommendation["rep_style"],
                base_vol
            )
            
            # Adjust volume/fatigue multipliers based on technique
            volume_adj *= fatigue_impact["volume_multiplier"]
            # Note: Fatigue multiplier could be used for recovery calculations
            
            adjustments[ex_id] = {
                "intensity_multiplier": round(intensity_adj, 3),
                "volume_multiplier": round(volume_adj, 3),
                "reason": self._get_exercise_adjustment_reason(rpe_diff),
                "intensity_technique": {
                    "set_type": technique_recommendation["set_type"].value,
                    "rep_style": technique_recommendation["rep_style"].value,
                    "set_type_params": technique_recommendation["set_type_params"],
                    "rep_style_params": technique_recommendation["rep_style_params"],
                    "reasoning": technique_recommendation["reasoning"],
                    "fatigue_impact": fatigue_impact,
                    "triggers": technique_recommendation.get("triggers", {})
                }
            }
            
            if form_gate_reason:
                adjustments[ex_id]["form_gate_reason"] = form_gate_reason
        
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
        phase: TrainingPhase,
        form_blocked_exercises: Optional[List[int]] = None,
        break_info: Optional[Dict] = None
    ) -> str:
        """Generate human-readable reasoning for adjustments."""
        reasons = []
        
        # Extended break takes priority in reasoning
        if break_info:
            days = break_info["days_since_break"]
            vol_reduction = int(break_info["volume_reduction"])
            int_reduction = int(break_info["intensity_reduction"])
            reasons.append(
                f"Extended break detected ({days} days) - reducing volume by {vol_reduction}% "
                f"and intensity by {int_reduction}% to account for detraining"
            )
        
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
        
        if form_blocked_exercises:
            count = len(form_blocked_exercises)
            reasons.append(
                f"Form quality below target on {count} exercise{'s' if count > 1 else ''} - "
                f"maintaining loads"
            )
        
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
        prediction_source: str = "rules",
        plateau_interventions: Optional[Dict] = None
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
        
        # Plateau intervention insights (AUTOMATIC)
        if plateau_interventions and plateau_interventions.get("plateaus_detected", 0) > 0:
            for intervention in plateau_interventions.get("interventions", []):
                exercise_name = intervention.get("exercise_name", "Exercise")
                intervention_type = intervention.get("intervention_type")
                recommendation = intervention.get("recommendation", "")
                
                if intervention_type == "exercise_substitution":
                    # Get substitute name from intervention dict
                    substitute_name = intervention.get("substitute_exercise_name", "alternative exercise")
                    insights.append(f"🔄 Plateau detected on {exercise_name} - substituting with {substitute_name} for novel stimulus")
                elif intervention_type == "volume_cycling":
                    insights.append(f"📈 {recommendation}")
                elif intervention_type == "periodization_adjustment":
                    insights.append(f"⚙️ {recommendation}")
                else:
                    insights.append(f"⚠️ Plateau detected on {exercise_name} - {recommendation}")
        
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
        
        # Constraint optimization insights
        if adjustments.get("constraints_adjusted", False):
            insights.append("🛡️ Parameters adjusted to satisfy injury prevention constraints")
        
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
        # Handle timezone-naive dates from database
        start_date = plan.start_date
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        days_since_start = (datetime.now(timezone.utc) - start_date).days
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
    
    def create_performance_trend_for_session(
        self,
        workout_session: WorkoutSession,
        recovery_status: Dict,
        performance_analysis: Dict,
        athlete_id: int
    ) -> PerformanceTrend:
        """
        Create PerformanceTrend record for a completed workout session.
        
        This must be called before ML prediction so the new session is included
        in feature extraction.
        
        Args:
            workout_session: Completed WorkoutSession
            recovery_status: Recovery status dict with readiness_score and fatigue_status
            performance_analysis: Performance analysis dict with total_volume, average_rpe
            athlete_id: Athlete ID
            
        Returns:
            Created PerformanceTrend instance (not yet committed)
        """
        # Calculate average intensity from exercise sets
        average_intensity = self._calculate_average_intensity(
            workout_session.id, performance_analysis
        )
        
        # Calculate performance score
        performance_score = self._calculate_performance_score(
            total_volume=performance_analysis.get("total_volume", 0),
            average_intensity=average_intensity,
            readiness_score=recovery_status.get("readiness_score", 0.5),
            fatigue_index=recovery_status.get("fatigue_status", {}).get("fatigue_score", 0.0)
        )
        
        # Calculate volume load
        total_volume = performance_analysis.get("total_volume", 0)
        volume_load = total_volume * average_intensity
        
        # Calculate training load metrics
        acute_load, chronic_load, acwr = self._calculate_training_load_metrics(
            athlete_id, workout_session.session_date, volume_load
        )
        
        # Calculate training monotony and strain (optional, can be simplified)
        training_monotony = None
        training_strain = None
        if acute_load is not None:
            # Simplified monotony calculation
            # Get recent loads including the current one we're creating
            recent_loads = self._get_recent_volume_loads(athlete_id, days=7, include_current=volume_load)
            if len(recent_loads) > 1:
                mean_load = np.mean(recent_loads)
                std_load = np.std(recent_loads) if len(recent_loads) > 1 else 1.0
                training_monotony = mean_load / (std_load + 0.1)  # Add small epsilon to avoid division by zero
                training_strain = volume_load * recovery_status.get("fatigue_status", {}).get("fatigue_score", 0.0)
        
        # Get average RPE
        average_rpe = performance_analysis.get("average_rpe") or workout_session.overall_rpe or 7.0
        
        # Get readiness score
        readiness_score = recovery_status.get("readiness_score", 0.5)
        
        # Get fatigue index
        fatigue_index = recovery_status.get("fatigue_status", {}).get("fatigue_score", 0.0)
        
        # Create PerformanceTrend
        performance_trend = PerformanceTrend(
            athlete_id=athlete_id,
            workout_session_id=workout_session.id,
            session_date=workout_session.session_date,
            total_volume=total_volume,
            average_intensity=average_intensity,
            average_rpe=average_rpe,
            readiness_score=readiness_score,
            performance_score=performance_score,
            fatigue_index=fatigue_index,
            volume_load=volume_load,
            training_monotony=training_monotony,
            training_strain=training_strain,
            acute_load=acute_load,
            chronic_load=chronic_load,
            acwr=acwr,
            deload_triggered=False,
            deload_reason=None
        )
        
        self.db.add(performance_trend)
        return performance_trend
    
    def _calculate_average_intensity(
        self,
        workout_session_id: int,
        performance_analysis: Dict
    ) -> float:
        """
        Calculate average intensity from exercise sets.
        
        Intensity is calculated as weighted average of (weight / estimated_1RM) for each set.
        
        Args:
            workout_session_id: WorkoutSession ID
            performance_analysis: Performance analysis dict with exercise_analyses
            
        Returns:
            Average intensity (0.0 - 1.0)
        """
        exercise_analyses = performance_analysis.get("exercise_analyses", [])
        
        if not exercise_analyses:
            # Fallback: query exercise sets directly
            exercise_sets = self.db.query(ExerciseSet).filter(
                ExerciseSet.workout_session_id == workout_session_id
            ).all()
            
            if not exercise_sets:
                return 0.7  # Default intensity
            
            intensities = []
            for set_data in exercise_sets:
                if set_data.weight and set_data.reps:
                    # Estimate 1RM
                    estimated_1rm = self.calc.estimate_1rm_average(set_data.weight, set_data.reps)
                    if estimated_1rm > 0:
                        intensity = set_data.weight / estimated_1rm
                        intensities.append(intensity)
            
            if intensities:
                return sum(intensities) / len(intensities)
            return 0.7
        
        # Query actual exercise sets for accurate intensity calculation
        exercise_sets = self.db.query(ExerciseSet).filter(
            ExerciseSet.workout_session_id == workout_session_id
        ).all()
        
        if exercise_sets:
            intensities = []
            for set_data in exercise_sets:
                if set_data.weight and set_data.reps:
                    # Estimate 1RM
                    estimated_1rm = self.calc.estimate_1rm_average(set_data.weight, set_data.reps)
                    if estimated_1rm > 0:
                        intensity = set_data.weight / estimated_1rm
                        intensities.append(intensity)
            
            if intensities:
                return sum(intensities) / len(intensities)
        
        # Fallback: use exercise analyses if available
        intensities = []
        for ex_analysis in exercise_analyses:
            estimated_1rm = ex_analysis.get("estimated_1rm")
            if estimated_1rm and estimated_1rm > 0:
                # Use established RPE-to-intensity mapping (Zourdos et al., 2016)
                avg_rpe = ex_analysis.get("average_rpe", 7.0)
                # Round to nearest 0.5 for lookup
                rpe_rounded = round(avg_rpe * 2) / 2
                # Clamp to valid range
                rpe_rounded = max(5.0, min(10.0, rpe_rounded))
                # Lookup intensity
                from app.utils.constants import RPE_TO_INTENSITY
                estimated_intensity = RPE_TO_INTENSITY.get(rpe_rounded, 0.86)  # Default to 7 RPE
                intensities.append(estimated_intensity)
        
        if intensities:
            return sum(intensities) / len(intensities)
        
        return 0.7  # Default intensity
    
    def _calculate_performance_score(
        self,
        total_volume: float,
        average_intensity: float,
        readiness_score: float,
        fatigue_index: float
    ) -> float:
        """
        Calculate composite performance score.
        
        Combines volume, intensity, readiness, and fatigue into a single score.
        Higher score = better performance.
        
        Args:
            total_volume: Total volume lifted (kg)
            average_intensity: Average intensity (0.0-1.0)
            readiness_score: Readiness score (0.0-1.0)
            fatigue_index: Fatigue index (0.0-1.0, higher = more fatigue)
            
        Returns:
            Performance score (typically 0.0-1.5)
        """
        # Normalize volume (assume typical range 1000-5000 kg)
        volume_normalized = min(total_volume / 3000.0, 1.5)  # Cap at 1.5x
        
        # Intensity component (0.0-1.0)
        intensity_component = average_intensity
        
        # Readiness component (0.0-1.0)
        readiness_component = readiness_score
        
        # Fatigue penalty (reduces score)
        fatigue_penalty = fatigue_index * 0.3  # Max 30% reduction
        
        # Weighted combination
        performance_score = (
            volume_normalized * 0.3 +  # Volume contribution
            intensity_component * 0.3 +  # Intensity contribution
            readiness_component * 0.4  # Readiness contribution (most important)
        ) * (1.0 - fatigue_penalty)
        
        # Clamp to reasonable range
        return max(0.0, min(1.5, performance_score))
    
    def _calculate_training_load_metrics(
        self,
        athlete_id: int,
        session_date: datetime,
        current_volume_load: float
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate acute load, chronic load, and ACWR.
        
        Args:
            athlete_id: Athlete ID
            session_date: Date of current session
            current_volume_load: Volume load for current session
            
        Returns:
            Tuple of (acute_load, chronic_load, acwr)
        """
        # Get recent performance trends (excluding current session)
        recent_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id,
            PerformanceTrend.session_date < session_date
        ).order_by(desc(PerformanceTrend.session_date)).all()
        
        # Calculate acute load (last 7 days including current)
        acute_cutoff = session_date - timedelta(days=7)
        acute_loads = [current_volume_load]  # Include current session
        for trend in recent_trends:
            if trend.session_date >= acute_cutoff:
                acute_loads.append(trend.volume_load)
            else:
                break
        
        acute_load = sum(acute_loads) if acute_loads else None
        
        # Calculate chronic load (last 28 days including current)
        chronic_cutoff = session_date - timedelta(days=28)
        chronic_loads = [current_volume_load]  # Include current session
        for trend in recent_trends:
            if trend.session_date >= chronic_cutoff:
                chronic_loads.append(trend.volume_load)
            else:
                break
        
        chronic_load = sum(chronic_loads) / len(chronic_loads) if chronic_loads else None
        
        # Calculate ACWR
        acwr = None
        if acute_load is not None and chronic_load is not None and chronic_load > 0:
            # Use weekly average for acute (7 days)
            acute_weekly_avg = acute_load / 7.0
            acwr = self.calc.calculate_acute_chronic_workload_ratio(
                [acute_weekly_avg],  # Single value for current week
                [chronic_load]  # Single value for chronic average
            )
        
        return acute_load, chronic_load, acwr
    
    def _get_recent_volume_loads(
        self,
        athlete_id: int,
        days: int = 7,
        include_current: Optional[float] = None
    ) -> List[float]:
        """
        Get recent volume loads for an athlete.
        
        Args:
            athlete_id: Athlete ID
            days: Number of days to look back
            include_current: Optional current volume load to include in results
            
        Returns:
            List of volume loads
        """
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id,
            PerformanceTrend.session_date >= cutoff
        ).order_by(PerformanceTrend.session_date).all()
        
        loads = [t.volume_load for t in trends]
        
        # Include current load if provided (for monotony calculation)
        if include_current is not None:
            loads.append(include_current)
        
        return loads


