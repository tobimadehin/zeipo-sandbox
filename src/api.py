from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import whisper
import tempfile
import os
import time
import torch
import uuid
import logging
from typing import Dict, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("whisper-api")

# Initialize FastAPI app
app = FastAPI(
    title="Zeipo.ai API",
    description="Intelligent telephony solution for African businesses based on OpenAI's Whisper model",
    version="0.0.1"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model cache
models: Dict[str, whisper.Whisper] = {}

# Get available device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {DEVICE}")

# Available models
AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large"]

def get_model(name: str):
    """Load and cache the requested model."""
    if name not in AVAILABLE_MODELS:
        raise ValueError(f"Model {name} not available. Choose from {AVAILABLE_MODELS}")
    
    if name not in models:
        logger.info(f"Loading model: {name}")
        start_time = time.time()
        models[name] = whisper.load_model(name, device=DEVICE)
        load_time = time.time() - start_time
        logger.info(f"Model {name} loaded in {load_time:.2f} seconds")
    
    return models[name]

async def process_audio(file_path: str, model_name: str, task: str, language: Optional[str] = None):
    """Process audio file with Whisper."""
    try:
        # Load model
        model = get_model(model_name)
        
        # Set options
        options = {"task": task}
        if language:
            options["language"] = language
        
        # Transcribe
        start_time = time.time()
        result = model.transcribe(file_path, **options)
        process_time = time.time() - start_time
        
        # Get audio duration for RTF calculation
        audio = whisper.load_audio(file_path)
        audio_duration = len(audio) / whisper.audio.SAMPLE_RATE
        rtf = process_time / audio_duration
        
        # Add performance metrics
        result["_performance"] = {
            "process_time": process_time,
            "audio_duration": audio_duration,
            "real_time_factor": rtf
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise e

@app.get("/")
async def root():
    """API root endpoint with basic information."""
    return {
        "name": "Zeipo.ai API",
        "status": "running",
        "models": AVAILABLE_MODELS,
        "device": DEVICE
    }

@app.post("/transcribe/")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("small"),
    task: str = Form("transcribe"),
    language: Optional[str] = Form(None)
):
    """Transcribe or translate audio file."""
    # Validate model
    if model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Model '{model}' not available. Choose from {AVAILABLE_MODELS}")
    
    # Validate task
    if task not in ["transcribe", "translate"]:
        raise HTTPException(status_code=400, detail="Task must be either 'transcribe' or 'translate'")
    
    # Save uploaded file
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            # Write uploaded file data to the temp file
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Process the audio
        result = await process_audio(temp_path, model, task, language)
        
        # Remove temporary file
        os.unlink(temp_path)
        
        return result
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        # Ensure temp file is removed in case of error
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models/")
async def list_models():
    """List available models and their status."""
    return {
        "available_models": AVAILABLE_MODELS,
        "loaded_models": list(models.keys()),
        "device": DEVICE
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)