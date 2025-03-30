# app/api/stt.py
import time
from typing import Optional
from fastapi import File, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import whisper
import tempfile
import os
from pydantic import BaseModel
from db.models import CallSession, Transcription
from src.stt import get_stt_provider
from static.constants import AVAILABLE_MODELS, logger
from db.session import get_db
from src.api.router import create_router


class TranscriptionSegment(BaseModel):
    session_id: str
    transcript: str
    speaker: str
    segment_start_time: float
    segment_end_time: Optional[float] = None
    
router = create_router("/stt")

async def process_audio(file_path: str, model_name: str, task: str, language: Optional[str] = None):
    """Process audio file with Whisper."""
    try:
        # Get STT provider
        provider = get_stt_provider()
        
        # Transcribe using provider
        result = provider.transcribe(
            audio_file=file_path, 
            language=language,
            task=task,
            model_name=model_name
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise e


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("tiny"),
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
    

@router.post("/segments")
def add_transcription(segment: TranscriptionSegment, db: Session = Depends(get_db)):
    call_session = db.query(CallSession).filter(CallSession.session_id == segment.session_id).first()
    
    if not call_session:
        raise HTTPException(status_code=404, detail=f"Session {segment.session_id} not found")
    
    transcription = Transcription(
        call_session_id=call_session.id,
        transcript=segment.transcript,
        speaker=segment.speaker,
        segment_start_time=segment.segment_start_time,
        segment_end_time=segment.segment_end_time
    )
    
    db.add(transcription)
    db.commit()
    
    return {"status": "success", "segment_id": transcription.id}

