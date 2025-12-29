"""
Tests for Model Selector.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.ml.model_selector import ModelSelector
from app.models import WorkoutSession


@pytest.mark.unit
@pytest.mark.ml
class TestModelSelector:
    """Test model selection logic."""
    
    def test_get_session_count(self):
        """Test session count retrieval."""
        db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 15
        
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        count = selector.get_session_count(athlete_id=1)
        
        assert count == 15
        db.query.assert_called_with(WorkoutSession)
    
    def test_select_model_rules_only(self):
        """Test selection for <10 sessions."""
        db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 5
        
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        model_type, n_models, config = selector.select_model_type(athlete_id=1)
        
        assert model_type == "rules_only"
        assert n_models == 0
        assert config == {}
    
    def test_select_model_lightgbm_5(self):
        """Test selection for 10-29 sessions."""
        db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 15
        
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        model_type, n_models, config = selector.select_model_type(athlete_id=1)
        
        # Should return lightgbm for 15 sessions (< 20, so no sequential)
        assert model_type == "lightgbm"
        assert n_models == 5
        assert config["min_sessions"] == 11  # 11 (not 10) to ensure 5 samples with 6 overhead
        assert config["use_ensemble"] is True
    
    def test_select_model_lightgbm_10(self):
        """Test selection for 30+ sessions."""
        db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 35  # 30+ sessions
        
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        model_type, n_models, config = selector.select_model_type(athlete_id=1)
        
        # Should return either sequential (if TensorFlow available) or lightgbm (fallback)
        assert model_type in ["lightgbm", "sequential"]
        assert config["min_sessions"] == 30
        assert config["use_ensemble"] is True
        
        # Both models should use 10 ensemble models for 30+ sessions
        assert n_models == 10
        if model_type == "sequential":
            assert "sequence_length" in config
    
    def test_get_model_config(self):
        """Test complete model configuration."""
        db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 15
        
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        config = selector.get_model_config(athlete_id=1)
        
        assert "model_type" in config
        assert "n_ensemble_models" in config
        assert "session_count" in config
        assert config["session_count"] == 15
        assert config["model_type"] == "lightgbm"
        assert config["n_ensemble_models"] == 5
    
    def test_should_use_sequential(self):
        """Test sequential model decision."""
        db = Mock(spec=Session)
        mock_query = Mock()
        
        # Test with 15 sessions (should not use sequential)
        mock_query.filter.return_value.count.return_value = 15
        db.query.return_value = mock_query
        
        selector = ModelSelector(db)
        assert not selector.should_use_sequential(athlete_id=1)
        
        # Test with 25 sessions (may use sequential if available)
        mock_query.filter.return_value.count.return_value = 25
        result = selector.should_use_sequential(athlete_id=1)
        # Result depends on TensorFlow availability, both are valid
        assert isinstance(result, bool)

