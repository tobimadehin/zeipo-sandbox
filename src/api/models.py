# app/api/models.py
import time
from typing import Dict
import torch
import whisper

from constants import AVAILABLE_MODELS, logger
from src.api.system import get_device
from ...main import router

models: Dict[str, whisper.Whisper] = {}
DEVICE = get_device()

def get_model(name: str):
    """Load and cache the requested model."""
    if name not in AVAILABLE_MODELS:
        raise ValueError(f"Model {name} not available. Choose from {AVAILABLE_MODELS}")
    
    if name not in models:
        logger.info(f"Loading model: {name} on {DEVICE}")
        start_time = time.time()
        models[name] = whisper.load_model(name, device=DEVICE)
        load_time = time.time() - start_time
        logger.info(f"Model {name} loaded in {load_time:.2f} seconds")
    
    return models[name]


@router.get("/models")
async def list_models():
    """List available models and their status."""
    # Existing models code from api.py
    return {
        "available_models": ["tiny", "base", "small", "medium", "large"],
        "loaded_models": {},
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "cuda_available": torch.cuda.is_available()
    }


