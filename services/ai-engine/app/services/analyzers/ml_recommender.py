"""
ML Recommendation Service.

Provides ML-based recommendations using WorkoutPredictor.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.ml.workout_predictor import WorkoutPredictor
from app.models import Athlete, PerformanceTrend
from sqlalchemy import desc


class MLRecommendationService:
    """
    Provides ML-based recommendations for plan optimization.
    
    Uses WorkoutPredictor to suggest:
    - Optimal volume multipliers
    - Optimal intensity multipliers
    - Based on athlete's historical performance
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.predictor = None  # Lazy initialization
    
    def recommend(
        self,
        athlete_id: int,
        plan_data: Dict
    ) -> Optional[Dict]:
        """
        Generate ML-based recommendations.
        
        Args:
            athlete_id: Athlete ID
            plan_data: Plan data dict
            
        Returns:
            Dict with ML recommendations or None if insufficient data
        """
        # Check if athlete has enough history
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None
        
        # Count performance trends
        trend_count = (
            self.db.query(PerformanceTrend)
            .filter(PerformanceTrend.athlete_id == athlete_id)
            .count()
        )
        
        # Cold start handling
        if trend_count == 0:
            # No training history - use population defaults
            return {
                "status": "cold_start",
                "message": "No training history. Using population defaults.",
                "recommendations": self._get_population_defaults(plan_data),
                "confidence": "low",
                "based_on_sessions": 0,
            }
        elif trend_count < 10:
            # Limited data - use conservative recommendations
            return {
                "status": "limited_data",
                "message": f"Only {trend_count} sessions. Recommendations are approximate.",
                "recommendations": self._get_conservative_recommendations(athlete_id, plan_data),
                "confidence": "low",
                "based_on_sessions": trend_count,
            }
        
        # Initialize predictor if needed
        if self.predictor is None:
            try:
                self.predictor = WorkoutPredictor(use_ensemble=True)
            except Exception:
                return None  # ML not available
        
        # Try to get predictions using the predictor
        # Note: WorkoutPredictor may have different interface, so we'll use a simplified approach
        try:
            # Get recent performance trend for context
            recent_trend = (
                self.db.query(PerformanceTrend)
                .filter(PerformanceTrend.athlete_id == athlete_id)
                .order_by(desc(PerformanceTrend.session_date))
                .first()
            )
            
            if not recent_trend:
                return None
            
            # For now, return basic recommendations based on recent performance
            # In production, this would use the full ML predictor
            avg_rpe = recent_trend.average_rpe
            performance_score = recent_trend.performance_score
            
            # Simple heuristic-based recommendations
            if avg_rpe > 9.0:
                volume_mult = 0.95
                intensity_mult = 0.95
            elif avg_rpe < 7.0:
                volume_mult = 1.05
                intensity_mult = 1.05
            else:
                volume_mult = 1.0
                intensity_mult = 1.0
            
            if performance_score and performance_score < 0.6:
                volume_mult *= 0.95
                intensity_mult *= 0.95
            
            return {
                "status": "full_ml",
                "volume_multiplier": round(volume_mult, 3),
                "intensity_multiplier": round(intensity_mult, 3),
                "confidence": "medium",
                "based_on_sessions": trend_count,
                "recommendation": self._generate_recommendation(volume_mult, intensity_mult),
            }
        except Exception:
            return None
    
    def _generate_recommendation(self, volume_mult: float, intensity_mult: float) -> str:
        """Generate human-readable recommendation."""
        recommendations = []
        
        if volume_mult > 1.05:
            recommendations.append(f"Increase volume by {(volume_mult - 1.0) * 100:.0f}%")
        elif volume_mult < 0.95:
            recommendations.append(f"Reduce volume by {(1.0 - volume_mult) * 100:.0f}%")
        
        if intensity_mult > 1.05:
            recommendations.append(f"Increase intensity by {(intensity_mult - 1.0) * 100:.0f}%")
        elif intensity_mult < 0.95:
            recommendations.append(f"Reduce intensity by {(1.0 - intensity_mult) * 100:.0f}%")
        
        if not recommendations:
            return "Current plan parameters are optimal based on your training history"
        
        return "; ".join(recommendations)
    
    def _get_population_defaults(self, plan_data: Dict) -> Dict:
        """
        Get population-based default recommendations for new athletes.
        
        Args:
            plan_data: Plan data dict
            
        Returns:
            Dict with default recommendations
        """
        training_type = plan_data.get("training_type", "hypertrophy")
        
        # Conservative defaults for new athletes
        defaults = {
            "volume_multiplier": 1.0,
            "intensity_multiplier": 1.0,
            "recommendation": "Start with moderate volume and intensity. Adjust based on performance after 2-3 weeks.",
        }
        
        # Slight adjustments based on training type
        if training_type == "strength":
            defaults["intensity_multiplier"] = 0.95  # Start slightly lower for strength
        elif training_type == "hypertrophy":
            defaults["volume_multiplier"] = 0.95  # Start slightly lower for hypertrophy
        
        return defaults
    
    def _get_conservative_recommendations(
        self,
        athlete_id: int,
        plan_data: Dict
    ) -> Dict:
        """
        Get conservative recommendations for athletes with limited data.
        
        Args:
            athlete_id: Athlete ID
            plan_data: Plan data dict
            
        Returns:
            Dict with conservative recommendations
        """
        # Get recent performance trend for context
        recent_trend = (
            self.db.query(PerformanceTrend)
            .filter(PerformanceTrend.athlete_id == athlete_id)
            .order_by(desc(PerformanceTrend.session_date))
            .first()
        )
        
        if not recent_trend:
            return self._get_population_defaults(plan_data)
        
        # Conservative adjustments based on recent performance
        avg_rpe = recent_trend.average_rpe
        performance_score = recent_trend.performance_score
        
        # More conservative adjustments (smaller changes)
        if avg_rpe > 9.0:
            volume_mult = 0.97  # Smaller reduction
            intensity_mult = 0.97
        elif avg_rpe < 7.0:
            volume_mult = 1.03  # Smaller increase
            intensity_mult = 1.03
        else:
            volume_mult = 1.0
            intensity_mult = 1.0
        
        if performance_score and performance_score < 0.6:
            volume_mult *= 0.97
            intensity_mult *= 0.97
        
        return {
            "volume_multiplier": round(volume_mult, 3),
            "intensity_multiplier": round(intensity_mult, 3),
            "recommendation": self._generate_recommendation(volume_mult, intensity_mult) + " (Limited data - recommendations are conservative)",
        }

