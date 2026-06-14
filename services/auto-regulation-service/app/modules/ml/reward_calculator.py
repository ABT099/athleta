"""
Reward calculator for ML training targets.

Computes hybrid reward signal based on workout outcomes:
- RPE Accuracy (40%): How close was predicted RPE to actual?
- Volume Progression (30%): Did volume increase appropriately?
- Injury Avoidance (30%): No injury flags or forced deloads
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    PerformanceTrend, WorkoutSession, PlanEntry, RecoveryMetrics
)
from app.models.workout import WorkoutPlan


class RewardCalculator:
    """
    Calculates reward signal for workout adjustments.
    
    Reward is computed based on outcomes in subsequent sessions.
    """
    
    def __init__(self, db: Session):
        """
        Initialize reward calculator.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def calculate_adjustment_reward(
        self,
        athlete_id: int,
        session_id: int,
        volume_mult_used: float,
        intensity_mult_used: float,
        lookahead_sessions: int = 2
    ) -> float:
        """
        Calculate reward for adjustments used in a session.
        
        Looks at outcomes in next N sessions to determine if adjustments were good.
        
        Args:
            athlete_id: Athlete ID
            session_id: Session ID where adjustments were used
            volume_mult_used: Volume multiplier that was applied
            intensity_mult_used: Intensity multiplier that was applied
            lookahead_sessions: Number of future sessions to consider (default: 2)
            
        Returns:
            Reward score (0.0 - 1.0)
        """
        # Get the session
        session = self.db.query(WorkoutSession).filter(
            WorkoutSession.id == session_id
        ).first()
        
        if not session:
            return 0.5  # Default neutral reward
        
        # Get performance trend for this session
        current_trend = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.workout_session_id == session_id
        ).first()
        
        if not current_trend:
            return 0.5  # Default neutral reward
        
        # Get subsequent sessions to evaluate outcomes
        subsequent_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id,
            PerformanceTrend.session_date > current_trend.session_date
        ).order_by(PerformanceTrend.session_date).limit(lookahead_sessions).all()
        
        if len(subsequent_trends) == 0:
            # No future data - return neutral reward
            return 0.5
        
        # Calculate component rewards
        rpe_accuracy = self._calculate_rpe_accuracy_reward(
            current_trend, subsequent_trends, intensity_mult_used
        )
        
        volume_progression = self._calculate_volume_progression_reward(
            current_trend, subsequent_trends, volume_mult_used
        )
        
        injury_avoidance = self._calculate_injury_avoidance_reward(
            athlete_id, current_trend.session_date, subsequent_trends
        )
        
        # Weighted combination
        reward = (
            rpe_accuracy * 0.40 +
            volume_progression * 0.30 +
            injury_avoidance * 0.30
        )
        
        return float(np.clip(reward, 0.0, 1.0))
    
    def _calculate_rpe_accuracy_reward(
        self,
        current_trend: PerformanceTrend,
        subsequent_trends: list[PerformanceTrend],
        intensity_mult_used: float
    ) -> float:
        """
        Calculate RPE accuracy reward component.
        
        Reward is based on:
        - How close actual RPE was to target RPE (if target was set)
        - Whether RPE stayed in reasonable range (not too high/low)
        - Consistency of RPE across subsequent sessions
        
        Args:
            current_trend: Current session performance trend
            subsequent_trends: Subsequent session trends
            intensity_mult_used: Intensity multiplier that was used
            
        Returns:
            RPE accuracy reward (0.0 - 1.0)
        """
        if not subsequent_trends:
            return 0.5
        
        # Get RPEs from subsequent sessions
        subsequent_rpes = [t.average_rpe for t in subsequent_trends if t.average_rpe]
        
        if not subsequent_rpes:
            return 0.5
        
        # Reward 1: RPE in optimal range (7-9 is good, 6-10 is acceptable)
        # Penalize extreme RPEs (too easy <6, too hard >10)
        rpe_scores = []
        for rpe in subsequent_rpes:
            if 7.0 <= rpe <= 9.0:
                # Optimal range
                score = 1.0
            elif 6.0 <= rpe < 7.0 or 9.0 < rpe <= 10.0:
                # Acceptable range
                score = 0.7
            elif rpe < 6.0:
                # Too easy - not challenging enough
                score = 0.4
            else:  # rpe > 10.0
                # Too hard - overreaching
                score = 0.2
            
            rpe_scores.append(score)
        
        avg_rpe_score = np.mean(rpe_scores)
        
        # Reward 2: RPE consistency (low variance is good)
        if len(subsequent_rpes) > 1:
            rpe_variance = np.var(subsequent_rpes)
            # Lower variance = higher reward (max variance ~4 for range 6-10)
            consistency_score = 1.0 - min(rpe_variance / 4.0, 1.0)
        else:
            consistency_score = 0.5
        
        # Combine: 70% optimal range, 30% consistency
        reward = avg_rpe_score * 0.7 + consistency_score * 0.3
        
        return float(reward)
    
    def _calculate_volume_progression_reward(
        self,
        current_trend: PerformanceTrend,
        subsequent_trends: list[PerformanceTrend],
        volume_mult_used: float
    ) -> float:
        """
        Calculate volume progression reward component.
        
        Reward is based on:
        - Whether volume increased appropriately (if multiplier > 1.0)
        - Whether volume decreased appropriately (if multiplier < 1.0)
        - Avoiding volume regression when trying to progress
        
        Args:
            current_trend: Current session performance trend
            subsequent_trends: Subsequent session trends
            volume_mult_used: Volume multiplier that was used
            
        Returns:
            Volume progression reward (0.0 - 1.0)
        """
        if not subsequent_trends:
            return 0.5
        
        current_volume = current_trend.total_volume
        subsequent_volumes = [t.total_volume for t in subsequent_trends if t.total_volume]
        
        if not subsequent_volumes:
            return 0.5
        
        avg_subsequent_volume = np.mean(subsequent_volumes)
        
        # Expected volume based on multiplier
        expected_volume = current_volume * volume_mult_used
        
        # Calculate how close actual volume was to expected
        if expected_volume > 0:
            volume_ratio = avg_subsequent_volume / expected_volume
        else:
            volume_ratio = 1.0
        
        # Reward based on how close to target
        # If multiplier was 1.05, we expect ~5% increase
        if volume_mult_used > 1.0:
            # Trying to progress - reward if volume increased
            if volume_ratio >= 0.95:  # Within 5% of target
                reward = 1.0
            elif volume_ratio >= 0.85:  # Within 15% of target
                reward = 0.7
            elif avg_subsequent_volume > current_volume:
                # At least increased
                reward = 0.5
            else:
                # Regressed despite trying to progress
                reward = 0.2
        elif volume_mult_used < 1.0:
            # Trying to reduce - reward if volume decreased appropriately
            if volume_ratio <= 1.05:  # Within 5% of target
                reward = 1.0
            elif volume_ratio <= 1.15:  # Within 15% of target
                reward = 0.7
            elif avg_subsequent_volume < current_volume:
                # At least decreased
                reward = 0.5
            else:
                # Increased despite trying to reduce
                reward = 0.2
        else:
            # Multiplier = 1.0 - maintain volume
            if 0.95 <= volume_ratio <= 1.05:
                reward = 1.0
            else:
                reward = 0.7
        
        return float(reward)
    
    def _calculate_injury_avoidance_reward(
        self,
        athlete_id: int,
        current_session_date: datetime,
        subsequent_trends: list[PerformanceTrend]
    ) -> float:
        """
        Calculate injury avoidance reward component.
        
        Reward is based on:
        - No forced deloads in subsequent sessions
        - No injury flags or pain markers
        - Readiness scores not critically low
        
        Args:
            athlete_id: Athlete ID
            current_session_date: Date of current session
            subsequent_trends: Subsequent session trends
            
        Returns:
            Injury avoidance reward (0.0 - 1.0)
        """
        if not subsequent_trends:
            return 0.5
        
        # Check for forced deloads
        forced_deloads = sum(
            1 for t in subsequent_trends
            if t.deload_triggered and t.deload_reason and "injury" in t.deload_reason.lower()
        )
        
        if forced_deloads > 0:
            # Injury-related deload - severe penalty
            return 0.1
        
        # Check for any deloads (may indicate overreaching)
        any_deloads = sum(1 for t in subsequent_trends if t.deload_triggered)
        if any_deloads > 0:
            # Deload needed - moderate penalty
            return 0.4
        
        # Check readiness scores
        readiness_scores = [t.readiness_score for t in subsequent_trends if t.readiness_score]
        if readiness_scores:
            avg_readiness = np.mean(readiness_scores)
            min_readiness = np.min(readiness_scores)
            
            # Penalize if readiness is critically low
            if min_readiness < 0.3:
                return 0.3
            elif avg_readiness < 0.5:
                return 0.6
            elif avg_readiness >= 0.7:
                return 1.0
            else:
                return 0.8
        
        # Check recovery metrics for pain/injury indicators
        cutoff_date = current_session_date
        if cutoff_date.tzinfo is None:
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        
        lookahead_days = 14  # Check next 2 weeks
        recovery_metrics = self.db.query(RecoveryMetrics).filter(
            RecoveryMetrics.athlete_id == athlete_id,
            RecoveryMetrics.date > cutoff_date,
            RecoveryMetrics.date <= cutoff_date + timedelta(days=lookahead_days)
        ).all()
        
        # Check for high soreness (potential injury risk)
        high_soreness_count = sum(
            1 for r in recovery_metrics
            if r.overall_soreness and r.overall_soreness >= 8
        )
        
        if high_soreness_count >= 3:
            # Persistent high soreness - injury risk
            return 0.5
        
        # No injury indicators - full reward
        return 1.0
    
    def calculate_historical_rewards(
        self,
        athlete_id: int,
        min_sessions: int = 10
    ) -> Dict[int, float]:
        """
        Calculate rewards for all historical sessions.
        
        Useful for creating training targets.
        
        Args:
            athlete_id: Athlete ID
            min_sessions: Minimum sessions required
            
        Returns:
            Dict mapping session_id -> reward_score
        """
        # Get all performance trends
        all_trends = self.db.query(PerformanceTrend).filter(
            PerformanceTrend.athlete_id == athlete_id
        ).order_by(PerformanceTrend.session_date).all()
        
        if len(all_trends) < min_sessions:
            return {}
        
        rewards = {}
        
        # For each session, calculate reward
        for i, trend in enumerate(all_trends[:-2]):  # Need at least 2 future sessions
            # Get adjustments used (from plan entry or default)
            session = self.db.query(WorkoutSession).filter(
                WorkoutSession.id == trend.workout_session_id
            ).first()
            
            if not session:
                continue
            
            # Try to get actual multipliers from plan entry
            volume_mult = 1.0
            intensity_mult = 1.0
            
            # Look for plan entry around this time
            plan_entry = self.db.query(PlanEntry).filter(
                PlanEntry.workout_plan_id.in_(
                    self.db.query(WorkoutPlan.id).filter(
                        WorkoutPlan.athlete_id == athlete_id
                    )
                ),
                PlanEntry.start_date <= trend.session_date,
                PlanEntry.end_date >= trend.session_date
            ).first()
            
            if plan_entry and plan_entry.ai_adjustments:
                volume_mult = plan_entry.ai_adjustments.get("volume_multiplier", 1.0)
                intensity_mult = plan_entry.ai_adjustments.get("intensity_multiplier", 1.0)
            elif plan_entry:
                volume_mult = plan_entry.target_volume_multiplier
                intensity_mult = plan_entry.target_intensity_multiplier
            
            # Calculate reward
            reward = self.calculate_adjustment_reward(
                athlete_id,
                trend.workout_session_id,
                volume_mult,
                intensity_mult
            )
            
            rewards[trend.workout_session_id] = reward
        
        return rewards

