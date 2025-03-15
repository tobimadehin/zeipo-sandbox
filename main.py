# app/main.py
from fastapi import APIRouter, FastAPI
import torch
from db.session import create_db_and_tables
from src.api import audio, calls, transcriptions
from config import settings

app = FastAPI(title="Zeipo.ai API")

router = APIRouter(settings.API_V1_STR)

@app.on_event("startup")
def startup_event():
    create_db_and_tables()

# Root endpoint from original api.py
@app.get("/")
async def root():
    """API root endpoint with basic information."""
    # Check if CUDA is available at runtime
    cuda_available = torch.cuda.is_available()
    current_device = "cuda" if cuda_available else "cpu"
    
    return {
        "name": "Zeipo.ai API",
        "status": "running",
        "models": ["tiny", "base", "small", "medium", "large"],
        "device": current_device,
        "cuda_available": cuda_available,
        "cuda_devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if cuda_available else []
    }

# Mount all API routers
app.include_router(calls.router, prefix=settings.API_V1_STR)
app.include_router(transcriptions.router, prefix=settings.API_V1_STR)
app.include_router(audio.router, prefix=settings.API_V1_STR)