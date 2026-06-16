"""
Injury prevention and risk assessment (auto-regulation-owned).

All risk signals are read from auto-regulation's OWN denormalised algo tables:
  * volume spike / ACWR / monotony  → performance_trends (per-session load)
  * joint stress                    → joint_stress_log (per-session per-joint)
  * form degradation                → form_quality_trends (via FormQualityService)

The current session + athlete come from the Analysis Context; exercise metadata
(safety, joints) is resolved over gRPC from exercise-service. No api-owned
sessions/sets are read.
"""
from typing import Dict, List
from datetime import datetime, timedelta, timezone

from app.models import PerformanceTrend, JointStressLog
from app.modules.analysis import AnalysisContext
from app.clients.exercise_client import ExerciseClient
from app.grpc_gen.exercise.v1 import exercise_pb2 as exercise_pb
from app.shared.calculations import TrainingCalculations
from app.modules.form import FormQualityService
from app.utils.constants import TrainingExperience, PROGRESSION_RATES


class InjuryPreventionService:
    """Monitors training for injury risk factors using local denormalised signals."""

    def __init__(self, db):
        self.db = db
        self.calc = TrainingCalculations()
        self.form_service = FormQualityService(db)

    # --- exercise-service helpers ---------------------------------------------
    def _get_exercises_map(self, exercise_ids) -> Dict[int, "exercise_pb.Exercise"]:
        ids = list({eid for eid in exercise_ids if eid})
        if not ids:
            return {}
        with ExerciseClient() as client:
            return {ex.id: ex for ex in client.get_exercises(ids)}

    def _get_exercise(self, exercise_id: int):
        return self._get_exercises_map([exercise_id]).get(exercise_id)

    def _get_exercise_name(self, exercise_id: int) -> str:
        exercise = self._get_exercise(exercise_id)
        return exercise.name if exercise else f"Exercise {exercise_id}"

    def _recent_trends(self, athlete_id: int, days: int) -> List[PerformanceTrend]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.db.query(PerformanceTrend)
            .filter(
                PerformanceTrend.athlete_id == athlete_id,
                PerformanceTrend.session_date >= cutoff,
            )
            .order_by(PerformanceTrend.session_date)
            .all()
        )

    # --- top-level check -------------------------------------------------------
    def check_all_injury_risks(
        self,
        ctx: AnalysisContext,
        proposed_workout_volume: float,
    ) -> Dict:
        """Comprehensive injury risk check over the context + local history."""
        athlete_id = ctx.athlete_id
        experience = ctx.athlete.training_experience
        proposed_exercises = ctx.exercise_ids

        warnings = []
        risk_level = "low"

        volume_check = self.check_volume_spike(athlete_id, experience, proposed_workout_volume)
        if volume_check["is_spike"]:
            warnings.append(volume_check["warning"])
            risk_level = "moderate" if risk_level == "low" else "high"

        acwr_check = self.check_acwr(athlete_id)
        if acwr_check["risk_level"] != "low":
            warnings.append(acwr_check["warning"])
            if acwr_check["risk_level"] == "high":
                risk_level = "high"

        monotony_check = self.check_training_monotony(athlete_id)
        if monotony_check["is_high"]:
            warnings.append(monotony_check["warning"])
            risk_level = "moderate" if risk_level == "low" else risk_level

        joint_check = self.check_joint_stress(athlete_id, experience, proposed_exercises)
        if joint_check["warnings"]:
            warnings.extend(joint_check["warnings"])
            risk_level = "high" if joint_check["high_risk"] else risk_level

        form_check = self.check_form_degradation(athlete_id)
        if form_check["warnings"]:
            warnings.extend(form_check["warnings"])
            risk_level = "moderate" if risk_level == "low" else risk_level

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "volume_status": volume_check,
            "acwr_status": acwr_check,
            "monotony_status": monotony_check,
            "joint_stress_status": joint_check,
            "form_status": form_check,
            "recommendations": self._generate_injury_prevention_recommendations(risk_level, warnings),
        }

    # --- volume spike (local trends) ------------------------------------------
    def check_volume_spike(
        self,
        athlete_id: int,
        experience: TrainingExperience,
        proposed_volume: float,
        weeks_to_compare: int = 4,
    ) -> Dict:
        """10% rule: weekly volume shouldn't jump beyond the experience-based cap."""
        progression_data = PROGRESSION_RATES.get(experience)
        max_increase = progression_data["max_weekly_volume_increase"]

        trends = self._recent_trends(athlete_id, days=weeks_to_compare * 7)
        if not trends:
            return {"is_spike": False, "warning": None, "average_volume": 0}

        total_volume = sum(t.total_volume or 0 for t in trends)
        oldest = trends[0].session_date
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        weeks_elapsed = min(weeks_to_compare, (datetime.now(timezone.utc) - oldest).days / 7)
        avg_weekly_volume = total_volume / max(weeks_elapsed, 1)

        if avg_weekly_volume == 0:
            return {"is_spike": False, "warning": None, "average_volume": 0}

        volume_increase = (proposed_volume - avg_weekly_volume) / avg_weekly_volume
        is_spike = volume_increase > max_increase

        warning = None
        if is_spike:
            warning = (
                f"Volume spike detected: {volume_increase*100:.1f}% increase. "
                f"Recommended max: {max_increase*100:.0f}%. "
                f"Consider reducing volume to {avg_weekly_volume * (1 + max_increase):.0f}kg."
            )

        return {
            "is_spike": is_spike,
            "volume_increase_percent": round(volume_increase * 100, 1),
            "max_recommended_percent": max_increase * 100,
            "average_volume": round(avg_weekly_volume, 1),
            "proposed_volume": proposed_volume,
            "warning": warning,
        }

    # --- ACWR (local trends) ---------------------------------------------------
    def check_acwr(self, athlete_id: int) -> Dict:
        """ACWR = acute (7d) / chronic (28d) load, from local performance trends."""
        acute = self._recent_trends(athlete_id, days=7)
        chronic = self._recent_trends(athlete_id, days=28)

        if not chronic:
            return {"acwr": 0.0, "risk_level": "low", "warning": None}

        def _loads(trends):
            loads = []
            for t in trends:
                load = 0
                if t.total_volume and t.average_rpe:
                    load = (t.total_volume / 1000) * t.average_rpe
                loads.append(load)
            return loads

        acute_loads = _loads(acute)
        chronic_loads = _loads(chronic)
        acwr = self.calc.calculate_acute_chronic_workload_ratio(acute_loads, chronic_loads)

        if 0.8 <= acwr <= 1.3:
            risk_level, warning = "low", None
        elif 1.3 < acwr <= 1.5:
            risk_level = "moderate"
            warning = f"ACWR slightly elevated at {acwr:.2f}. Monitor for overtraining signs."
        elif acwr > 1.5:
            risk_level = "high"
            warning = (
                f"ACWR dangerously high at {acwr:.2f}. "
                f"Significant injury risk - reduce training volume immediately."
            )
        elif 0.5 <= acwr < 0.8:
            risk_level = "moderate"
            warning = f"ACWR low at {acwr:.2f}. Undertraining may lead to deconditioning."
        else:
            risk_level, warning = "low", None

        return {
            "acwr": round(acwr, 2),
            "risk_level": risk_level,
            "warning": warning,
            "acute_load": round(sum(acute_loads), 1),
            "chronic_load": round(sum(chronic_loads), 1),
        }

    # --- monotony (local trends) ----------------------------------------------
    def check_training_monotony(self, athlete_id: int, days: int = 14) -> Dict:
        """High monotony (>2.0) with high volume increases injury risk."""
        trends = self._recent_trends(athlete_id, days=days)
        if len(trends) < 3:
            return {"is_high": False, "monotony": 0.0, "warning": None}

        daily_loads = []
        for t in trends:
            if t.total_volume and t.average_rpe:
                daily_loads.append((t.total_volume / 1000) * t.average_rpe)
            elif t.average_rpe:
                daily_loads.append(t.average_rpe)
            else:
                daily_loads.append(0)

        monotony = self.calc.calculate_training_monotony(daily_loads)
        is_high = monotony > 2.0
        warning = None
        if is_high:
            warning = (
                f"Training monotony high ({monotony:.2f}). "
                f"Add variety to training: different exercises, rep ranges, or intensities."
            )
        return {
            "is_high": is_high,
            "monotony": round(monotony, 2),
            "warning": warning,
            "recommendation": "Incorporate more variation in training" if is_high else None,
        }

    # --- joint stress (local joint_stress_log) --------------------------------
    def log_session_joint_stress(self, ctx: AnalysisContext) -> List[JointStressLog]:
        """
        Compute and persist this session's weighted per-joint stress into the local
        joint_stress_log: stress = volume-load x RPE-factor x injury-risk-factor,
        distributed across each exercise's stressed joints. Returns created rows.
        """
        sets = ctx.sets
        if not sets:
            return []

        sets_by_exercise: Dict[int, list] = {}
        for s in sets:
            sets_by_exercise.setdefault(s.exercise_id, []).append(s)
        exercises = self._get_exercises_map(sets_by_exercise.keys())

        joint_scores: Dict[str, float] = {}
        for ex_id, ex_sets in sets_by_exercise.items():
            exercise = exercises.get(ex_id)
            if not exercise or not exercise.safety.joint_stress_areas:
                continue
            for s in ex_sets:
                volume_load = (s.weight or 0) * (s.reps or 0)
                rpe = s.rpe or 7.0
                rpe_factor = rpe / 10.0
                risk_factor = (exercise.safety.injury_risk_level or 2.5) / 5.0
                stress_score = volume_load * rpe_factor * risk_factor
                for joint in exercise.safety.joint_stress_areas:
                    joint_scores[joint] = joint_scores.get(joint, 0) + stress_score

        rows = []
        for joint_name, score in joint_scores.items():
            row = JointStressLog(
                athlete_id=ctx.athlete_id,
                workout_session_id=ctx.session.id,
                session_date=ctx.session.session_date,
                joint_name=joint_name,
                stress_score=score,
            )
            self.db.add(row)
            rows.append(row)
        return rows

    def calculate_weighted_joint_stress(
        self,
        athlete_id: int,
        days_lookback: int = 7,
    ) -> Dict[str, float]:
        """Weighted joint-stress scores over a window, summed from joint_stress_log."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        rows = (
            self.db.query(JointStressLog)
            .filter(
                JointStressLog.athlete_id == athlete_id,
                JointStressLog.session_date >= cutoff_date,
            )
            .all()
        )
        scores: Dict[str, float] = {}
        for r in rows:
            scores[r.joint_name] = scores.get(r.joint_name, 0) + r.stress_score
        return scores

    def check_joint_stress(
        self,
        athlete_id: int,
        experience: TrainingExperience,
        proposed_exercise_ids: List[int],
        days_lookback: int = 7,
    ) -> Dict:
        """Check joint-stress accumulation against the proposed exercises' joints."""
        warnings = []
        high_risk = False

        proposed_exercises = list(self._get_exercises_map(proposed_exercise_ids).values())

        high_risk_exercises = [
            ex for ex in proposed_exercises if ex.safety.injury_risk_level >= 2.5
        ]
        if len(high_risk_exercises) > 3:
            warnings.append(
                f"Workout contains {len(high_risk_exercises)} high-risk exercises. "
                f"Consider substituting some with lower-risk alternatives."
            )
            high_risk = True

        joint_stress_scores = self.calculate_weighted_joint_stress(athlete_id, days_lookback)

        # Convert to set-equivalents (avg set ~ 262.5 stress units)
        AVERAGE_SET_STRESS = 262.5
        joint_stress_count = {
            joint: int(score / AVERAGE_SET_STRESS) for joint, score in joint_stress_scores.items()
        }

        experience_multipliers = {
            TrainingExperience.BEGINNER: 1.0,
            TrainingExperience.INTERMEDIATE: 1.33,
            TrainingExperience.ADVANCED: 1.67,
        }
        warning_threshold = 15 * experience_multipliers.get(experience, 1.0)

        for exercise in proposed_exercises:
            if exercise.safety.joint_stress_areas:
                for joint in exercise.safety.joint_stress_areas:
                    current_count = joint_stress_count.get(joint, 0)
                    if current_count > warning_threshold:
                        warnings.append(
                            f"High {joint} stress detected ({current_count} set-equiv this week). "
                            f"Exercise '{exercise.name}' may increase injury risk."
                        )
                        high_risk = True

        return {
            "warnings": warnings,
            "high_risk": high_risk,
            "high_risk_exercise_count": len(high_risk_exercises),
            "joint_stress_distribution": joint_stress_count,
            "joint_stress_scores": joint_stress_scores,
        }

    # --- form degradation (local form trends) ---------------------------------
    def check_form_degradation(self, athlete_id: int, days_lookback: int = 14) -> Dict:
        """
        Surface form-degradation risk from the local form_quality_trends (via
        FormQualityService alerts + chronic-issue detection).
        """
        alerts = self.form_service.generate_form_alerts(athlete_id, days_lookback=days_lookback)
        chronic_issues = self.form_service.detect_chronic_form_issues(athlete_id, days_lookback=days_lookback)

        warnings = [
            a["message"] for a in alerts
            if a.get("severity") in ("WARNING", "CRITICAL", "CAUTION")
        ]

        return {
            "warnings": warnings,
            "alert_count": len(alerts),
            "high_risk_sets": sum(1 for a in alerts if a.get("type") == "high_rpe_poor_form"),
            "chronic_issues": chronic_issues,
        }

    def _generate_injury_prevention_recommendations(
        self,
        risk_level: str,
        warnings: List[str],
    ) -> List[str]:
        """Generate actionable injury-prevention recommendations."""
        recommendations = []
        if risk_level == "high":
            recommendations.append("URGENT: Implement deload week immediately (50% volume, 90% intensity)")
            recommendations.append("Consult with a healthcare professional if experiencing pain")
            recommendations.append("Focus on mobility, recovery, and technique work")
        elif risk_level == "moderate":
            recommendations.append("Reduce training volume by 20-30% for next 1-2 weeks")
            recommendations.append("Increase attention to warm-up and mobility work")
            recommendations.append("Monitor for any pain or discomfort closely")
        else:
            recommendations.append("Continue current training approach")
            recommendations.append("Maintain proper warm-up and recovery practices")

        if any("monotony" in w.lower() for w in warnings):
            recommendations.append("Add exercise variation: try different grips, angles, or rep ranges")
        if any("form" in w.lower() for w in warnings):
            recommendations.append("Include technique-focused sessions with lighter loads (50-60% 1RM)")
            recommendations.append("Consider working with a coach for form assessment")

        return recommendations
