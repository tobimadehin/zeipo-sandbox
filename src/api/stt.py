# app/api/stt.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import CallSession, Transcription
from src.api.router import create_router

class TranscriptionSegment(BaseModel):
    session_id: str
    transcript: str
    speaker: str
    segment_start_time: float
    segment_end_time: Optional[float] = None
    
router = create_router("/stt")

@router.post("/")
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
