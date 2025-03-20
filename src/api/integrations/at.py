# app/src/api/integrations/at.py
import os
from fastapi import APIRouter, Depends, Request, Form, Response
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import africastalking
import uuid
from datetime import datetime
import json

from config import settings
from db.session import get_db
from db.models import Customer, CallSession
from src.tts import get_tts_provider
from src.utils import log_call_to_file
from src.utils.helpers import gen_uuid_12, gen_uuid_16
from static.constants import logger
from src.api.router import create_router
from src.utils.at_utils import log_call_to_file

# Initialize Africa's Talking SDK
africastalking.initialize(settings.AT_USER, settings.AT_API_KEY)
voice = africastalking.Voice

router = create_router("/integrations/at")

# Helper function to build Africa's Talking Voice XML
def build_voice_response(say_text=None, play_url=None, get_digits=None, record=False, **kwargs):
    """
    Build an XML response for Africa's Talking Voice API.
    
    Args:
        say_text: Text to be spoken
        play_url: URL of audio file to play
        get_digits: Configuration for collecting digits
        record: Whether to record the call
        **kwargs: Additional parameters for specific actions
    
    Returns:
        XML string with the voice response
    """
    response = '<?xml version="1.0" encoding="UTF-8"?><Response>'
    
    if say_text:
        # Check if TTS is enabled
        if settings.GOOGLE_TTS_ENABLED and kwargs.get("use_tts", True):
            try:
                # Generate TTS audio
                tts_provider = get_tts_provider()
                audio_content = tts_provider.synthesize(
                    say_text, 
                    voice_id=kwargs.get("voice_id"),
                    language_code=kwargs.get("language_code")
                )
                
                # Save to file
                filename = f"tts_{gen_uuid_16().hex}.mp3"
                output_dir = "data/tts_output"
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, filename)
                
                tts_provider.save_to_file(audio_content, file_path)
                
                # Use the webhook base URL to create a public URL
                audio_url = f"{settings.WEBHOOK_URL}{settings.API_V1_STR}/tts/audio/{filename}"
                
                # Use Play instead of Say for TTS audio
                response += f'<Play url="{audio_url}"/>'
            except Exception as e:
                logger.error(f"Error using TTS in AT response: {str(e)}")
                # Fallback to Say if TTS fails
                response += f'<Say>{say_text}</Say>'
        else:
            # Use regular Say for AT text-to-speech
            response += f'<Say>{say_text}</Say>'
    
    if play_url:
        # Add Play action
        response += f'<Play url="{play_url}"/>'
    
    if get_digits:
        # Add GetDigits action with nested actions
        digits_config = get_digits.get("config", {})
        timeout = digits_config.get("timeout", 30)
        finishOnKey = digits_config.get("finishOnKey", "#")
        numDigits = digits_config.get("numDigits", None)
        
        response += f'<GetDigits timeout="{timeout}" finishOnKey="{finishOnKey}"'
        if numDigits:
            response += f' numDigits="{numDigits}"'
        response += '>'
        
        # Add prompt inside GetDigits
        if "say" in get_digits:
            response += f'<Say>{get_digits["say"]}</Say>'
        
        if "play" in get_digits:
            response += f'<Play url="{get_digits["play"]}"/>'
        
        response += '</GetDigits>'
    
    if record:
        # Add Record action
        record_params = {
            "finishOnKey": kwargs.get("finishOnKey", "#"),
            "maxLength": kwargs.get("maxLength", 10),  # in seconds
            "timeout": kwargs.get("timeout", 10),  # in seconds
            "trimSilence": str(kwargs.get("trimSilence", True)).lower(),
            "playBeep": str(kwargs.get("playBeep", True)).lower()
        }
        
        response += f'<Record finishOnKey="{record_params["finishOnKey"]}" ' \
                  f'maxLength="{record_params["maxLength"]}" ' \
                  f'timeout="{record_params["timeout"]}" ' \
                  f'trimSilence="{record_params["trimSilence"]}" ' \
                  f'playBeep="{record_params["playBeep"]}"/>'
    
    # Add Reject action if provided
    if "reject" in kwargs and kwargs["reject"]:
        reason = kwargs.get("rejectReason", "busy")
        response += f'<Reject reason="{reason}"/>'
    
    # Add Redirect action if provided
    if "redirect" in kwargs and kwargs["redirect"]:
        response += f'<Redirect>{kwargs["redirect"]}</Redirect>'
    
    # Close the response
    response += '</Response>'
    
    return response

# Webhook for incoming voice calls
@router.post("/voice")
async def voice_webhook(
    request: Request,
    sessionId: Optional[str] = Form(None),
    callerNumber: Optional[str] = Form(None),
    direction: Optional[str] = Form(None),
    isActive: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Primary webhook for handling incoming voice calls."""
    # Log the incoming call
    logger.info(f"Incoming call: sessionId={sessionId}, callerNumber={callerNumber}")
    
    # Get all form data for logging
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Log call to file
    log_call_to_file(
        call_sid=sessionId if sessionId else "unknown",
        phone_number=callerNumber if callerNumber else "anonymous",
        direction=direction if direction else "inbound",
        status="received",
        additional_data=form_dict
    )
    
    try:
        # Find or create customer
        phone_number = callerNumber if callerNumber else "anonymous"
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
        session_id = sessionId if sessionId else gen_uuid_12()
        call_session = CallSession(
            session_id=session_id,
            customer_id=customer.id,
            start_time=datetime.now()
        )
        
        db.add(call_session)
        db.commit()
        logger.info(f"Created call session: ID={call_session.id}, SessionID={session_id}")
        
        # Generate XML response
        xml_response = build_voice_response(
            say_text="Welcome to Zeipo AI. How can I help you today?"
        )
        
    except Exception as e:
        logger.error(f"Error handling call: {str(e)}")
        xml_response = build_voice_response(
            say_text="We're sorry, but an error occurred while processing your call."
        )
    
    # Return XML response
    return Response(content=xml_response, media_type="application/xml")


# Webhook for DTMF (keypad) input
@router.post("/dtmf")
async def dtmf_webhook(
    request: Request,
    sessionId: Optional[str] = Form(None),
    dtmfDigits: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Webhook for handling DTMF input from the keypad.
    """
    logger.info(f"DTMF input: sessionId={sessionId}, digits={dtmfDigits}")
    
    # Get all form data for logging
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Log DTMF to file
    log_call_to_file(
        call_sid=sessionId if sessionId else "unknown",
        phone_number="unknown",
        direction="inbound",
        status="dtmf",
        additional_data={"dtmf_digits": dtmfDigits, **form_dict}
    )
    
    # Process DTMF input
    response_text = "You entered "
    if dtmfDigits:
        for digit in dtmfDigits:
            response_text += f"{digit}, "
        response_text += "Thank you for your input."
    else:
        response_text = "No digits were received. Please try again."
    
    # Generate XML response
    xml_response = build_voice_response(say_text=response_text)
    
    return Response(content=xml_response, media_type="application/xml")

# Webhook for call status events
@router.post("/events")
async def events_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook for handling call events like hangup, transfer, etc.
    """
    # Get all form data
    form_data = await request.form()
    form_dict = {key: form_data[key] for key in form_data}
    
    # Extract important fields
    sessionId = form_dict.get("sessionId", "unknown")
    status = form_dict.get("status", "unknown")
    duration = form_dict.get("durationInSeconds", None)
    
    logger.info(f"Call event: sessionId={sessionId}, status={status}, duration={duration}")
    
    # Log event to file
    from src.utils.at_utils import log_call_to_file
    log_call_to_file(
        call_sid=sessionId,
        phone_number="unknown",
        direction="inbound",
        status=status,
        additional_data=form_dict
    )
    
    # Update call session if it's a call end event
    if status in ["completed", "failed", "no-answer", "busy", "rejected"]:
        call_session = db.query(CallSession).filter(CallSession.session_id == sessionId).first()
        
        if call_session:
            call_session.end_time = datetime.now()
            if duration:
                try:
                    call_session.duration_seconds = int(duration)
                except ValueError:
                    pass
            
            db.commit()
            logger.info(f"Updated call session {sessionId} with end time and duration")
        else:
            logger.warning(f"Call session not found for sessionId={sessionId}")
    
    return {"status": "success"}

# Function to make outbound calls
def make_outbound_call(to_number: str, client_name: str = "Zeipo AI", say_text: str = None):
    """
    Make an outbound call using Africa's Talking Voice API.
    
    Args:
        to_number: The phone number to call
        client_name: Caller ID to display (if available)
        say_text: Text to be spoken when call is answered
    
    Returns:
        Call response from Africa's Talking
    """
    try:
        # Prepare callback URLs
        callback_url = f"{settings.WEBHOOK_BASE_URL}{settings.API_V1_STR}/at/events"
        
        # Build response XML if say_text is provided
        xml = None
        if say_text:
            xml = build_voice_response(say_text=say_text)
        
        # Make the call
        call_response = voice.call(
            callFrom=settings.AT_PHONE_NUMBER,
            callTo=[to_number],
            clientRequestId=str(uuid.uuid4()),
            callbackUrl=callback_url,
            xml=xml
        )
        
        logger.info(f"Initiated outbound call to {to_number}")
        logger.debug(f"Call response: {json.dumps(call_response)}")
        
        return call_response
    except Exception as e:
        logger.error(f"Error making outbound call: {str(e)}")
        raise