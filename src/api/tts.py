# src/api/tts.py
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os
import uuid

from db.session import get_db
from src.tts import get_tts_provider
from config import settings
from static.constants import logger
from src.api.router import create_router

router = create_router("/tts")

@router.get("/voices")
async def list_voices(language_code: Optional[str] = None):
    """
    List available TTS voices.
    
    Args:
        language_code: Optional language code to filter voices
        
    Returns:
        List of available voices
    """
    try:
        tts_provider = get_tts_provider()
        voices = tts_provider.get_available_voices(language_code)
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Error listing voices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/synthesize")
async def synthesize_speech(
    text: str,
    voice_id: Optional[str] = None,
    language_code: Optional[str] = None,
    return_audio: bool = False,
    db: Session = Depends(get_db)
):
    """
    Synthesize speech from text.
    
    Args:
        text: The text to synthesize
        voice_id: Specific voice name (e.g., 'en-US-Neural2-F')
        language_code: Language code (e.g., 'en-US', 'sw')
        return_audio: Whether to return audio file directly
        
    Returns:
        Audio file or file URL
    """
    try:
        tts_provider = get_tts_provider()
        
        # Synthesize speech
        audio_content = tts_provider.synthesize(text, voice_id, language_code)
        
        # Generate a unique filename
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        output_dir = "data/tts_output"
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, filename)
        tts_provider.save_to_file(audio_content, file_path)
        
        # Return either the audio file or a URL
        if return_audio:
            return FileResponse(
                file_path,
                media_type="audio/mpeg",
                filename=filename
            )
        else:
            return {
                "success": True,
                "file_path": file_path,
                "file_url": f"/api/v1/tts/audio/{filename}"
            }
    
    except Exception as e:
        logger.error(f"Error synthesizing speech: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """
    Get a generated audio file.
    
    Args:
        filename: Name of the audio file
        
    Returns:
        Audio file
    """
    file_path = os.path.join("data/tts_output", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )