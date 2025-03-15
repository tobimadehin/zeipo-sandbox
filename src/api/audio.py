# app/api/audio.py
import time
from typing import Optional
from fastapi import File, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import whisper
import tempfile
import os
from static.constants import AVAILABLE_MODELS, logger
from db.session import get_db
from src.api.models import get_model
from src.api.router import router

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


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("small"),
    task: str = Form("transcribe"),
    language: Optional[str] = Form(None),
    db: Session = Depends(get_db)
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
