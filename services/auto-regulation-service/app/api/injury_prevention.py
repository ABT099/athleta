"""
Injury prevention API endpoints.

Scientific basis:
- Experience-adjusted thresholds based on progressive adaptation (Kraemer & Ratamess, 2004)
- Weighted stress calculation including intensity, volume-load, and injury risk
- Conservative baseline to prevent overuse injuries (Cook & Purdam, 2009)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime, timedelta, timezone
from autoregulation.database import get_db
from autoregulation.auth import get_current_user
from pydantic import BaseModel
from autoregulation.models import Athlete, WorkoutSession, ExerciseSet, Exercise
from autoregulation.utils.constants import TrainingExperience

router = APIRouter()


class JointStressProfileResponse(BaseModel):
    avoidJoints: List[str]
    reason: str


def calculate_weighted_joint_stress(
    athlete: Athlete,
    db: Session,
    days_lookback: int = 7
) -> Dict[str, float]:
    """
    Calculate weighted joint stress scores based on scientific principles.
    
    Stress Score = Volume-Load × RPE-Factor × Injury-Risk-Factor
    
    Where:
    - Volume-Load = weight × reps (mechanical work)
    - RPE-Factor = actual_rpe / 10 (intensity scaling)
    - Injury-Risk-Factor = exercise.injury_risk_level / 5 (exercise-specific risk)
    
    References:
    - González-Badillo & Sánchez-Medina (2010) - Volume-load quantification
    - Schoenfeld (2010) - Intensity and mechanical tension
    - Cook & Purdam (2009) - Joint-specific loading and pathology
    
    Args:
        athlete: Athlete model with training experience
        db: Database session
        days_lookback: Days to analyze (default 7)
        
    Returns:
        Dict mapping joint names to weighted stress scores
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
    
    # Query recent training sets with exercise data
    recent_sets = (
        db.query(ExerciseSet, Exercise)
        .join(WorkoutSession, ExerciseSet.workout_session_id == WorkoutSession.id)
        .join(Exercise, ExerciseSet.exercise_id == Exercise.id)
        .filter(
            WorkoutSession.athlete_id == athlete.id,
            WorkoutSession.session_date >= cutoff_date
        )
        .all()
    )
    
    joint_stress_scores: Dict[str, float] = {}
    
    for ex_set, exercise in recent_sets:
        if not exercise.joint_stress_areas:
            continue
        
        # Calculate volume-load (kg × reps)
        volume_load = (ex_set.weight or 0) * (ex_set.reps or 0)
        
        # Normalize RPE to 0-1 scale (higher RPE = higher stress)
        # Use target_rpe if actual not available, default to moderate (7.0)
        rpe = ex_set.actual_rpe or ex_set.target_rpe or 7.0
        rpe_factor = rpe / 10.0
        
        # Normalize injury risk level to 0-1 scale
        # injury_risk_level ranges from 1.0 (low) to 5.0 (very high)
        risk_factor = (exercise.injury_risk_level or 2.5) / 5.0
        
        # Calculate weighted stress score
        stress_score = volume_load * rpe_factor * risk_factor
        
        # Distribute stress across all joints involved in the exercise
        for joint in exercise.joint_stress_areas:
            joint_stress_scores[joint] = joint_stress_scores.get(joint, 0) + stress_score
    
    return joint_stress_scores


@router.get(
    "/injury-prevention/athlete/{athlete_id}/joint-stress-profile",
    response_model=JointStressProfileResponse
)
def get_joint_stress_profile(
    athlete_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> JointStressProfileResponse:
    """
    Get scientifically-validated joint stress profile for an athlete.
    
    Returns joints that should be avoided based on weighted stress accumulation
    over the past 7 days, adjusted for athlete training experience.
    
    Algorithm:
    1. Calculate weighted stress for each joint (volume-load × RPE × injury-risk)
    2. Normalize to set-equivalent units
    3. Compare against experience-adjusted thresholds
    4. Flag joints exceeding safe stress levels
    
    Experience-adjusted thresholds (conservative baseline = 12 sets/joint/week):
    - Beginner: 12 sets (1.0x multiplier)
    - Intermediate: 16 sets (1.33x multiplier)  
    - Advanced: 20 sets (1.67x multiplier)
    
    Scientific References:
    - Kraemer & Ratamess (2004) - Progressive adaptation and training experience
    - Gabbett (2016) - Workload monitoring and injury prevention
    - Cook & Purdam (2009) - Tendon pathology and loading management
    """
    try:
        # Get athlete with training experience
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        
        # Experience-adjusted thresholds based on progressive adaptation principle
        # Advanced athletes have greater tissue resilience and work capacity
        experience_multipliers = {
            TrainingExperience.BEGINNER: 1.0,      # 12 sets baseline
            TrainingExperience.INTERMEDIATE: 1.33, # 16 sets
            TrainingExperience.ADVANCED: 1.67      # 20 sets
        }
        
        # Conservative baseline: 12 set-equivalents per joint per week
        # Based on typical MRV (Maximum Recoverable Volume) for single joint
        BASE_THRESHOLD_SETS = 12.0
        threshold = BASE_THRESHOLD_SETS * experience_multipliers.get(
            athlete.training_experience,
            1.0
        )
        
        # Calculate weighted joint stress scores
        joint_stress_scores = calculate_weighted_joint_stress(athlete, db, days_lookback=7)
        
        if not joint_stress_scores:
            return JointStressProfileResponse(
                avoidJoints=[],
                reason="Insufficient training data to assess joint stress"
            )
        
        # Average set stress units for normalization
        # Typical set: 75kg × 10 reps × 0.7 RPE × 0.5 risk = 262.5 stress units
        AVERAGE_SET_STRESS = 262.5
        
        # Identify joints exceeding threshold
        avoid_joints = []
        joint_details = []
        
        for joint, stress_score in joint_stress_scores.items():
            # Convert stress score to set-equivalent
            set_equivalent = stress_score / AVERAGE_SET_STRESS
            
            if set_equivalent > threshold:
                avoid_joints.append(joint)
                joint_details.append(f"{joint} ({set_equivalent:.1f} set-equiv)")
        
        # Generate detailed reason message
        if avoid_joints:
            experience_level = athlete.training_experience.value
            reason = (
                f"High stress on {len(avoid_joints)} joint(s) exceeding "
                f"{threshold:.0f}-set threshold ({experience_level} level): "
                f"{', '.join(joint_details)}"
            )
        else:
            max_stress = max(
                (stress / AVERAGE_SET_STRESS for stress in joint_stress_scores.values()),
                default=0
            )
            reason = (
                f"Joint stress levels within safe ranges "
                f"(max: {max_stress:.1f} sets, threshold: {threshold:.0f} sets)"
            )
        
        return JointStressProfileResponse(
            avoidJoints=avoid_joints,
            reason=reason
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate joint stress profile: {str(e)}"
        )

