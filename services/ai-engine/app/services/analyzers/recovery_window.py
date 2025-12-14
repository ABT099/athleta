"""
Recovery Window Analyzer.

Detects insufficient rest between same muscle group training.
References: Schoenfeld, Krieger - Recovery time requirements.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import MuscleGroupModel
from app.utils.constants import (
    CNS_HEAVY_PATTERNS, CNS_MODERATE_PATTERNS,
    CNS_RECOVERY_HOURS_HEAVY, CNS_RECOVERY_HOURS_MODERATE,
    CNS_FATIGUE_PER_HEAVY_COMPOUND, CNS_FATIGUE_PER_MODERATE_COMPOUND,
    CNS_FATIGUE_RECOVERY_PER_REST_DAY, FOCUS_AREA_RECOVERY_BONUS,
    FocusArea
)


class RecoveryWindowAnalyzer:
    """
    Analyzes recovery windows between muscle group training sessions.
    
    Checks:
    - Local (muscular) recovery: Minimum 48-72 hours between same muscle group training
    - Systemic (CNS) recovery: CNS fatigue accumulation across heavy compound days
    - Rest day handling: Account for rest days in hour calculations
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        workout_days: List[Dict],
        frequency: int,
        focus_areas: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze recovery windows across workout days with focus-aware recovery requirements.
        
        Args:
            workout_days: List of workout day dicts with exercises and order_in_week
            frequency: Workouts per week
            focus_areas: Optional list of focus areas (e.g., ["chest", "back"])
            
        Returns:
            Dict with recovery window analysis (local and systemic)
        """
        # Expand focus areas to muscle groups
        focus_muscle_groups = self._expand_focus_areas(focus_areas or [])
        
        # Local (muscular) recovery analysis
        local_recovery = self._analyze_local_recovery(workout_days, frequency, focus_muscle_groups)
        
        # Systemic (CNS) recovery analysis
        systemic_recovery = self._analyze_systemic_recovery(workout_days, frequency)
        
        # Combine warnings
        all_warnings = local_recovery.get("warnings", []) + systemic_recovery.get("warnings", [])
        
        return {
            "local_recovery": local_recovery.get("muscle_recovery", {}),
            "systemic_recovery": systemic_recovery,
            "warnings": all_warnings,
        }
    
    def _analyze_local_recovery(
        self,
        workout_days: List[Dict],
        frequency: int,
        focus_muscle_groups: Optional[set] = None
    ) -> Dict:
        """
        Analyze local (muscular) recovery windows with focus-aware recovery requirements.
        
        Args:
            workout_days: List of workout day dicts
            frequency: Workouts per week
            focus_muscle_groups: Set of muscle groups that are focus areas
            
        Returns:
            Dict with local recovery analysis
        """
        focus_muscle_groups = focus_muscle_groups or set()
        
        # Map each muscle group to days it's trained
        muscle_to_days = self._map_muscles_to_days(workout_days)
        
        # Calculate actual hours between sessions (including rest days)
        actual_hours = self._calculate_actual_hours(workout_days, frequency)
        
        recovery_analysis = {}
        warnings = []
        
        for muscle_name, training_days in muscle_to_days.items():
            if len(training_days) < 2:
                continue  # Only trained once, no recovery issue
            
            # Get required recovery time for this muscle from database
            muscle = self.db.query(MuscleGroupModel).filter(
                MuscleGroupModel.name == muscle_name
            ).first()
            
            if muscle:
                required_hours = muscle.base_recovery_hours
            else:
                required_hours = 48  # Default fallback
            
            # Add recovery bonus for focus muscles
            if muscle_name in focus_muscle_groups:
                required_hours += FOCUS_AREA_RECOVERY_BONUS
                is_focus = True
            else:
                is_focus = False
            
            # Calculate hours between consecutive sessions using actual hours
            violations = []
            for i in range(len(training_days) - 1):
                day1 = training_days[i]
                day2 = training_days[i + 1]
                
                # Get actual hours between these days
                hours_between = actual_hours.get((day1, day2), 0)
                if hours_between == 0:
                    # Fallback to estimated hours
                    hours_between = (day2 - day1) * (24 * 7 / frequency)
                
                if hours_between < required_hours:
                    violations.append({
                        "day1": day1,
                        "day2": day2,
                        "hours_between": round(hours_between, 1),
                        "required_hours": required_hours,
                    })
            
            recovery_analysis[muscle_name] = {
                "training_days": training_days,
                "required_hours": required_hours,
                "violations": violations,
                "status": "sufficient" if not violations else "insufficient",
                "is_focus": is_focus,
            }
            
            # Generate warnings for violations
            for violation in violations:
                focus_note = " (focus muscle requires additional recovery)" if is_focus else ""
                warnings.append({
                    "severity": "high",
                    "category": "recovery",
                    "message": f"{muscle_name.replace('_', ' ').title()} trained on days {violation['day1']} and {violation['day2']} with only {violation['hours_between']:.0f}h rest (needs {violation['required_hours']}h){focus_note}",
                    "affected_items": [muscle_name],
                    "recommendation": f"Add at least {violation['required_hours'] - violation['hours_between']:.0f} more hours rest between {muscle_name} training sessions"
                })
        
        return {
            "muscle_recovery": recovery_analysis,
            "warnings": warnings,
        }
    
    def _analyze_systemic_recovery(self, workout_days: List[Dict], frequency: int) -> Dict:
        """
        Analyze systemic (CNS) recovery and fatigue accumulation.
        
        CNS fatigue is shared across all muscle groups and accumulates from
        heavy compound exercises (squats, deadlifts, heavy rows).
        
        Args:
            workout_days: List of workout day dicts
            frequency: Workouts per week
            
        Returns:
            Dict with systemic recovery analysis
        """
        # Identify days with CNS-demanding exercises
        cns_demand_by_day = {}
        cns_fatigue_accumulation = 0.0
        warnings = []
        
        for workout_day in workout_days:
            day_number = workout_day.get("order_in_week", 0)
            if day_number == 0:
                continue
            
            exercises = workout_day.get("exercises", [])
            day_cns_demand = 0.0
            
            for exercise in exercises:
                exercise_id = exercise.get("exercise_id")
                if not exercise_id:
                    continue
                
                # Get exercise from database
                from app.models import Exercise
                ex = self.db.query(Exercise).filter(Exercise.id == exercise_id).first()
                if not ex:
                    continue
                
                movement_pattern = (ex.movement_pattern or "").lower()
                
                # Get number of sets (use average of min/max if available, otherwise assume 3)
                sets_min = exercise.get("target_sets_min", 0)
                sets_max = exercise.get("target_sets_max", 0)
                if sets_max > 0:
                    num_sets = (sets_min + sets_max) / 2
                elif sets_min > 0:
                    num_sets = sets_min
                else:
                    num_sets = 3  # Default assumption for plan analysis
                
                # Check if exercise is CNS-demanding
                # CNS fatigue scales with volume (number of sets)
                if movement_pattern in CNS_HEAVY_PATTERNS:
                    day_cns_demand += CNS_FATIGUE_PER_HEAVY_COMPOUND * num_sets
                elif movement_pattern in CNS_MODERATE_PATTERNS:
                    day_cns_demand += CNS_FATIGUE_PER_MODERATE_COMPOUND * num_sets
            
            cns_demand_by_day[day_number] = day_cns_demand
            
            # Accumulate CNS fatigue
            cns_fatigue_accumulation += day_cns_demand
            
            # Check for back-to-back heavy CNS days
            if day_cns_demand > 0:
                # Check previous day
                prev_day = day_number - 1
                if prev_day in cns_demand_by_day and cns_demand_by_day[prev_day] > 0:
                    # Check if rest day exists between them
                    actual_hours = self._calculate_actual_hours(workout_days, frequency)
                    hours_between = actual_hours.get((prev_day, day_number), 0)
                    
                    if hours_between < CNS_RECOVERY_HOURS_HEAVY:
                        warnings.append({
                            "severity": "high",
                            "category": "recovery",
                            "message": f"CNS-demanding workouts on consecutive days (Day {prev_day} and Day {day_number}) without sufficient rest",
                            "affected_items": [f"Day {prev_day}", f"Day {day_number}"],
                            "recommendation": f"Add rest day between heavy compound sessions or ensure {CNS_RECOVERY_HOURS_HEAVY}h+ between sessions"
                        })
        
        # Check for excessive CNS fatigue accumulation
        if cns_fatigue_accumulation > 1.0:
            warnings.append({
                "severity": "medium",
                "category": "recovery",
                "message": f"High CNS fatigue accumulation ({cns_fatigue_accumulation:.1f}) across the week",
                "affected_items": ["plan_structure"],
                "recommendation": "Consider adding more rest days or reducing heavy compound frequency"
            })
        
        return {
            "cns_demand_by_day": cns_demand_by_day,
            "total_cns_fatigue": round(cns_fatigue_accumulation, 2),
            "warnings": warnings,
        }
    
    def _calculate_actual_hours(
        self,
        workout_days: List[Dict],
        frequency: int
    ) -> Dict[tuple, float]:
        """
        Calculate actual hours between workout days including rest days.
        
        Args:
            workout_days: List of workout day dicts with day_of_week or order_in_week
            frequency: Workouts per week
            
        Returns:
            Dict mapping (day1, day2) tuples to hours between
        """
        hours_map = {}
        
        # Get all workout day numbers sorted
        day_numbers = sorted([wd.get("order_in_week", 0) for wd in workout_days if wd.get("order_in_week", 0) > 0])
        
        # If we have day_of_week, use that for more accurate calculation
        has_day_of_week = any(wd.get("day_of_week") is not None for wd in workout_days)
        
        if has_day_of_week:
            # Use actual day_of_week for precise calculation
            day_to_weekday = {}
            for wd in workout_days:
                day_num = wd.get("order_in_week", 0)
                weekday = wd.get("day_of_week")
                if day_num > 0 and weekday is not None:
                    day_to_weekday[day_num] = weekday
            
            for i in range(len(day_numbers) - 1):
                day1 = day_numbers[i]
                day2 = day_numbers[i + 1]
                
                weekday1 = day_to_weekday.get(day1)
                weekday2 = day_to_weekday.get(day2)
                
                if weekday1 is not None and weekday2 is not None:
                    # Calculate actual days between (including weekends)
                    days_between = (weekday2 - weekday1) % 7
                    if days_between == 0:
                        days_between = 7  # Wrap around week
                    hours_map[(day1, day2)] = days_between * 24
                else:
                    # Fallback to estimated
                    hours_map[(day1, day2)] = (day2 - day1) * (24 * 7 / frequency)
        else:
            # Estimate based on order_in_week and frequency
            for i in range(len(day_numbers) - 1):
                day1 = day_numbers[i]
                day2 = day_numbers[i + 1]
                
                # Estimate: assume workouts are evenly spaced
                # If frequency is 3, workouts might be Mon/Wed/Fri (2 days between)
                days_between = (day2 - day1) * (7 / frequency)
                hours_map[(day1, day2)] = days_between * 24
        
        return hours_map
    
    def _map_muscles_to_days(self, workout_days: List[Dict]) -> Dict[str, List[int]]:
        """
        Map each muscle group to the days it's trained.
        
        Args:
            workout_days: List of workout day dicts
            
        Returns:
            Dict mapping muscle name to list of day numbers (order_in_week)
        """
        muscle_to_days = {}
        
        for workout_day in workout_days:
            day_number = workout_day.get("order_in_week", 0)
            if day_number == 0:
                continue
            
            exercises = workout_day.get("exercises", [])
            
            for exercise in exercises:
                exercise_id = exercise.get("exercise_id")
                if not exercise_id:
                    continue
                
                # Get muscle activations for this exercise via junction table
                from app.models import ExerciseMuscle
                
                # Get primary muscles (activation >= 70%)
                muscle_links = (
                    self.db.query(ExerciseMuscle, MuscleGroupModel)
                    .join(MuscleGroupModel, ExerciseMuscle.muscle_group_id == MuscleGroupModel.id)
                    .filter(
                        ExerciseMuscle.exercise_id == exercise_id,
                        ExerciseMuscle.activation_percent >= 70  # Primary targets
                    )
                    .all()
                )
                
                # Add primary muscles to the day
                for link, muscle in muscle_links:
                    muscle_name = muscle.name
                    if muscle_name not in muscle_to_days:
                        muscle_to_days[muscle_name] = []
                    if day_number not in muscle_to_days[muscle_name]:
                        muscle_to_days[muscle_name].append(day_number)
        
        # Sort day lists
        for muscle_name in muscle_to_days:
            muscle_to_days[muscle_name].sort()
        
        return muscle_to_days
    
    def _expand_focus_areas(self, focus_areas: List[str]) -> set:
        """
        Expand focus areas to muscle group names.
        
        Args:
            focus_areas: List of focus area strings (e.g., ["chest", "back"])
            
        Returns:
            Set of muscle group names
        """
        if not focus_areas:
            return set()
        
        # Map focus areas to muscle names
        focus_to_muscles = {
            "chest": {"upper_chest", "mid_chest", "lower_chest"},
            "back": {"lats", "upper_traps", "mid_back", "lower_traps"},
            "shoulders": {"anterior_delt", "lateral_delt", "posterior_delt"},
            "arms": {"biceps", "triceps", "forearms"},
            "legs": {"quadriceps", "hamstrings", "glutes", "hip_flexors", "calves"},
            "core": {"abs", "erector_spinae"},
        }
        
        muscle_groups = set()
        for focus_area_str in focus_areas:
            try:
                focus_area_lower = focus_area_str.lower()
                # Try as FocusArea enum
                try:
                    focus_area = FocusArea(focus_area_lower)
                    muscles = focus_to_muscles.get(focus_area.value, set())
                    muscle_groups.update(muscles)
                except ValueError:
                    # Maybe it's a direct muscle name
                    muscle_groups.add(focus_area_lower)
            except (ValueError, KeyError):
                continue
        
        return muscle_groups

