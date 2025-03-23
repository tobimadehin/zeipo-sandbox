# app/main.py
from fastapi.responses import FileResponse
import torch
from fastapi import FastAPI
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from db.session import create_db_and_tables
from src.api import stt
from src.nlu import intent_understanding
from src.api import calls, stt, system, tts, websockets, telephony
from config import settings

app = FastAPI(title="Zeipo.ai API")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_event():
    create_db_and_tables()
    # Create logs directory
    import os
    os.makedirs("logs/calls", exist_ok=True)

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
app.include_router(stt.router, prefix=settings.API_V1_STR)
app.include_router(stt.router, prefix=settings.API_V1_STR)
app.include_router(telephony.router, prefix=settings.API_V1_STR)
app.include_router(intent_understanding.router, prefix=settings.API_V1_STR)
app.include_router(system.router, prefix=settings.API_V1_STR)
app.include_router(websockets.router, prefix=settings.API_V1_STR)
app.include_router(tts.router, prefix=settings.API_V1_STR)

# Mount static routes
@app.get("/client")
async def get_client():
    return FileResponse("static/client/index.html")

# Register the startup and shutdown events
@app.on_event("startup")
async def startup_websocket_manager():
    await websockets.start_cleanup_task()

@app.on_event("shutdown")
async def shutdown_websocket_manager():
    await websockets.stop_cleanup_task()

