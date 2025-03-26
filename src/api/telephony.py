# app/src/api/telephony.py
import time
from fastapi import APIRouter, Depends, Request, Response, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import json

from config import settings
from db.session import get_db, SessionLocal
from db.models import Customer, CallSession
from src.nlp.intent_processor import IntentProcessor
from src.telephony import get_telephony_provider
from src.telephony.provider_base import TelephonyProvider
from src.tts import get_tts_provider
from src.utils.helpers import gen_uuid_12, gen_uuid_16
from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager
from ...main import ari_client  

stream_manager = AudioStreamManager()
intent_processor = IntentProcessor()

router = APIRouter(prefix="/telephony")

class CallHandler:
    """Factory class that handles different types of call connections."""
    
    @staticmethod
    async def create_call_session(
                                phone_number: str, 
                                provider_name: str = "unknown", 
                                session_id: Optional[str] = None) -> str:
        """Create a database record for this call."""
        db = SessionLocal()
        try:
            # Find or create customer
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
            session_id = session_id or gen_uuid_12()
            
            existing_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()
            if existing_session:
                logger.info(f"Found existing call session: ID={existing_session.id}, SessionID={session_id}")
                return existing_session.session_id
            
            call_session = CallSession(
                session_id=session_id,
                customer_id=customer.id,
                start_time=datetime.now()
            )
            
            db.add(call_session)
            db.commit()
            logger.info(f"Created call session: ID={call_session.id}, SessionID={session_id}, Provider: {provider_name}")
            
            return session_id
        except Exception as e:
            logger.error(f"Database error creating call session: {str(e)}")
            if db.is_active:
                db.rollback()
            return gen_uuid_12()  # Fallback
        finally:
            db.close()
    
    @staticmethod
    async def handle_webhook(request: Request) -> Response:
        """Handle webhook POST requests (Africa's Talking)."""
        telephony_provider = get_telephony_provider()
        
        logger.debug(f"Handling webhook request: {request} from provider: {telephony_provider}")
        
        # Get the form data
        form_data = await request.form()
        form_dict = {key: form_data[key] for key in form_data}
        
        # Parse call data
        call_data = telephony_provider.parse_call_data(form_dict)
        session_id = call_data.get("session_id")
        
        # Build response to dial SIP extension in Asterisk
        sip_extension = "9000"  # The Stasis application extension in Asterisk
        voice_response = telephony_provider.build_voice_response(
            dial_sip=f"{sip_extension}@{settings.ASTERISK_HOST}"
        )
        
        return Response(content=voice_response, media_type="application/xml")
    
    @staticmethod
    async def handle_websocket(
        websocket: WebSocket, 
        language: Optional[str] = None, 
        model: str = "small",
        provider_name: str = "voip_simulator"
    ):
        """Handle WebSocket connections (VoIP client)."""
        connection_id = None
        session_id = None
        
        try:
            # Accept the WebSocket connection
            await websocket.accept()
            connection_id = gen_uuid_16()
            
            # Create call session in database
            session_id = await CallHandler.create_call_session(
                phone_number=f"websocket-{connection_id[:8]}", 
                provider_name=provider_name
            )
            
            logger.info(f"New Voice WebSocket connection established: {connection_id}, session: {session_id}")
            
            # Respond with connection confirmation
            await websocket.send_json({
                "type": "connection_confirmed",
                "connection_id": connection_id,
                "session_id": session_id,
                "server_time": time.time(),
                "provider": provider_name
            })
            
            # Define callback for transcription results
            async def transcript_callback(result):
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                    
                # Send transcript to client
                await websocket.send_json({
                    "type": "transcription",
                    "connection_id": connection_id,
                    "session_id": session_id,
                    "text": result["text"],
                    "is_final": result["is_final"]
                })
                
                # Process text for response
                text = result.get("text", "").strip()
                if not text or len(text) < 5:
                    return
                
                # Debounce responses
                current_time = time.time()
                if hasattr(transcript_callback, "last_response_time"):
                    time_since_last = current_time - transcript_callback.last_response_time
                    if time_since_last < 5.0:  # Wait at least 5 seconds between responses
                        return
                transcript_callback.last_response_time = current_time
                
                try:
                    # Process text through NLU
                    db = SessionLocal()
                    try:
                        # TODO: Analyze results
                        nlu_results, response_text = intent_processor.process_text(
                            text=text,
                            session_id=session_id,
                            db=db
                        )
                        
                        # Skip if no meaningful response
                        if not response_text or response_text.strip() == "":
                            return
                        
                        # Send the text response
                        await websocket.send_json({
                            "type": "response",
                            "text": response_text
                        })
                        
                        # Generate and send TTS audio
                        tts_provider = get_tts_provider()
                        audio_content = tts_provider.synthesize(response_text)
                        await websocket.send_bytes(audio_content)
                        
                        logger.info(f"Sent voice response: {response_text[:50]}...")
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Error generating response: {str(e)}")
            
            # Static timestamp (Unix time) that tracks when we last sent a TTS response
            # Enables debouncing: if current_time - last_response_time < 5.0, skip response
            # Example: last_response_time=1000, current_time=1003 → 3s < 5s → no response
            # Set to 0 initially so first call always passes time check
            transcript_callback.last_response_time = 0
            
            # Connect to the audio stream manager
            await stream_manager.connect(
                websocket=websocket,
                session_id=session_id,
                connection_id=connection_id,
                language=language,
                model_name=model,
                callback=transcript_callback
            )
            
            # Send welcome message
            tts_provider = get_tts_provider()
            greeting_text = "Welcome to Zeipo AI. How can I help you today?"
            
            await websocket.send_json({
                "type": "greeting",
                "text": greeting_text
            })
            
            audio_content = tts_provider.synthesize(greeting_text)
            await websocket.send_bytes(audio_content)
            
            # Recieve initial greeting message
            greeting_msg = await websocket.receive()
            logger.debug(f"Received test data: {greeting_msg}, {type(greeting_msg)}")
            
            # Process incoming audio stream
            async for data in websocket.iter_bytes():
                if data:
                    await stream_manager.receive_audio(connection_id, data)
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}, session: {session_id}")
        
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {str(e)}", exc_info=True)
        
        finally:
            # Clean up
            if connection_id:
                try:
                    final_results = await stream_manager.disconnect(connection_id)
                    logger.info(f"Disconnected WebSocket: {connection_id}")
                except Exception as e:
                    logger.error(f"Error disconnecting: {str(e)}")

@router.post("/voice")
async def voice_webhook(request: Request):
    """Handle Africa's Talking voice webhook - routes to Asterisk"""  
    # Set the telephony provider to Africa's Talking (Default)
    settings.TELEPHONY_PROVIDER = "at"
    
    return await CallHandler.handle_webhook(request)

@router.websocket("/voice/ws")
async def websocket_voice_endpoint(
    websocket: WebSocket, 
    language: Optional[str] = None,
    model: str = "small",
    provider: Optional[str] = None
):
    """WebSocket endpoint for voice calls"""
    provider_name = provider or settings.TELEPHONY_PROVIDER
    await CallHandler.handle_websocket(
        websocket=websocket,
        language=language,
        model=model,
        provider_name=provider_name
    )

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
    content_type = "application/xml" if provider_name == "at" else "application/json"
    
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
    phone_number: str,
    caller_id: str = "Zeipo AI",
):
    """
    Make an outbound call using the configured telephony provider.
    
    Args:
        phone_number: Phone number to call
        caller_id: Name to display as caller ID
    
    Returns:
        Call response details
    """
    try:
        """Make an outbound call via Asterisk"""
        if not ari_client:
            logger.error("Cannot make outbound call - ARI client not initialized")
            return False
            
        try:
            # Create origination channel
            channel = ari_client.client.channels.originate(
                endpoint=f"SIP/{phone_number}@africas-talking",
                app=ari_client.app_name,
                appArgs=f"outbound,{phone_number}",
                callerId=caller_id or "Zeipo AI <254700000000>"
            )
            
            logger.info(f"Initiated outbound call to {phone_number} with channel ID {channel.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to make outbound call: {str(e)}", exc_info=True)
            return False
        
    except Exception as e:
        logger.error(f"Error making outbound call: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to make call: {str(e)}")
    