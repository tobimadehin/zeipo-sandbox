# app/src/api/telephony.py
from fastapi import APIRouter, Depends, Request, Response, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import json

from config import settings
from db.session import get_db
from db.models import Customer, CallSession
from src.telephony import get_telephony_provider
from src.utils.helpers import gen_uuid_12
from static.constants import logger

router = APIRouter(prefix="/telephony")

@router.post("/voice")
async def voice_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Primary webhook for handling incoming voice calls from any provider.
    """
    # Get the telephony provider
    provider = get_telephony_provider()
    
    # Get the form data
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Parse the call data using the provider
    call_data = provider.parse_call_data(form_dict)
    
    try:
        # Find or create customer
        phone_number = call_data.get("phone_number", "anonymous")
        customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()
        
        if not customer:
            logger.info(f"Creating new customer with phone number: {phone_number}")
            customer = Customer(
                phone_number=phone_number,
                last_activity=datetime.now()
            )
            db.add(customer)
            db.flush()
        else:
            logger.info(f"Found existing customer: ID={customer.id}")
            customer.last_activity = datetime.now()
        
        # Create call session
        session_id = call_data.get("session_id", gen_uuid_12())
        call_session = CallSession(
            session_id=session_id,
            customer_id=customer.id,
            start_time=datetime.now()
        )
        
        db.add(call_session)
        db.commit()
        logger.info(f"Created call session: ID={call_session.id}, SessionID={session_id}")
        
        # Generate provider-specific response
        voice_response = provider.build_voice_response(
            say_text="Welcome to Zeipo AI. How can I help you today?"
        )
        
        # Determine content type based on provider
        provider_name = call_data.get("provider", "")
        content_type = "application/xml" if provider_name == "africas_talking" else "application/json"
        
        return Response(content=voice_response, media_type=content_type)
        
    except Exception as e:
        logger.error(f"Error handling call: {str(e)}")
        error_response = provider.build_voice_response(
            say_text="We're sorry, but an error occurred while processing your call."
        )
        
        # Determine content type based on provider
        provider_name = call_data.get("provider", "")
        content_type = "application/xml" if provider_name == "africas_talking" else "application/json"
        
        return Response(content=error_response, media_type=content_type)


@router.post("/dtmf")
async def dtmf_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook for handling DTMF input from the keypad.
    """
    # Get the telephony provider
    provider = get_telephony_provider()
    
    # Get the form data
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Parse the DTMF data using the provider
    dtmf_data = provider.parse_dtmf_data(form_dict)
    
    session_id = dtmf_data.get("session_id")
    digits = dtmf_data.get("digits", "")
    
    logger.info(f"DTMF input: sessionId={session_id}, digits={digits}")
    
    # Process DTMF input
    response_text = "You entered "
    if digits:
        for digit in digits:
            response_text += f"{digit}, "
        response_text += "Thank you for your input."
    else:
        response_text = "No digits were received. Please try again."
    
    # Generate provider-specific response
    voice_response = provider.build_voice_response(say_text=response_text)
    
    # Determine content type based on provider
    provider_name = dtmf_data.get("provider", "")
    content_type = "application/xml" if provider_name == "africas_talking" else "application/json"
    
    return Response(content=voice_response, media_type=content_type)


@router.post("/events")
async def events_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook for handling call events like hangup, transfer, etc.
    """
    # Get the telephony provider
    provider = get_telephony_provider()
    
    # Get the form data
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Parse the event data using the provider
    event_data = provider.parse_event_data(form_dict)
    
    session_id = event_data.get("session_id", "unknown")
    status = event_data.get("status", "unknown")
    duration = event_data.get("duration")
    
    logger.info(f"Call event: sessionId={session_id}, status={status}, duration={duration}")
    
    # Update call session if it's a call end event
    if status in ["completed", "failed", "no-answer", "busy", "rejected"]:
        call_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()
        
        if call_session:
            call_session.end_time = datetime.now()
            if duration is not None:
                try:
                    call_session.duration_seconds = int(duration)
                except ValueError:
                    pass
            
            db.commit()
            logger.info(f"Updated call session {session_id} with end time and duration")
        else:
            logger.warning(f"Call session not found for sessionId={session_id}")
    
    return {"status": "success"}


@router.post("/outbound")
async def make_outbound_call(
    to_number: str,
    message: Optional[str] = None,
    client_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Make an outbound call using the configured telephony provider.
    
    Args:
        to_number: Phone number to call
        message: Message to speak when the call is answered
        client_name: Name to display as caller ID
    
    Returns:
        Call response details
    """
    try:
        # Get the telephony provider
        provider = get_telephony_provider()
        
        # Default client name if not provided
        client_name = client_name or "Zeipo AI"
        
        # Make the call
        call_response = provider.make_outbound_call(
            to_number=to_number,
            client_name=client_name,
            say_text=message
        )
        
        # Create a call session record
        session_id = call_response.get("session_id", gen_uuid_12())
        
        # Find or create customer
        customer = db.query(Customer).filter(Customer.phone_number == to_number).first()
        if not customer:
            customer = Customer(
                phone_number=to_number,
                last_activity=datetime.now()
            )
            db.add(customer)
            db.flush()
        
        # Create call session
        call_session = CallSession(
            session_id=session_id,
            customer_id=customer.id,
            start_time=datetime.now()
        )
        
        db.add(call_session)
        db.commit()
        
        return {
            "status": "success",
            "call_id": call_session.id,
            "session_id": session_id,
            "provider_response": call_response
        }
        
    except Exception as e:
        logger.error(f"Error making outbound call: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to make call: {str(e)}")
    