# app/main.py
import json
import os
import time
from fastapi.responses import FileResponse
import torch
from fastapi import FastAPI
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from db.session import create_db_and_tables
from src.telephony import get_telephony_provider
from src.api import stt
from src.telephony.clients.signalwire_client import SignalWireClient
from src.nlu import intent_understanding
from src.api import calls, stt, system, tts, telephony
from config import settings
from src.telephony.provider_factory import get_telephony_provider_name, set_telephony_provider
from static.constants import logger

app = FastAPI(title="Zeipo.ai API")

# Global SignalWire client
telephony_provider = None

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_event():
    global telephony_provider
    
    # Setup database schema
    create_db_and_tables()
    
    # Create logs directory
    import os
    os.makedirs("logs/calls", exist_ok=True)
    
    # Initialize SignalWire if it's the configured provider
    if settings.DEFAULT_TELEPHONY_PROVIDER == "signalwire":
        logger.debug("Found default configuration, initializing client...")
        try:
            telephony_provider = set_telephony_provider("signalwire")
            
            logger.debug(f"SignalWire client: {get_telephony_provider_name(telephony_provider)} initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SignalWire client: {str(e)}", exc_info=True)
            

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
        "device": current_device,
        "cuda_available": cuda_available,
        "cuda_devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if cuda_available else []
    }

# Mount all API routers
app.include_router(calls.router, prefix=settings.API_V1_STR)
app.include_router(stt.router, prefix=settings.API_V1_STR)
app.include_router(system.router, prefix=settings.API_V1_STR)
app.include_router(tts.router, prefix=settings.API_V1_STR)
app.include_router(telephony.router, prefix=settings.API_V1_STR)

# Mount static routes
@app.get("/client")
async def get_client():
    return FileResponse("static/client/index.html")


