"""
RPE calibration service.

Tracks RPE accuracy and adjusts RPE-to-RIR conversion based on individual athlete patterns.
Hybrid approach: rule-based tracking with ML enhancement capability (Phase 2).
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import statistics
import numpy as np

try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    GradientBoostingRegressor = None

from app.models import Athlete, Exercise, AthleteRPECalibration, ExerciseSet, WorkoutSession
from app.utils.constants import TrainingExperience, RPE_TO_RIR
from app.services.training_calculations import TrainingCalculations


class RPECalibrationService:
    """
    Manages RPE calibration and accuracy tracking.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.calc = TrainingCalculations()
        self.ml_model = None
        self.ml_model_trained = False
        self.ml_weight = 0.0  # Start with 0% ML, 100% rules
    
    def calibrate_rpe_to_rir(
        self,
        athlete_id: int,
        reported_rpe: float,
        exercise_id: Optional[int] = None
    ) -> float:
        """
        Convert RPE to RIR using calibrated conversion for this athlete.
        
        Uses athlete's historical accuracy to adjust standard RPE-to-RIR mapping.
        
        Args:
            athlete_id: Athlete ID
            reported_rpe: Reported RPE (6.0 - 10.0)
            exercise_id: Optional exercise ID for exercise-specific calibration
            
        Returns:
            Calibrated RIR (Reps in Reserve)
        """
        # Get standard RIR from RPE
        standard_rir = self._get_standard_rir(reported_rpe)
        
        # Get athlete's calibration factor
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return float(standard_rir)
        
        calibration_factor = athlete.rpe_calibration_factor
        
        # Get exercise-specific calibration if available
        if exercise_id:
            exercise_calibration = self.get_exercise_specific_calibration(
                athlete_id, exercise_id
            )
            if exercise_calibration:
                calibration_factor = exercise_calibration
        
        # Apply calibration
        # calibration_factor > 1.0 = athlete underestimates difficulty (reports lower RPE)
        # calibration_factor < 1.0 = athlete overestimates difficulty (reports higher RPE)
        calibrated_rir = standard_rir / calibration_factor
        
        return round(max(0, calibrated_rir), 1)
    
    @staticmethod
    def _get_standard_rir(rpe: float) -> int:
        """
        Get standard RIR from RPE using lookup table.
        
        Args:
            rpe: Reported RPE
            
        Returns:
            Standard RIR
        """
        # Find closest RPE value in lookup table
        closest_rpe = min(RPE_TO_RIR.keys(), key=lambda x: abs(x - rpe))
        return RPE_TO_RIR[closest_rpe]
    
    def track_rpe_accuracy(
        self,
        athlete_id: int,
        exercise_id: int,
        workout_session_id: int,
        reported_rpe: float,
        weight_used: float,
        reps_completed: int,
        reps_attempted: Optional[int] = None
    ) -> AthleteRPECalibration:
        """
        Track RPE accuracy for calibration.
        
        Compares reported RPE with estimated actual difficulty based on
        performance (reps achieved, proximity to failure).
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            workout_session_id: Workout session ID
            reported_rpe: RPE reported by athlete
            weight_used: Weight used (kg)
            reps_completed: Reps completed
            reps_attempted: Reps attempted (if went to failure)
            
        Returns:
            Created calibration record
        """
        # Predict RIR based on reported RPE
        predicted_rir = self.calibrate_rpe_to_rir(athlete_id, reported_rpe, exercise_id)
        
        # Calculate actual RIR if reps_attempted is provided
        actual_rir = None
        calibration_accuracy = None
        
        if reps_attempted is not None:
            actual_rir = reps_attempted - reps_completed
            
            # Calculate accuracy: how close was prediction to reality?
            if predicted_rir > 0:
                accuracy = 1.0 - abs(predicted_rir - actual_rir) / predicted_rir
                calibration_accuracy = max(0.0, min(1.0, accuracy))
        
        # Create calibration record
        calibration = AthleteRPECalibration(
            athlete_id=athlete_id,
            exercise_id=exercise_id,
            reported_rpe=reported_rpe,
            predicted_rir=predicted_rir,
            actual_rir=actual_rir,
            weight_used=weight_used,
            reps_completed=reps_completed,
            session_date=datetime.utcnow(),
            calibration_accuracy=calibration_accuracy
        )
        
        self.db.add(calibration)
        self.db.commit()
        self.db.refresh(calibration)
        
        # Update athlete's overall calibration factor if enough data
        self.update_athlete_calibration_factor(athlete_id)
        
        return calibration
    
    def update_athlete_calibration_factor(
        self,
        athlete_id: int,
        lookback_sessions: int = 10
    ) -> float:
        """
        Update athlete's overall RPE calibration factor based on recent history.
        
        Recalculates every 5-10 workouts to adapt to athlete's RPE reporting patterns.
        
        Args:
            athlete_id: Athlete ID
            lookback_sessions: Number of recent sessions to analyze
            
        Returns:
            Updated calibration factor
        """
        # Get recent calibration records with actual RIR
        recent_calibrations = self.db.query(AthleteRPECalibration).filter(
            AthleteRPECalibration.athlete_id == athlete_id,
            AthleteRPECalibration.actual_rir.isnot(None)
        ).order_by(desc(AthleteRPECalibration.session_date)).limit(lookback_sessions).all()
        
        if len(recent_calibrations) < 5:
            # Not enough data for calibration
            return 1.0
        
        # Calculate average error
        errors = []
        for cal in recent_calibrations:
            if cal.predicted_rir > 0 and cal.actual_rir is not None:
                # Positive error = athlete reported lower RPE than reality
                # Negative error = athlete reported higher RPE than reality
                error_ratio = cal.actual_rir / cal.predicted_rir
                errors.append(error_ratio)
        
        if not errors:
            return 1.0
        
        # Calculate new calibration factor as average of error ratios
        avg_error_ratio = statistics.mean(errors)
        
        # Smooth the adjustment (don't overcorrect)
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        current_factor = athlete.rpe_calibration_factor if athlete else 1.0
        
        # Apply 70% of new calculation, keep 30% of old (smoothing)
        new_factor = (avg_error_ratio * 0.7) + (current_factor * 0.3)
        
        # Clamp to reasonable range (0.7 - 1.3)
        new_factor = max(0.7, min(1.3, new_factor))
        
        # Update athlete record
        if athlete:
            athlete.rpe_calibration_factor = new_factor
            self.db.commit()
        
        return round(new_factor, 3)
    
    def get_exercise_specific_calibration(
        self,
        athlete_id: int,
        exercise_id: int,
        lookback_sessions: int = 5
    ) -> Optional[float]:
        """
        Get exercise-specific calibration factor.
        
        Some athletes may be more accurate on certain exercises than others.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            lookback_sessions: Number of recent sessions to analyze
            
        Returns:
            Exercise-specific calibration factor or None
        """
        # Get recent calibrations for this specific exercise
        exercise_calibrations = self.db.query(AthleteRPECalibration).filter(
            AthleteRPECalibration.athlete_id == athlete_id,
            AthleteRPECalibration.exercise_id == exercise_id,
            AthleteRPECalibration.actual_rir.isnot(None)
        ).order_by(desc(AthleteRPECalibration.session_date)).limit(lookback_sessions).all()
        
        if len(exercise_calibrations) < 3:
            # Not enough data for exercise-specific calibration
            return None
        
        # Calculate average accuracy for this exercise
        errors = []
        for cal in exercise_calibrations:
            if cal.predicted_rir > 0 and cal.actual_rir is not None:
                error_ratio = cal.actual_rir / cal.predicted_rir
                errors.append(error_ratio)
        
        if not errors:
            return None
        
        avg_error_ratio = statistics.mean(errors)
        
        # Only use exercise-specific calibration if significantly different from overall
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        overall_factor = athlete.rpe_calibration_factor if athlete else 1.0
        
        # If exercise-specific differs by >10%, use it
        if abs(avg_error_ratio - overall_factor) > 0.1:
            return round(max(0.7, min(1.3, avg_error_ratio)), 3)
        
        return None
    
    def get_calibration_status(
        self,
        athlete_id: int
    ) -> Dict:
        """
        Get athlete's RPE calibration status and statistics.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with calibration statistics
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"error": "Athlete not found"}
        
        # Get all calibration records
        all_calibrations = self.db.query(AthleteRPECalibration).filter(
            AthleteRPECalibration.athlete_id == athlete_id,
            AthleteRPECalibration.actual_rir.isnot(None)
        ).order_by(desc(AthleteRPECalibration.session_date)).all()
        
        total_records = len(all_calibrations)
        
        if total_records == 0:
            return {
                "calibration_factor": athlete.rpe_calibration_factor,
                "total_records": 0,
                "average_accuracy": None,
                "status": "insufficient_data",
                "message": "Complete more workouts to establish RPE calibration"
            }
        
        # Calculate average accuracy
        accuracies = [cal.calibration_accuracy for cal in all_calibrations if cal.calibration_accuracy is not None]
        avg_accuracy = statistics.mean(accuracies) if accuracies else None
        
        # Determine status
        if total_records < 5:
            status = "calibrating"
            message = f"Calibration in progress ({total_records}/5 sessions)"
        elif avg_accuracy and avg_accuracy > 0.8:
            status = "excellent"
            message = "RPE reporting is highly accurate"
        elif avg_accuracy and avg_accuracy > 0.6:
            status = "good"
            message = "RPE reporting is reasonably accurate"
        else:
            status = "needs_improvement"
            message = "RPE reporting needs calibration - focus on accurate failure estimation"
        
        return {
            "calibration_factor": athlete.rpe_calibration_factor,
            "total_records": total_records,
            "average_accuracy": round(avg_accuracy, 3) if avg_accuracy else None,
            "status": status,
            "message": message,
            "recent_sessions": self._get_recent_calibration_summary(all_calibrations[:10])
        }
    
    def _get_recent_calibration_summary(
        self,
        calibrations: List[AthleteRPECalibration]
    ) -> List[Dict]:
        """
        Get summary of recent calibration sessions.
        
        Args:
            calibrations: List of calibration records
            
        Returns:
            List of calibration summaries
        """
        summaries = []
        for cal in calibrations:
            summaries.append({
                "date": cal.session_date.isoformat(),
                "exercise_id": cal.exercise_id,
                "reported_rpe": cal.reported_rpe,
                "predicted_rir": cal.predicted_rir,
                "actual_rir": cal.actual_rir,
                "accuracy": cal.calibration_accuracy
            })
            return summaries
    
    # =========================================
    # ML ENHANCEMENT METHODS (Phase 2)
    # =========================================
    
    def train_ml_model(
        self,
        athlete_id: int,
        min_samples: int = 30
    ) -> Tuple[bool, Optional[str]]:
        """
        Train ML model for RIR prediction from RPE.
        
        Uses GradientBoostingRegressor to learn athlete-specific RPE patterns.
        
        Args:
            athlete_id: Athlete ID
            min_samples: Minimum calibration samples required
            
        Returns:
            Tuple of (success, error_message)
        """
        if not SKLEARN_AVAILABLE:
            return False, "scikit-learn not available"
        
        # Get all calibration data with actual RIR
        calibrations = self.db.query(AthleteRPECalibration).filter(
            AthleteRPECalibration.athlete_id == athlete_id,
            AthleteRPECalibration.actual_rir.isnot(None)
        ).order_by(desc(AthleteRPECalibration.session_date)).all()
        
        if len(calibrations) < min_samples:
            return False, f"Insufficient data. Need {min_samples} samples, have {len(calibrations)}"
        
        # Prepare features and targets
        X_list = []
        y_list = []
        
        for cal in calibrations:
            features = [
                cal.reported_rpe,
                cal.weight_used,
                cal.reps_completed,
                cal.reported_rpe * cal.reps_completed,  # Interaction feature
            ]
            X_list.append(features)
            y_list.append(cal.actual_rir)
        
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        
        # Train model
        try:
            self.ml_model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=3,
                random_state=42
            )
            
            self.ml_model.fit(X, y)
            self.ml_model_trained = True
            
            # Set ML weight based on sample size
            # 0% at 0 samples -> 70% at 50+ samples
            self.ml_weight = min(0.7, (len(calibrations) - min_samples) / (50 - min_samples) * 0.7)
            
            return True, None
        
        except Exception as e:
            return False, str(e)
    
    def predict_rir_with_ml(
        self,
        athlete_id: int,
        reported_rpe: float,
        weight_used: float,
        reps_completed: int,
        use_hybrid: bool = True
    ) -> Tuple[float, str]:
        """
        Predict RIR using ML model (hybrid with rules).
        
        Args:
            athlete_id: Athlete ID
            reported_rpe: Reported RPE
            weight_used: Weight used (kg)
            reps_completed: Reps completed
            use_hybrid: If True, combine ML and rule-based predictions
            
        Returns:
            Tuple of (predicted_rir, method_used)
        """
        # Get rule-based prediction
        rule_rir = self.calibrate_rpe_to_rir(athlete_id, reported_rpe)
        
        # Check if ML model is available and trained
        if not self.ml_model_trained or self.ml_model is None:
            return rule_rir, "rules"
        
        # Make ML prediction
        try:
            features = np.array([[
                reported_rpe,
                weight_used,
                reps_completed,
                reported_rpe * reps_completed
            ]], dtype=np.float32)
            
            ml_rir = self.ml_model.predict(features)[0]
            
            if use_hybrid and self.ml_weight > 0:
                # Weighted average of ML and rules
                hybrid_rir = (ml_rir * self.ml_weight) + (rule_rir * (1 - self.ml_weight))
                return round(max(0, hybrid_rir), 1), "hybrid"
            else:
                return round(max(0, ml_rir), 1), "ml"
        
        except Exception as e:
            print(f"ML prediction error: {e}")
            return rule_rir, "rules_fallback"
    
    def get_ml_model_status(
        self,
        athlete_id: int
    ) -> Dict:
        """
        Get ML model training status.
        
        Args:
            athlete_id: Athlete ID
            
        Returns:
            Dict with ML model status
        """
        # Count calibration samples
        sample_count = self.db.query(AthleteRPECalibration).filter(
            AthleteRPECalibration.athlete_id == athlete_id,
            AthleteRPECalibration.actual_rir.isnot(None)
        ).count()
        
        return {
            "ml_available": SKLEARN_AVAILABLE,
            "model_trained": self.ml_model_trained,
            "sample_count": sample_count,
            "ml_weight": self.ml_weight,
            "rule_weight": 1.0 - self.ml_weight,
            "min_samples_needed": 30,
            "optimal_samples": 50,
            "status": self._determine_ml_status(sample_count, self.ml_model_trained)
        }
    
    @staticmethod
    def _determine_ml_status(sample_count: int, trained: bool) -> str:
        """Determine ML model status."""
        if not SKLEARN_AVAILABLE:
            return "sklearn_unavailable"
        elif sample_count < 30:
            return "insufficient_data"
        elif not trained:
            return "ready_to_train"
        elif sample_count < 50:
            return "trained_low_confidence"
        else:
            return "trained_high_confidence"

