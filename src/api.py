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
    description="Intelligent telephony solution for African businesses",
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

# Get available device - Enhanced with better diagnostic logging
def get_device():
    """Detect and configure the optimal device with detailed logging."""
    try:
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            # Log GPU information
            device_count = torch.cuda.device_count()
            logger.info(f"Found {device_count} CUDA device(s)")
            
            for i in range(device_count):
                logger.info(f"Device {i}: {torch.cuda.get_device_name(i)}")
                
            # Test CUDA functionality
            test_tensor = torch.tensor([1.0, 2.0, 3.0]).cuda()
            logger.info(f"Test tensor created on GPU: {test_tensor.device}")
            
            return "cuda"
        else:
            logger.warning("CUDA is not available, falling back to CPU")
            return "cpu"
    except Exception as e:
        logger.error(f"Error detecting device: {str(e)}")
        logger.warning("Falling back to CPU due to error")
        return "cpu"

# Initialize device
DEVICE = get_device()
logger.info(f"Selected device for API: {DEVICE}")

# Available models
AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large"]

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
        logger.info(f"Starting transcription of {file_path} with model {model_name}")
        result = model.transcribe(file_path, **options)
        process_time = time.time() - start_time
        
        # Get audio duration for RTF calculation
        audio = whisper.load_audio(file_path)
        audio_duration = len(audio) / whisper.audio.SAMPLE_RATE
        rtf = process_time / audio_duration
        
        logger.info(f"Transcription completed in {process_time:.2f}s, RTF: {rtf:.2f}")
        
        # Add performance metrics
        result["_performance"] = {
            "process_time": process_time,
            "audio_duration": audio_duration,
            "real_time_factor": rtf,
            "device": str(model.device)
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise e

@app.get("/")
async def root():
    """API root endpoint with basic information."""
    # Check if CUDA is available at runtime
    cuda_available = torch.cuda.is_available()
    current_device = "cuda" if cuda_available else "cpu"
    
    # If there's a mismatch between initial detection and current status
    if current_device != DEVICE:
        logger.warning(f"Device mismatch: Initially detected {DEVICE}, now {current_device}")
    
    return {
        "name": "Zeipo.ai API",
        "status": "running",
        "models": AVAILABLE_MODELS,
        "device": current_device,
        "cuda_available": cuda_available,
        "cuda_devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if cuda_available else []
    }

@app.get("/gpu-info")
async def gpu_info():
    """Detailed information about available GPU resources."""
    if not torch.cuda.is_available():
        return {"status": "No GPU available", "device": "cpu"}
    
    try:
        info = {
            "cuda_available": True,
            "device_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "devices": []
        }
        
        for i in range(info["device_count"]):
            device_info = {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "capability": torch.cuda.get_device_capability(i),
                "total_memory": torch.cuda.get_device_properties(i).total_memory / (1024**3)  # Convert to GB
            }
            info["devices"].append(device_info)
        
        return info
    except Exception as e:
        return {"status": "Error getting GPU info", "error": str(e)}

@app.post("/transcribe")
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

@app.get("/models")
async def list_models():
    """List available models and their status."""
    loaded_model_info = {}
    for name, model in models.items():
        loaded_model_info[name] = {
            "device": str(model.device),
            "dims": model.dims.__dict__ if hasattr(model, "dims") else None
        }
    
    return {
        "available_models": AVAILABLE_MODELS,
        "loaded_models": loaded_model_info,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available()
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on 0.0.0.0:8000 - This will make it accessible from outside the container")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
    