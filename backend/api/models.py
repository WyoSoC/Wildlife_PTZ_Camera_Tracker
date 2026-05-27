"""
Wildlife model registry endpoints.
"""
from __future__ import annotations
from fastapi import APIRouter
from ..core.models import list_models, models_dir

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def get_models():
    """List all available models (built-in + custom in models/ directory)."""
    return {
        "models": [
            {
                "name":            m.name,
                "path":            m.path,
                "description":     m.description,
                "species":         m.species,
                "source":          m.source,
                "auto_download":   m.auto_download,
                "detect_classes":  m.detect_classes,
            }
            for m in list_models()
        ],
        "models_dir": models_dir(),
    }
