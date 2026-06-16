"""
Form quality tracking and analysis service.

Provides comprehensive form quality analysis including:
- Quantitative form scoring
- Within-session form degradation tracking
- Historical trend analysis
- Chronic form issue detection
- Alert generation
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models import FormQualityTrend  # algo-owned, local
from app.modules.analysis import AnalysisContext
from app.clients.exercise_client import ExerciseClient
from app.utils.constants import (
    FORM_SCORE_EXCELLENT, FORM_SCORE_GOOD, FORM_SCORE_FAIR, FORM_SCORE_POOR,
    FORM_DEGRADATION_THRESHOLD, FORM_CHRONIC_ISSUE_THRESHOLD,
    FORM_MIN_SCORE_FOR_PROGRESSION
)


class FormQualityService:
    """
    Service for tracking and analyzing form quality.
    """
    
    # Form quality to score mapping
    FORM_SCORES = {
        "excellent": FORM_SCORE_EXCELLENT,
        "good": FORM_SCORE_GOOD,
        "fair": FORM_SCORE_FAIR,
        "poor": FORM_SCORE_POOR
    }
    
    def __init__(self, db: Session):
        self.db = db

    def _get_exercise_names(self, exercise_ids) -> Dict[int, str]:
        """Return {exercise_id: name} for known ids from exercise-service."""
        ids = list({eid for eid in exercise_ids if eid})
        if not ids:
            return {}
        with ExerciseClient() as client:
            exercises = client.get_exercises(ids)
        return {ex.id: ex.name for ex in exercises}

    def _get_exercise_name(self, exercise_id: int) -> str:
        """Return the exercise name, or an 'Exercise {id}' fallback."""
        names = self._get_exercise_names([exercise_id])
        return names.get(exercise_id, f"Exercise {exercise_id}")

    @staticmethod
    def calculate_form_score(form_quality: Optional[str]) -> float:
        """
        Convert qualitative form quality to quantitative score.
        
        Args:
            form_quality: Form quality string ("excellent", "good", "fair", "poor")
            
        Returns:
            Form score (1.0 = excellent, 0.75 = good, 0.5 = fair, 0.25 = poor)
            Returns 0.75 (good) as default if None or invalid
        """
        if not form_quality:
            return FORM_SCORE_GOOD  # Default to "good" if not specified
        
        return FormQualityService.FORM_SCORES.get(
            form_quality.lower(), 
            FORM_SCORE_GOOD  # Default to "good" for invalid values
        )
    
    def _degradation_rate(self, sets) -> Optional[float]:
        """
        Form degradation within a session for one exercise: average form score of
        the first half of sets minus the second half (positive = degraded). ``sets``
        are the session's ExerciseSetDTOs for one exercise.
        """
        scored = [s for s in sorted(sets, key=lambda s: s.set_number) if s.form_quality is not None]
        if len(scored) < 2:
            return None
        midpoint = len(scored) // 2
        first = [self.calculate_form_score(s.form_quality) for s in scored[:midpoint]]
        second = [self.calculate_form_score(s.form_quality) for s in scored[midpoint:]]
        if not first or not second:
            return None
        return round(sum(first) / len(first) - sum(second) / len(second), 3)

    def track_session_form_quality(self, ctx: AnalysisContext) -> Dict[int, Dict]:
        """
        Track form quality for all exercises in the completed session (from the
        context). Returns a dict mapping exercise_id to form-quality metrics.
        """
        sets = [s for s in ctx.sets if s.form_quality is not None]
        if not sets:
            return {}

        by_exercise: Dict[int, list] = {}
        for s in sets:
            by_exercise.setdefault(s.exercise_id, []).append(s)

        return {
            ex_id: self._calculate_exercise_metrics(ex_id, ex_sets)
            for ex_id, ex_sets in by_exercise.items()
        }

    def _calculate_exercise_metrics(self, exercise_id: int, sets) -> Dict:
        """Calculate form quality metrics for an exercise in a session (DTO sets)."""
        form_scores = [self.calculate_form_score(s.form_quality) for s in sets]
        average_score = sum(form_scores) / len(form_scores)

        from app.utils.constants import HIGH_RPE_THRESHOLD
        high_rpe_poor_form = sum(
            1 for s in sets
            if s.rpe and s.rpe >= HIGH_RPE_THRESHOLD
            and s.form_quality in ["poor", "fair"]
        )

        return {
            "average_form_score": round(average_score, 3),
            "sets_analyzed": len(sets),
            "degradation_rate": self._degradation_rate(sets),
            "high_rpe_poor_form_count": high_rpe_poor_form
        }
    
    def save_form_quality_trend(
        self,
        athlete_id: int,
        exercise_id: int,
        date: datetime,
        average_form_score: float,
        sets_analyzed: int,
        degradation_rate: Optional[float] = None,
        high_rpe_poor_form_count: int = 0
    ) -> FormQualityTrend:
        """
        Save form quality trend data for an exercise on a specific date.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            date: Date of the workout
            average_form_score: Average form score for the exercise
            sets_analyzed: Number of sets analyzed
            degradation_rate: Form degradation rate within session
            high_rpe_poor_form_count: Count of high RPE + poor form sets
            
        Returns:
            Created FormQualityTrend instance
        """
        trend = FormQualityTrend(
            athlete_id=athlete_id,
            exercise_id=exercise_id,
            date=date,
            average_form_score=average_form_score,
            sets_analyzed=sets_analyzed,
            degradation_rate=degradation_rate,
            high_rpe_poor_form_count=high_rpe_poor_form_count
        )
        
        self.db.add(trend)
        self.db.flush()
        
        return trend
    
    def get_form_quality_trend(
        self,
        athlete_id: int,
        exercise_id: int,
        days_lookback: int = 14
    ) -> Dict:
        """
        Get historical form quality trend for an exercise.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            days_lookback: Number of days to look back
            
        Returns:
            Dict with trend data including average score, trend direction, etc.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        trends = (
            self.db.query(FormQualityTrend)
            .filter(
                FormQualityTrend.athlete_id == athlete_id,
                FormQualityTrend.exercise_id == exercise_id,
                FormQualityTrend.date >= cutoff_date
            )
            .order_by(FormQualityTrend.date.desc())
            .all()
        )
        
        if not trends:
            return {
                "has_data": False,
                "average_score": None,
                "trend_direction": None,
                "session_count": 0
            }
        
        scores = [t.average_form_score for t in trends]
        avg_score = sum(scores) / len(scores)
        
        # Determine trend direction (comparing first half to second half)
        if len(scores) >= 2:
            midpoint = len(scores) // 2
            recent_avg = sum(scores[:midpoint]) / midpoint
            older_avg = sum(scores[midpoint:]) / len(scores[midpoint:])
            
            if recent_avg > older_avg + 0.05:
                trend_direction = "improving"
            elif recent_avg < older_avg - 0.05:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "insufficient_data"
        
        return {
            "has_data": True,
            "average_score": round(avg_score, 3),
            "trend_direction": trend_direction,
            "session_count": len(trends),
            "latest_score": round(scores[0], 3) if scores else None
        }
    
    def detect_chronic_form_issues(
        self,
        athlete_id: int,
        exercise_id: Optional[int] = None,
        days_lookback: int = 14
    ) -> Dict:
        """
        Detect chronic form issues across multiple sessions.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Optional exercise ID (if None, checks all exercises)
            days_lookback: Number of days to analyze
            
        Returns:
            Dict with detected issues and recommendations
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        query = (
            self.db.query(FormQualityTrend)
            .filter(
                FormQualityTrend.athlete_id == athlete_id,
                FormQualityTrend.date >= cutoff_date
            )
        )
        
        if exercise_id:
            query = query.filter(FormQualityTrend.exercise_id == exercise_id)
        
        trends = query.order_by(FormQualityTrend.date.desc()).all()
        
        if not trends:
            return {
                "has_issues": False,
                "issues": [],
                "affected_exercises": []
            }
        
        # Group by exercise
        exercise_issues = {}
        for trend in trends:
            if trend.exercise_id not in exercise_issues:
                exercise_issues[trend.exercise_id] = []
            exercise_issues[trend.exercise_id].append(trend)
        
        issues = []
        affected_exercises = []
        exercise_names = self._get_exercise_names(exercise_issues.keys())

        for ex_id, ex_trends in exercise_issues.items():
            # Check if >40% of sets are fair/poor
            total_sets = sum(t.sets_analyzed for t in ex_trends)
            poor_form_sets = sum(
                t.sets_analyzed for t in ex_trends
                if t.average_form_score < FORM_MIN_SCORE_FOR_PROGRESSION  # Below "good"
            )

            if total_sets > 0:
                poor_percentage = (poor_form_sets / total_sets) * 100

                if poor_percentage >= FORM_CHRONIC_ISSUE_THRESHOLD * 100:
                    exercise_name = exercise_names.get(ex_id, f"Exercise {ex_id}")
                    
                    issues.append({
                        "exercise_id": ex_id,
                        "exercise_name": exercise_name,
                        "poor_form_percentage": round(poor_percentage, 1),
                        "sessions_affected": len(ex_trends),
                        "recommendation": "Reduce loads and focus on technique. Consider deload."
                    })
                    affected_exercises.append(ex_id)
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "affected_exercises": affected_exercises
        }
    
    def generate_form_alerts(
        self,
        athlete_id: int,
        exercise_id: Optional[int] = None,
        days_lookback: int = 14
    ) -> List[Dict]:
        """
        Generate form quality alerts based on various triggers.
        
        Alert triggers:
        - Form degradation >20% within a session
        - 3+ consecutive sessions with avg form score < 0.6
        - High RPE (9+) combined with poor form on any set
        - Exercise-specific chronic form issues (>40% of sets fair/poor over 2 weeks)
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Optional exercise ID (if None, checks all exercises)
            days_lookback: Number of days to analyze
            
        Returns:
            List of alert dicts with severity and message
        """
        alerts = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Get recent trends
        query = (
            self.db.query(FormQualityTrend)
            .filter(
                FormQualityTrend.athlete_id == athlete_id,
                FormQualityTrend.date >= cutoff_date
            )
        )
        
        if exercise_id:
            query = query.filter(FormQualityTrend.exercise_id == exercise_id)
        
        trends = query.order_by(FormQualityTrend.date.desc()).all()
        
        if not trends:
            return alerts
        
        # Group by exercise
        exercise_trends = {}
        for trend in trends:
            if trend.exercise_id not in exercise_trends:
                exercise_trends[trend.exercise_id] = []
            exercise_trends[trend.exercise_id].append(trend)
        
        exercise_names = self._get_exercise_names(exercise_trends.keys())
        for ex_id, ex_trends in exercise_trends.items():
            exercise_name = exercise_names.get(ex_id, f"Exercise {ex_id}")

            # Check for within-session degradation >20%
            for trend in ex_trends:
                if trend.degradation_rate and trend.degradation_rate >= FORM_DEGRADATION_THRESHOLD:
                    alerts.append({
                        "severity": "WARNING",
                        "type": "within_session_degradation",
                        "exercise_id": ex_id,
                        "exercise_name": exercise_name,
                        "message": (
                            f"Form degrading during {exercise_name}: "
                            f"{trend.degradation_rate*100:.1f}% drop from first to last sets. "
                            f"Watch technique and consider reducing volume."
                        ),
                        "date": trend.date
                    })
            
            # Check for consecutive poor form sessions
            consecutive_poor = 0
            for trend in sorted(ex_trends, key=lambda t: t.date, reverse=True):
                if trend.average_form_score < FORM_MIN_SCORE_FOR_PROGRESSION:
                    consecutive_poor += 1
                else:
                    break
            
            if consecutive_poor >= 3:
                alerts.append({
                    "severity": "CAUTION",
                    "type": "consecutive_poor_form",
                    "exercise_id": ex_id,
                    "exercise_name": exercise_name,
                    "message": (
                        f"{consecutive_poor} consecutive sessions with poor form on {exercise_name}. "
                        f"Load reduction recommended."
                    ),
                    "sessions_affected": consecutive_poor
                })
            
            # Check for high RPE + poor form combinations
            total_high_risk = sum(t.high_rpe_poor_form_count for t in ex_trends)
            if total_high_risk > 0:
                alerts.append({
                    "severity": "CRITICAL",
                    "type": "high_rpe_poor_form",
                    "exercise_id": ex_id,
                    "exercise_name": exercise_name,
                    "message": (
                        f"{total_high_risk} sets with poor form at RPE 9+ on {exercise_name}. "
                        f"This combination significantly increases injury risk. "
                        f"Reduce intensity immediately."
                    ),
                    "high_risk_sets": total_high_risk
                })
        
        # Check for chronic issues
        chronic_issues = self.detect_chronic_form_issues(
            athlete_id, exercise_id, days_lookback
        )
        
        if chronic_issues["has_issues"]:
            for issue in chronic_issues["issues"]:
                alerts.append({
                    "severity": "CAUTION",
                    "type": "chronic_form_issue",
                    "exercise_id": issue["exercise_id"],
                    "exercise_name": issue["exercise_name"],
                    "message": (
                        f"Chronic form issues on {issue['exercise_name']}: "
                        f"{issue['poor_form_percentage']:.1f}% of sets rated fair/poor over "
                        f"{days_lookback} days. {issue['recommendation']}"
                    ),
                    "poor_form_percentage": issue["poor_form_percentage"]
                })
        
        return alerts
    
    def should_block_progression(
        self,
        athlete_id: int,
        exercise_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if form quality should block progression for an exercise.
        
        Args:
            athlete_id: Athlete ID
            exercise_id: Exercise ID
            
        Returns:
            Tuple of (should_block, reason)
        """
        trend = self.get_form_quality_trend(athlete_id, exercise_id, days_lookback=14)
        
        if not trend["has_data"]:
            return False, None
        
        # Block if average score is below minimum threshold
        if trend["average_score"] and trend["average_score"] < FORM_MIN_SCORE_FOR_PROGRESSION:
            exercise_name = self._get_exercise_name(exercise_id)
            
            return True, (
                f"Form quality below target on {exercise_name} "
                f"(score: {trend['average_score']:.2f}). "
                f"Maintain loads and focus on technique before progressing."
            )
        
        # Check for degrading trend (stricter check - any sign of degradation)
        if trend["trend_direction"] == "degrading" or (
            trend["average_score"] and trend["average_score"] < FORM_MIN_SCORE_FOR_PROGRESSION + 0.1
        ):
            exercise_name = self._get_exercise_name(exercise_id)
            
            if trend["trend_direction"] == "degrading":
                return True, (
                    f"Form quality degrading on {exercise_name}. "
                    f"Hold progression until form improves."
                )
            else:
                return True, (
                    f"Form quality marginal on {exercise_name} "
                    f"(score: {trend['average_score']:.2f}). "
                    f"Hold progression and focus on technique."
                )
        
        return False, None

