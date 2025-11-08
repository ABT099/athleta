"""
Model management service.

Handles model persistence, versioning, and lifecycle management.
"""
from typing import Dict, Optional, Any
import os
import pickle
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.ml.base_model import BaseMLModel


class ModelManager:
    """
    Manages ML model persistence and versioning.
    """
    
    def __init__(self, models_dir: str = "models"):
        """
        Initialize model manager.
        
        Args:
            models_dir: Directory to store model files
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.models_dir / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def save_model(
        self,
        model: BaseMLModel,
        athlete_id: Optional[int] = None,
        version: Optional[str] = None
    ) -> str:
        """
        Save model to disk.
        
        Args:
            model: Trained model to save
            athlete_id: Optional athlete ID for athlete-specific models
            version: Optional version string
            
        Returns:
            Path to saved model file
        """
        if not model.is_trained:
            raise ValueError("Cannot save untrained model")
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        version_str = version or timestamp
        
        if athlete_id:
            filename = f"{model.model_name}_athlete_{athlete_id}_v{version_str}.pkl"
        else:
            filename = f"{model.model_name}_global_v{version_str}.pkl"
        
        filepath = self.models_dir / filename
        
        # Save model
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
        
        # Save metadata
        metadata = {
            "model_name": model.model_name,
            "athlete_id": athlete_id,
            "version": version_str,
            "training_date": model.training_date.isoformat() if model.training_date else None,
            "training_samples": model.training_samples,
            "feature_names": model.feature_names,
            "target_names": model.target_names,
            "saved_at": datetime.utcnow().isoformat(),
            "filepath": str(filepath)
        }
        
        metadata_file = self.metadata_dir / f"{filename}.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return str(filepath)
    
    def load_model(
        self,
        model_name: str,
        athlete_id: Optional[int] = None,
        version: Optional[str] = None
    ) -> Optional[BaseMLModel]:
        """
        Load model from disk.
        
        Args:
            model_name: Name of the model
            athlete_id: Optional athlete ID
            version: Optional version string (loads latest if not specified)
            
        Returns:
            Loaded model or None if not found
        """
        # Find matching model files
        if athlete_id:
            pattern = f"{model_name}_athlete_{athlete_id}_*.pkl"
        else:
            pattern = f"{model_name}_global_*.pkl"
        
        matching_files = list(self.models_dir.glob(pattern))
        
        if not matching_files:
            return None
        
        # If version specified, find exact match
        if version:
            if athlete_id:
                target_file = self.models_dir / f"{model_name}_athlete_{athlete_id}_v{version}.pkl"
            else:
                target_file = self.models_dir / f"{model_name}_global_v{version}.pkl"
            
            if not target_file.exists():
                return None
        else:
            # Load most recent
            target_file = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        # Load model
        try:
            with open(target_file, 'rb') as f:
                model = pickle.load(f)
            return model
        except Exception as e:
            print(f"Error loading model from {target_file}: {e}")
            return None
    
    def get_model_metadata(
        self,
        model_name: str,
        athlete_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Get metadata for a model.
        
        Args:
            model_name: Name of the model
            athlete_id: Optional athlete ID
            
        Returns:
            Metadata dict or None
        """
        # Find matching metadata files
        if athlete_id:
            pattern = f"{model_name}_athlete_{athlete_id}_*.pkl.json"
        else:
            pattern = f"{model_name}_global_*.pkl.json"
        
        matching_files = list(self.metadata_dir.glob(pattern))
        
        if not matching_files:
            return None
        
        # Get most recent
        target_file = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        try:
            with open(target_file, 'r') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            print(f"Error loading metadata from {target_file}: {e}")
            return None
    
    def list_models(
        self,
        athlete_id: Optional[int] = None
    ) -> list[Dict]:
        """
        List all available models.
        
        Args:
            athlete_id: Optional athlete ID to filter by
            
        Returns:
            List of model metadata dicts
        """
        if athlete_id:
            pattern = f"*_athlete_{athlete_id}_*.pkl.json"
        else:
            pattern = "*.pkl.json"
        
        metadata_files = list(self.metadata_dir.glob(pattern))
        
        models = []
        for filepath in metadata_files:
            try:
                with open(filepath, 'r') as f:
                    metadata = json.load(f)
                models.append(metadata)
            except Exception:
                continue
        
        # Sort by saved date
        models.sort(key=lambda m: m.get('saved_at', ''), reverse=True)
        
        return models
    
    def delete_old_models(
        self,
        model_name: str,
        athlete_id: Optional[int] = None,
        keep_latest: int = 3
    ) -> int:
        """
        Delete old model versions, keeping only the most recent.
        
        Args:
            model_name: Name of the model
            athlete_id: Optional athlete ID
            keep_latest: Number of latest versions to keep
            
        Returns:
            Number of models deleted
        """
        # Find matching model files
        if athlete_id:
            pattern = f"{model_name}_athlete_{athlete_id}_*.pkl"
        else:
            pattern = f"{model_name}_global_*.pkl"
        
        matching_files = list(self.models_dir.glob(pattern))
        
        if len(matching_files) <= keep_latest:
            return 0
        
        # Sort by modification time
        matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Delete old files
        deleted = 0
        for filepath in matching_files[keep_latest:]:
            try:
                filepath.unlink()
                # Delete metadata too
                metadata_file = self.metadata_dir / f"{filepath.name}.json"
                if metadata_file.exists():
                    metadata_file.unlink()
                deleted += 1
            except Exception as e:
                print(f"Error deleting {filepath}: {e}")
        
        return deleted

