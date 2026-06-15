"""
Injury prevention API endpoints (joint-stress profile).

Joint stress is read from auto-regulation's OWN joint_stress_log (denormalised at
analyse time); the athlete is fetched from the api service.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_autoreg_db
from app.utils.helpers import get_athlete_or_404
from app.modules.injury.service import InjuryPreventionService
from app.utils.constants import TrainingExperience

router = APIRouter()


class JointStressProfileResponse(BaseModel):
    avoidJoints: List[str]
    reason: str


@router.get(
    "/injury-prevention/athlete/{athlete_id}/joint-stress-profile",
    response_model=JointStressProfileResponse,
)
def get_joint_stress_profile(
    athlete_id: int,
    db: Session = Depends(get_autoreg_db),
) -> JointStressProfileResponse:
    """
    Joint-stress profile from the local joint_stress_log, with experience-adjusted
    thresholds. Returns joints to avoid based on weighted stress over the past 7 days.
    """
    try:
        athlete = get_athlete_or_404(athlete_id)  # AthleteDTO (api)

        # Experience-adjusted thresholds (conservative 12 set-equiv/joint/week base)
        experience_multipliers = {
            TrainingExperience.BEGINNER: 1.0,
            TrainingExperience.INTERMEDIATE: 1.33,
            TrainingExperience.ADVANCED: 1.67,
        }
        BASE_THRESHOLD_SETS = 12.0
        threshold = BASE_THRESHOLD_SETS * experience_multipliers.get(
            athlete.training_experience, 1.0
        )

        joint_stress_scores = InjuryPreventionService(db).calculate_weighted_joint_stress(
            athlete_id, days_lookback=7
        )

        if not joint_stress_scores:
            return JointStressProfileResponse(
                avoidJoints=[],
                reason="Insufficient training data to assess joint stress",
            )

        # Average set stress units for normalization (75kg x 10 x 0.7 RPE x 0.5 risk)
        AVERAGE_SET_STRESS = 262.5

        avoid_joints = []
        joint_details = []
        for joint, stress_score in joint_stress_scores.items():
            set_equivalent = stress_score / AVERAGE_SET_STRESS
            if set_equivalent > threshold:
                avoid_joints.append(joint)
                joint_details.append(f"{joint} ({set_equivalent:.1f} set-equiv)")

        if avoid_joints:
            reason = (
                f"High stress on {len(avoid_joints)} joint(s) exceeding "
                f"{threshold:.0f}-set threshold ({athlete.training_experience.value} level): "
                f"{', '.join(joint_details)}"
            )
        else:
            max_stress = max(
                (stress / AVERAGE_SET_STRESS for stress in joint_stress_scores.values()),
                default=0,
            )
            reason = (
                f"Joint stress levels within safe ranges "
                f"(max: {max_stress:.1f} sets, threshold: {threshold:.0f} sets)"
            )

        return JointStressProfileResponse(avoidJoints=avoid_joints, reason=reason)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate joint stress profile: {str(e)}",
        )
