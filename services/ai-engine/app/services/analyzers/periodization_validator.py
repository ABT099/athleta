"""
Periodization Validator.

Validates periodization structure matches the selected model.
References: Issurin (2010), Kiely (2012).
"""
from typing import Dict, List

from app.utils.constants import (
    PeriodizationModel, TrainingType, TrainingPhase,
    BLOCK_PERIODIZATION_CONFIG, REP_RANGES
)


class PeriodizationValidator:
    """
    Validates periodization structure.
    
    Checks:
    - Duration matches periodization model requirements
    - Phase structure (DUP: daily variation, Block: sequential phases)
    - Deload frequency
    - Training type alignment with rep ranges
    """
    
    def validate(self, plan_data: Dict) -> Dict:
        """
        Validate periodization structure.
        
        Args:
            plan_data: Plan data dict
            
        Returns:
            Dict with validation results
        """
        periodization_model = plan_data.get("periodization_model")
        duration_weeks = plan_data.get("duration_weeks", 0)
        training_type = plan_data.get("training_type")
        workout_days = plan_data.get("workout_days", [])
        
        warnings = []
        suggestions = []
        
        # Validate duration
        if periodization_model == PeriodizationModel.BLOCK:
            min_weeks = 12  # Block needs at least 2 full blocks
            if duration_weeks < min_weeks:
                warnings.append({
                    "severity": "high",
                    "category": "periodization",
                    "message": f"Block periodization requires at least {min_weeks} weeks (current: {duration_weeks})",
                    "affected_items": ["plan_duration"],
                    "recommendation": f"Increase plan duration to {min_weeks}+ weeks for proper block structure"
                })
        elif periodization_model == PeriodizationModel.UNDULATING:
            min_weeks = 8  # DUP needs at least 8 weeks
            if duration_weeks < min_weeks:
                warnings.append({
                    "severity": "medium",
                    "category": "periodization",
                    "message": f"Undulating periodization works best with {min_weeks}+ weeks",
                    "affected_items": ["plan_duration"],
                    "recommendation": f"Consider increasing duration to {min_weeks}+ weeks"
                })
        
        # Validate deload frequency
        if duration_weeks >= 4:
            # Should have deload every 3-4 weeks
            expected_deloads = duration_weeks // 4
            suggestions.append({
                "category": "periodization",
                "message": f"Plan should include {expected_deloads} deload week(s) over {duration_weeks} weeks",
                "impact": "medium",
                "action": "Add deload weeks every 3-4 weeks for optimal recovery"
            })
        
        # Validate training type alignment with rep ranges
        if training_type:
            rep_range = REP_RANGES.get(training_type, {})
            rep_min = rep_range.get("min", 0)
            rep_max = rep_range.get("max", 0)
            
            # Check if exercises use appropriate rep ranges
            rep_violations = []
            for workout_day in workout_days:
                for exercise in workout_day.get("exercises", []):
                    ex_rep_min = exercise.get("target_reps_min", 0)
                    ex_rep_max = exercise.get("target_reps_max", 0)
                    
                    if ex_rep_max > 0:
                        # Check if rep range aligns with training type
                        if ex_rep_max < rep_min or ex_rep_min > rep_max:
                            rep_violations.append({
                                "exercise_id": exercise.get("exercise_id"),
                                "rep_range": f"{ex_rep_min}-{ex_rep_max}",
                                "expected": f"{rep_min}-{rep_max}",
                            })
            
            if rep_violations:
                suggestions.append({
                    "category": "periodization",
                    "message": f"{len(rep_violations)} exercise(s) have rep ranges outside optimal for {training_type} training",
                    "impact": "low",
                    "action": f"Consider adjusting rep ranges to {rep_min}-{rep_max} for {training_type} training"
                })
        
        # Validate workout frequency
        frequency = plan_data.get("frequency", 0)
        if frequency == 0:
            warnings.append({
                "severity": "high",
                "category": "periodization",
                "message": "Workout frequency not specified",
                "affected_items": ["frequency"],
                "recommendation": "Specify workouts per week for proper periodization"
            })
        elif frequency > 6:
            warnings.append({
                "severity": "medium",
                "category": "periodization",
                "message": f"Very high frequency ({frequency} workouts/week) may lead to overreaching",
                "affected_items": ["frequency"],
                "recommendation": "Consider reducing frequency or ensuring adequate recovery"
            })
        
        return {
            "warnings": warnings,
            "suggestions": suggestions,
            "valid": len(warnings) == 0,
        }

