# app/api/language-detections.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.session import get_db
from db.models import CallSession, LanguageDetection
from ...main import router

class LanguageDetectionRequest(BaseModel):
    session_id: str
    language: str
    confidence: float

@router.post("/language-detection")
def detect_language(detection: LanguageDetectionRequest, db: Session = Depends(get_db)):
    call_session = db.query(CallSession).filter(CallSession.session_id == detection.session_id).first()
    
    if not call_session:
        raise HTTPException(status_code=404, detail=f"Session {detection.session_id} not found")
    
    lang_detection = LanguageDetection(
        call_session_id=call_session.id,
        detected_language=detection.language,
        confidence=detection.confidence
    )
    
    db.add(lang_detection)
    db.commit()
    
    return {"status": "success", "detection_id": lang_detection.id}

