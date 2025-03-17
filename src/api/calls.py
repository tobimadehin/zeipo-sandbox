# app/api/calls.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import Customer, CallSession
import uuid
from src.api.router import router

class CallRequest(BaseModel):
    phone_number: str
    session_id: Optional[str] = None

class CallResponse(BaseModel):
    id: int
    session_id: str
    customer_id: int
    start_time: datetime

    class Config:
        orm_mode = True

@router.get("/calls", response_model=list[CallResponse])
def list_calls(db: Session = Depends(get_db)):
    calls = db.query(CallSession).all()
    return calls

@router.get("/calls/{session_id}", response_model=CallResponse)
def get_call(session_id: str, db: Session = Depends(get_db)):
    call_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()

    if not call_session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return call_session

@router.patch("/calls/{session_id}")
def end_call(
    session_id: str, 
    recording_url: Optional[str] = None, 
    escalated: bool = False,
    db: Session = Depends(get_db)
):
    call_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()
    
    if not call_session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    end_time = datetime.now()
    duration = (end_time - call_session.start_time).total_seconds()
    
    call_session.end_time = end_time
    call_session.duration_seconds = duration
    call_session.recording_url = recording_url
    call_session.escalated = escalated
    
    db.commit()
    
    return {"status": "success", "call_id": call_session.id}
