# src/api/nlu/intent_understanding.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any
from pydantic import BaseModel

from db.session import get_db
from db.models import CallSession
from src.nlp.intent_processor import IntentProcessor

# Create intent processor
intent_processor = IntentProcessor()

class NLURequest(BaseModel):
    """Request model for NLU processing."""
    text: str
    session_id: str

class NLUResponse(BaseModel):
    """Response model for NLU processing."""
    primary_intent: str
    confidence: float
    all_intents: List[Dict[str, Any]]
    entities: Dict[str, List[str]]
    response: str
    session_id: str
    text: str

async def process_text(
    request: NLURequest,
    db: Session = Depends(get_db)
):
    """
    Process text to detect intents and entities.
    
    Args:
        request: NLU request with text and session ID
        db: Database session
    
    Returns:
        NLU processing results
    """
    # Check if session exists
    call_session = db.query(CallSession).filter(CallSession.session_id == request.session_id).first()
    if not call_session:
        raise HTTPException(status_code=404, detail=f"Call session not found: {request.session_id}")
    
    # Process text
    results, response = intent_processor.process_text(
        text=request.text,
        session_id=request.session_id,
        db=db
    )
    
    # Check for errors
    if "error" in results:
        raise HTTPException(status_code=500, detail=results["error"])
    
    # Format response
    all_intents_list = [{"intent": intent, "confidence": conf} for intent, conf in results.get("all_intents", [])]
    
    nlu_response = {
        "primary_intent": results["primary_intent"],
        "confidence": results["confidence"],
        "all_intents": all_intents_list,
        "entities": results["entities"],
        "response": response,
        "session_id": request.session_id,
        "text": request.text
    }
    
    return nlu_response