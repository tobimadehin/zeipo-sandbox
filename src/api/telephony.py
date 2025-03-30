# app/src/api/telephony.py
import json
import time
from pydantic import BaseModel
from fastapi import (Depends, HTTPException, Request, Response, 
                     WebSocket, WebSocketDisconnect)
from fastapi.websockets import WebSocketState
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from config import settings
from db.session import get_db, SessionLocal
from db.models import Customer, CallSession
from src.api.router import create_router
from src.nlp.intent_processor import IntentProcessor
from src.telephony import get_telephony_provider
from src.telephony.provider_base import TelephonyProvider
from src.telephony.provider_factory import get_telephony_provider_name, set_telephony_provider
from src.utils.helpers import gen_uuid_12, gen_uuid_16
from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager 

# Global variables
stream_manager = AudioStreamManager()
intent_processor = IntentProcessor()

router = create_router("/telephony")

telephony_provider = None
telephony_provider_name = None

class WebRTCSignal(BaseModel):
    """
    Model for WebRTC signaling messages exchanged between client and server.
    
    WebRTC requires a signaling mechanism to coordinate connection establishment
    between peers. This class encapsulates the different types of signaling
    messages exchanged during WebRTC setup:
    
    Attributes:
        type (str): Message type, typically 'offer', 'answer', or 'candidate'.
            - 'offer': Initial SDP offer from the client
            - 'answer': SDP answer from Asterisk
            - 'candidate': ICE candidate for connection negotiation
        
        sdp (Optional[str]): Session Description Protocol data containing media
            capabilities, codecs, and connection information. Present in 'offer'
            and 'answer' messages.
        
        candidate (Optional[Dict[str, Any]]): ICE candidate information for NAT
            traversal, containing network routing options. Includes fields like:
            - candidate: The candidate descriptor string
            - sdpMid: Media stream identifier
            - sdpMLineIndex: Index of the media line
            - usernameFragment: ICE username fragment
        
        session_id (Optional[str]): Unique identifier for the call session,
            used to correlate signaling messages with specific calls.
    
    This model serves as both the request body for incoming WebRTC signals from
    clients and as the internal representation for processing these signals
    before forwarding them to Asterisk.
    """
    type: str
    sdp: Optional[str] = None
    candidate: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

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
            global telephony_provider
            global telephony_provider_name
            telephony_provider = get_telephony_provider()
            telephony_provider_name = get_telephony_provider_name(telephony_provider)
            
            logger.debug(f"Connecting to telephony provider client: {telephony_provider_name}")
            
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
    async def handle_webhook(request: Request, telephony_provider: TelephonyProvider) -> Response:
        """Webhook base method POST requests (Africa's Talking)."""
        
        # Get the form data
        form_data = await request.form()
        form_dict = {key: form_data[key] for key in form_data}
        
        # Parse the call data using the provider
        call_data = telephony_provider.parse_call_data(form_dict)
        _session_id = call_data.get("session_id")
        provider_name = get_telephony_provider_name(telephony_provider)
        
        try:
            # Create call session
            # TODO: Implement factory method for passing different key value 
            # pairs for same intent as they differ accross multiple providers
            phone_number = call_data.get("phone_number", f"anonymous-{gen_uuid_12()}")
            await CallHandler.create_call_session(phone_number, provider_name, _session_id)
            
            voice_response = telephony_provider.build_voice_response(
                say_text="Welcome to Zeipo AI. How can I help you today?" 
            )
            
            return Response(content=voice_response, media_type="application/xml")
            
        except Exception as e:
            logger.error(f"Error handling call webhook: {str(e)}", exc_info=True)
            error_response = telephony_provider.build_voice_response(
                say_text="We're sorry, but an error occurred while processing your call."
            )
            
            return Response(content=error_response, media_type="application/xml")
        
    @staticmethod
    async def handle_webrtc_websocket(websocket: WebSocket, telephony_provider: TelephonyProvider) -> None:
        """
        WebSocket endpoint base method for WebRTC signaling and audio streaming.
        """
        connection_id = None
        session_id = None
        
        try:
            connection_id = gen_uuid_16()
            session_id = gen_uuid_12()
            provider_name = get_telephony_provider_name(telephony_provider)
            
            # Accept the WebSocket connection
            await websocket.accept()
            logger.debug(f"Handling WebRTC WebSocket connection for session {session_id} with {provider_name}")
            
            # Respond with connection confirmation
            await websocket.send_json({
                "type": "connection_confirmed",
                "connection_id": connection_id,
                "session_id": session_id,
                "server_time": time.time(),
                "provider": "signalwire"
            })
            
            voice_response = telephony_provider.build_voice_response(
                say_text="Welcome to Zeipo AI. How can I help you today?" 
            )
            
            # Set up transcript callback
            async def transcript_callback(result):
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                    
                # Send transcript to client
                await websocket.send_json({
                    "type": "transcription",
                    "text": result["text"],
                    "is_final": result["is_final"]
                })
                
                # Process intent and generate response for final transcripts
                if result.get("is_final", False):
                    text = result.get("text", "").strip()
                    if text and len(text) > 5:
                        # Process through NLU
                        db = SessionLocal()
                        try:
                            # TODO: Analyze the results
                            nlu_results, response_text = intent_processor.process_text(
                                text=text,
                                session_id=session_id,
                                db=db
                            )
                            
                            if response_text and response_text.strip():
                                # Send text response to client
                                await websocket.send_json({
                                    "type": "response",
                                    "text": response_text
                                })
                                
                                # Also send via SignalWire TTS if available
                                if telephony_provider:
                                    telephony_provider.speak_text(session_id, response_text)
                        finally:
                            db.close()
            
            # Connect to audio stream manager
            await stream_manager.connect(
                websocket=websocket,
                session_id=session_id,
                connection_id=connection_id,
                callback=transcript_callback
            )
            
            # Main WebSocket message loop
            async for message in websocket.iter_json():
                msg_type = message.get("type")
                
                if msg_type == "webrtc_offer":
                    # Forward SDP offer to SignalWire
                    logger.info(f"Received WebRTC offer for session {session_id}")
                    
                    # For debugging/testing, send back a simple SDP answer
                    # This is a placeholder - in production this would come from FreeSWITCH
                    sdp =   "v=0\r\n" + \
                            "o=- 12345 12345 IN IP4 127.0.0.1\r\n" + \
                            "s=FreeSWITCH\r\n" + \
                            "c=IN IP4 203.0.113.1\r\n" + \
                            "t=0 0\r\n" + \
                            "m=audio 16000 RTP/SAVPF 111\r\n" + \
                            "a=rtpmap:111 opus/48000/2\r\n" + \
                            "a=fmtp:111 minptime=10;useinbandfec=1\r\n" + \
                            "a=sendrecv\r\n" + \
                            "a=ice-ufrag:random123\r\n" + \
                            "a=ice-pwd:randompassword123\r\n" + \
                            "a=fingerprint:sha-256 AB:CD:EF:12:34:56:78:90:AB:CD:EF:12:34:56:78:90:AB:CD:EF:12:34:56:78:90:AB:CD:EF:12:34:56:78:90\r\n" 
                            
                    if telephony_provider:
                        logger.debug(f"Sending SDP answer to SignalWire for session {session_id}")
                        # In real implementation, would create SignalWire WebRTC session
                        # Here we'll just respond with a placeholder
                        await websocket.send_json({
                            "type": "webrtc_answer",
                            "sdp": sdp
                        })
                    else:
                        logger.warning("SignalWire client not available, cannot send SDP answer")
                
                elif msg_type == "ice_candidate":
                    # Forward ICE candidate
                    logger.info(f"Received ICE candidate for session {session_id}")
                    
                    # In real implementation would send to SignalWire
                    pass
                
                elif msg_type == "audio_data":
                    # Process audio data
                    audio_data = message.get("data")
                    if audio_data:
                        await stream_manager.receive_audio(connection_id, audio_data)
                
                elif msg_type == "end_call":
                    # End the call
                    logger.info(f"Received end call request for session {session_id}")
                    
                    if telephony_provider:
                        telephony_provider.hangup_call(session_id)
                    
                    # Close the WebSocket
                    await websocket.close()
                    break
        
        except WebSocketDisconnect:
            logger.info(f"WebRTC WebSocket disconnected: {connection_id}")
        
        except Exception as e:
            logger.error(f"Error in WebRTC WebSocket: {str(e)}", exc_info=True)
        
        finally:
            # Clean up
            if connection_id:
                try:
                    await stream_manager.disconnect(connection_id)
                    logger.info(f"Disconnected WebRTC WebSocket: {connection_id}")
                except Exception as e:
                    logger.error(f"Error disconnecting WebRTC WebSocket: {str(e)}")
        
    @router.post("/speech")
    async def speech_webhook(request: Request):
        """Handle speech recognition results from SignalWire"""
        form_data = await request.form()
        form_dict = {key: form_data[key] for key in form_data}
        
        logger.debug(f"Received speech recognition results: {json.dumps(form_dict, indent=4, sort_keys=True)}")
        
        # Extract session ID and speech text
        session_id = form_dict.get("sessionId", "unknown")
        speech_text = form_dict.get("speechResult", "")
        
        logger.info(f"Received speech: {speech_text} for session {session_id}")
        
        # Process speech through NLU
        db = SessionLocal()
        try:
            # TODO: Process the speech text
            nlu_results, response_text = intent_processor.process_text(
                text=speech_text,
                session_id=session_id,
                db=db
            )
            
            # Generate response XML
            xml_response = '<?xml version="1.0" encoding="UTF-8"?><Response>'
            xml_response += f'<Say>{response_text}</Say>'
            xml_response += '<GetSpeech action="/api/v1/telephony/speech" speechTimeout="5">'
            xml_response += '</GetSpeech></Response>'
            
            return Response(content=xml_response, media_type="application/xml")
        except Exception as e:
            logger.error(f"Error processing speech: {str(e)}")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Sorry, I encountered an error.</Say></Response>',
                media_type="application/xml"
            )
        finally:
            db.close()

    
    @router.websocket("/webrtc/ws")
    async def webrtc_websocket(websocket: WebSocket):
        """Handle WebRTC WebSocket connections"""
        from src.telephony.integrations.signalwire import SignalWireProvider
        
        telephony_provider = get_telephony_provider() 
        
        if get_telephony_provider_name(telephony_provider) != SignalWireProvider.__class__.__name__:
            telephony_provider = set_telephony_provider("signalwire")
        
        await CallHandler.handle_webrtc_websocket(websocket, telephony_provider)
        
    
    # This is a secondary entry point for handling incoming calls
    # to Zeipo API via webhooks (Africa's Talking HTTP callbacks).
    # 
    # The primary entry point for calls is via FreeSWITCH SIP trunking,
    # which provides more reliable and efficient voice connectivity.
    # This webhook approach can be used for:
    # - Testing without SIP infrastructure
    # - Hybrid deployments with both SIP and webhook methods
    # - Development and debugging
    @router.post("/voice")
    async def voice_webhook(request: Request):
        """Handle call routing from Africa's Talking voice via webhook"""
        from src.telephony.integrations.at import AfricasTalkingProvider
        
        if not settings.WEBHOOK_ENTRY:
            error = "Webhook entry is disabled. Use FreeSWITCH as main entry point."
            
            logger.fatal(error)
            raise HTTPException(status_code=403, detail=error)
        
        # Override the existing telephony provider to use Africa's 
        # Talking directly without FreeSWITCH SIP trunking.
        telephony_provider = get_telephony_provider() 
        
        # TODO: Figure out why it doesn't detect the equal names to 
        # prevent un-necessary re-initialization of the provider.
        logger.debug(f"Current Telephony provider is: {get_telephony_provider_name(telephony_provider)}")
        
        if get_telephony_provider_name(telephony_provider) != AfricasTalkingProvider.__class__.__name__:
            telephony_provider = set_telephony_provider("at")
        
        logger.debug(f"Telephony provider is: {get_telephony_provider_name(telephony_provider)}")
        
        return await CallHandler.handle_webhook(request, telephony_provider)

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
        say_text: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Make an outbound call using the configured telephony provider.
        
        Args:
            phone_number: Phone number to call
            caller_id: Name to display as caller ID
            say_text: Text to speak when the call is answered
            provider: Override the default telephony provider
        
        Returns:
            Call response details
        """
        try:
            telephony_provider = get_telephony_provider()
            provider_name = get_telephony_provider_name(telephony_provider)
            
            # Make the call
            call_response = telephony_provider.make_outbound_call(
                to_number=phone_number,
                caller_id=caller_id,
                say_text=say_text
            )
            
            return call_response
            
        except Exception as e:
            logger.error(f"Error making outbound call: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)}
            )
        