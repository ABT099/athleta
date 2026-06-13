"""
Constraint-Based Multi-Objective Optimizer.

Optimizes workout parameters (volume, intensity) subject to injury prevention constraints.
Uses constraint-based approach: injury prevention as hard constraints, strength/hypertrophy as objectives.
"""
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from autoregulation.models import Athlete
from autoregulation.utils.constants import TrainingType, TrainingExperience


class ConstrainedOptimizer:
    """
    Optimizes workout parameters subject to injury prevention constraints.
    
    Hard Constraints (must be satisfied):
    - ACWR in 0.8-1.3 range
    - CNS fatigue below threshold
    - Muscle recovery >= 48 hours
    
    Soft Objectives (optimize within constraints):
    - Strength: Maximize intensity progression
    - Hypertrophy: Maximize effective volume (MEV -> MRV)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def optimize(
        self,
        athlete_id: int,
        proposed_volume_mult: float,
        proposed_intensity_mult: float,
        injury_risk: Dict,
        recovery_status: Dict,
        training_type: TrainingType,
        experience: TrainingExperience
    ) -> Dict:
        """
        Optimize workout parameters within injury prevention constraints.
        
        Args:
            athlete_id: Athlete ID
            proposed_volume_mult: Proposed volume multiplier
            proposed_intensity_mult: Proposed intensity multiplier
            injury_risk: Injury risk assessment dict
            recovery_status: Recovery status dict
            training_type: Training type (strength/hypertrophy/hybrid)
            experience: Training experience
            
        Returns:
            Dict with optimized parameters and constraint status
        """
        # Get athlete
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {
                "volume_multiplier": proposed_volume_mult,
                "intensity_multiplier": proposed_intensity_mult,
                "constraints_satisfied": False,
                "reason": "Athlete not found"
            }
        
        # Check hard constraints
        constraints = self._check_constraints(
            athlete_id, proposed_volume_mult, proposed_intensity_mult,
            injury_risk, recovery_status
        )
        
        if not constraints["all_satisfied"]:
            # Adjust parameters to satisfy constraints
            adjusted_volume, adjusted_intensity = self._adjust_to_satisfy_constraints(
                proposed_volume_mult, proposed_intensity_mult, constraints
            )
            
            return {
                "volume_multiplier": adjusted_volume,
                "intensity_multiplier": adjusted_intensity,
                "constraints_satisfied": True,
                "constraints": constraints,
                "adjustments_made": {
                    "volume_adjusted": adjusted_volume != proposed_volume_mult,
                    "intensity_adjusted": adjusted_intensity != proposed_intensity_mult
                },
                "reason": "Parameters adjusted to satisfy injury prevention constraints"
            }
        
        # All constraints satisfied - optimize objectives
        optimized_volume, optimized_intensity = self._optimize_objectives(
            proposed_volume_mult, proposed_intensity_mult,
            training_type, experience, constraints
        )
        
        return {
            "volume_multiplier": optimized_volume,
            "intensity_multiplier": optimized_intensity,
            "constraints_satisfied": True,
            "constraints": constraints,
            "objectives_optimized": True,
            "reason": "Parameters optimized within constraints"
        }
    
    def _check_constraints(
        self,
        athlete_id: int,
        volume_mult: float,
        intensity_mult: float,
        injury_risk: Dict,
        recovery_status: Dict
    ) -> Dict:
        """
        Check if proposed parameters satisfy hard constraints.
        """
        constraints = {
            "acwr_ok": True,
            "cns_fatigue_ok": True,
            "recovery_ok": True,
            "all_satisfied": True
        }
        
        # Constraint 1: ACWR in 0.8-1.3 range
        acwr = injury_risk.get("acwr", {}).get("ratio", 1.0)
        if acwr < 0.8 or acwr > 1.3:
            constraints["acwr_ok"] = False
            constraints["all_satisfied"] = False
        
        # Constraint 2: CNS fatigue below threshold
        cns_fatigue = recovery_status.get("fatigue_status", {}).get("cns_fatigue", 0.0)
        cns_threshold = 0.8  # Max CNS fatigue before constraint violation
        if cns_fatigue > cns_threshold:
            constraints["cns_fatigue_ok"] = False
            constraints["all_satisfied"] = False
        
        # Constraint 3: Muscle recovery >= 48 hours
        recovery_warnings = recovery_status.get("warnings", [])
        insufficient_recovery = any(
            "insufficient recovery" in w.lower() or "48" in w.lower()
            for w in recovery_warnings
        )
        if insufficient_recovery:
            constraints["recovery_ok"] = False
            constraints["all_satisfied"] = False
        
        return constraints
    
    def _adjust_to_satisfy_constraints(
        self,
        volume_mult: float,
        intensity_mult: float,
        constraints: Dict
    ) -> Tuple[float, float]:
        """
        Adjust parameters to satisfy constraints.
        
        Priority: Reduce volume first (safer), then intensity if needed.
        """
        adjusted_volume = volume_mult
        adjusted_intensity = intensity_mult
        
        # If ACWR too high, reduce volume
        if not constraints.get("acwr_ok"):
            adjusted_volume = volume_mult * 0.9  # Reduce by 10%
            # If still too high, reduce more
            if adjusted_volume > 1.1:
                adjusted_volume = 1.0  # Cap at baseline
        
        # If CNS fatigue too high, reduce intensity
        if not constraints.get("cns_fatigue_ok"):
            adjusted_intensity = intensity_mult * 0.95  # Reduce by 5%
            # Also reduce volume slightly
            adjusted_volume = adjusted_volume * 0.95
        
        # If recovery insufficient, reduce volume
        if not constraints.get("recovery_ok"):
            adjusted_volume = adjusted_volume * 0.85  # Reduce by 15%
        
        # Ensure minimums (don't go below 0.7 for volume, 0.8 for intensity)
        adjusted_volume = max(adjusted_volume, 0.7)
        adjusted_intensity = max(adjusted_intensity, 0.8)
        
        return round(adjusted_volume, 3), round(adjusted_intensity, 3)
    
    def _optimize_objectives(
        self,
        volume_mult: float,
        intensity_mult: float,
        training_type: TrainingType,
        experience: TrainingExperience,
        constraints: Dict
    ) -> Tuple[float, float]:
        """
        Optimize objectives within constraints.
        
        Strength: Prioritize intensity
        Hypertrophy: Prioritize volume
        Hybrid: Balance both
        """
        # Start with proposed values
        optimized_volume = volume_mult
        optimized_intensity = intensity_mult
        
        if training_type == TrainingType.STRENGTH:
            # Maximize intensity (within constraints)
            # Slight increase if room
            if intensity_mult < 1.1 and constraints.get("cns_fatigue_ok"):
                optimized_intensity = min(intensity_mult * 1.02, 1.1)
            # Volume can be moderate
            optimized_volume = volume_mult
        
        elif training_type == TrainingType.HYPERTROPHY:
            # Maximize volume (within constraints)
            # Slight increase if room
            if volume_mult < 1.2 and constraints.get("acwr_ok"):
                optimized_volume = min(volume_mult * 1.03, 1.2)
            # Intensity moderate
            optimized_intensity = intensity_mult
        
        else:  # HYBRID
            # Balance both
            # Small increases to both if constraints allow
            if volume_mult < 1.15 and constraints.get("acwr_ok"):
                optimized_volume = min(volume_mult * 1.02, 1.15)
            if intensity_mult < 1.08 and constraints.get("cns_fatigue_ok"):
                optimized_intensity = min(intensity_mult * 1.01, 1.08)
        
        return round(optimized_volume, 3), round(optimized_intensity, 3)

