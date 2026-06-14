"""
Tests for Volume Landmarks (MEV/MAV/MRV) system.

Tests volume tracking, landmark calculations, and recommendations.
"""
import pytest
from datetime import datetime, timedelta
from app.modules.volume import VolumeManager
from app.utils.constants import TrainingExperience


class TestVolumeLandmarks:
    """Test volume landmark calculations."""
    
    def test_get_volume_landmarks_beginner(self):
        """Test MEV/MAV/MRV for beginner."""
        # Create a mock db session (would need proper setup in real test)
        # For now, test the logic directly
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        landmarks = vm.get_volume_landmarks(
            TrainingExperience.BEGINNER,
            "mid_chest"
        )
        
        # Beginner chest (large muscle) should have MEV around 8, MRV around 15
        assert landmarks["mev"] >= 6
        assert landmarks["mrv"] >= 12
        assert landmarks["mav"] == (landmarks["mev"] + landmarks["mrv"]) // 2
    
    def test_get_volume_landmarks_advanced(self):
        """Test MEV/MAV/MRV for advanced."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        landmarks = vm.get_volume_landmarks(
            TrainingExperience.ADVANCED,
            "mid_chest"
        )
        
        # Advanced should have higher landmarks
        assert landmarks["mev"] >= 10
        assert landmarks["mrv"] >= 20
        assert landmarks["mav"] == (landmarks["mev"] + landmarks["mrv"]) // 2
    
    def test_muscle_size_adjustment(self):
        """Test that muscle size affects landmarks."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock

        vm = VolumeManager(Mock())

        # quadriceps (large) and biceps (small) come from the fake exercise-service

        # Large muscle (quadriceps)
        large_landmarks = vm.get_volume_landmarks(
            TrainingExperience.INTERMEDIATE,
            "quadriceps"
        )
        
        # Small muscle (biceps)
        small_landmarks = vm.get_volume_landmarks(
            TrainingExperience.INTERMEDIATE,
            "biceps"
        )
        
        # Large muscles should have higher landmarks
        assert large_landmarks["mev"] > small_landmarks["mev"]
        assert large_landmarks["mrv"] > small_landmarks["mrv"]


class TestVolumePosition:
    """Test volume position calculations."""
    
    def test_below_mev_position(self):
        """Test detection when volume is below MEV."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock calculate_current_volume to return low volume
        vm.calculate_current_volume = Mock(return_value={
            "total_sets": 5,  # Below MEV (typically 8-10)
            "total_volume_load": 1000.0,
            "exercises_count": 2,
            "days_analyzed": 7,
        })
        
        position = vm.get_volume_position(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE
        )
        
        assert position["position"] == "below_mev"
        assert position["recommendation"] == "increase_volume"
        assert position["priority"] == "high"
    
    def test_above_mrv_position(self):
        """Test detection when volume is above MRV."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock calculate_current_volume to return high volume
        vm.calculate_current_volume = Mock(return_value={
            "total_sets": 25,  # Above MRV (typically 20)
            "total_volume_load": 5000.0,
            "exercises_count": 4,
            "days_analyzed": 7,
        })
        
        position = vm.get_volume_position(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE
        )
        
        assert position["position"] == "above_mrv"
        assert position["recommendation"] == "reduce_volume"
        assert position["priority"] == "high"
    
    def test_optimal_position(self):
        """Test detection when volume is in optimal range."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock calculate_current_volume to return optimal volume
        vm.calculate_current_volume = Mock(return_value={
            "total_sets": 15,  # Between MEV and MRV
            "total_volume_load": 3000.0,
            "exercises_count": 3,
            "days_analyzed": 7,
        })
        
        position = vm.get_volume_position(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE
        )
        
        assert position["position"] in ["mev_to_mav", "mav_to_mrv"]
        assert position["recommendation"] in ["maintain_or_increase", "maintain"]


class TestVolumeAdjustmentRecommendations:
    """Test volume adjustment recommendations."""
    
    def test_increase_volume_recommendation(self):
        """Test recommendation to increase volume when below MEV."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock get_volume_position to return below_mev
        vm.get_volume_position = Mock(return_value={
            "position": "below_mev",
            "current_sets": 5,
            "mev": 10,
            "mrv": 20,
            "message": "Volume below MEV",
            "priority": "high",
        })
        
        recommendation = vm.get_volume_adjustment_recommendation(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE,
            current_volume_multiplier=1.0
        )
        
        assert recommendation["adjustment"] > 1.0
        assert recommendation["recommended_multiplier"] > 1.0
        assert recommendation["priority"] == "high"
    
    def test_reduce_volume_recommendation(self):
        """Test recommendation to reduce volume when above MRV."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock get_volume_position to return above_mrv
        vm.get_volume_position = Mock(return_value={
            "position": "above_mrv",
            "current_sets": 25,
            "mev": 10,
            "mrv": 20,
            "message": "Volume exceeds MRV",
            "priority": "high",
        })
        
        recommendation = vm.get_volume_adjustment_recommendation(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE,
            current_volume_multiplier=1.0
        )
        
        assert recommendation["adjustment"] < 1.0
        assert recommendation["recommended_multiplier"] < 1.0
        assert recommendation["priority"] == "high"
    
    def test_maintain_volume_recommendation(self):
        """Test recommendation to maintain volume when optimal."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock get_volume_position to return optimal
        vm.get_volume_position = Mock(return_value={
            "position": "mav_to_mrv",
            "current_sets": 15,
            "mev": 10,
            "mrv": 20,
            "message": "Volume in optimal range",
            "priority": "low",
        })
        
        recommendation = vm.get_volume_adjustment_recommendation(
            athlete_id=1,
            muscle_name="mid_chest",
            experience=TrainingExperience.INTERMEDIATE,
            current_volume_multiplier=1.0
        )
        
        assert recommendation["adjustment"] == 1.0
        assert recommendation["recommended_multiplier"] == 1.0


class TestAllMuscleVolumeStatus:
    """Test getting volume status for all muscle groups."""
    
    def test_get_all_muscle_status(self):
        """Test getting volume status for all muscle groups."""
        from app.modules.volume import VolumeManager
        from unittest.mock import Mock
        
        db = Mock()
        vm = VolumeManager(db)
        
        # Mock get_volume_position for all muscle groups
        def mock_get_volume_position(athlete_id, muscle_name, experience, days_lookback):
            return {
                "position": "mev_to_mav",
                "current_sets": 12,
                "mev": 10,
                "mav": 15,
                "mrv": 20,
                "message": "Volume in effective range",
                "priority": "medium",
                "percentage_of_range": 60.0,
                "volume_load": 2000.0,
            }
        
        vm.get_volume_position = Mock(side_effect=mock_get_volume_position)

        # All muscle groups come from the fake exercise-service (GetMuscles).

        status = vm.get_all_muscle_volume_status(
            athlete_id=1,
            experience=TrainingExperience.INTERMEDIATE
        )
        
        assert "muscle_groups" in status
        assert "summary" in status
        assert "overall_recommendation" in status
        assert len(status["muscle_groups"]) > 0
        assert status["summary"]["total_muscle_groups"] > 0

