# app/src/api/telephony.py
import asyncio
import json
import time
import aiohttp
from pydantic import BaseModel
from fastapi import (APIRouter, Depends, Request, Response, 
                     HTTPException, WebSocket, WebSocketDisconnect)
from fastapi.websockets import WebSocketState
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from config import settings
from db.session import get_db, SessionLocal
from db.models import Customer, CallSession
from src.nlp.intent_processor import IntentProcessor
from src.telephony import get_telephony_provider
from src.tts import get_tts_provider
from src.utils.helpers import gen_uuid_12, gen_uuid_16
from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager 

# Global variables
stream_manager = AudioStreamManager()
intent_processor = IntentProcessor()
signalwire_client = None

router = APIRouter(prefix="/telephony")

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
        """Handle webhook POST requests (Africa's Talking or SignalWire)."""
        provider = get_telephony_provider()
        
        logger.debug(f"Handling webhook request from provider: {provider}")
        
        # Get the form data
        form_data = await request.form()
        form_dict = {key: form_data[key] for key in form_data}
        
        # Parse call data
        call_data = provider.parse_call_data(form_dict)
        session_id = call_data.get("session_id")
        
        # For SignalWire, route through a dialog application
        if settings.TELEPHONY_PROVIDER == "signalwire":
            # Generate XML that instructs SignalWire to use our dialog script
            dialplan_response = '<?xml version="1.0" encoding="UTF-8"?><Response>'
            dialplan_response += '<GetSpeech action="/api/v1/telephony/speech" speechTimeout="5" playBeep="true">'
            dialplan_response += '<Say>Welcome to Zeipo AI. How can I help you today?</Say>'
            dialplan_response += '</GetSpeech></Response>'
            return Response(content=dialplan_response, media_type="application/xml")
        
        voice_response = provider.build_voice_response(
            say_text="Welcome to Zeipo AI. How can I help you today?" 
        )
        
        return Response(content=voice_response, media_type="application/xml")
    
    
    @router.post("/voice")
    async def voice_webhook(request: Request):
        """Handle Africa's Talking voice webhook - routes to Asterisk"""  
        # Set the telephony provider to signalwire (Default)
        settings.TELEPHONY_PROVIDER = "signalwire"
        
        return await CallHandler.handle_webhook(request)
        
        
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

    
    @router.websocket("/webrtc/ws/{session_id}")
    async def webrtc_websocket(
        websocket: WebSocket, 
        session_id: str,
        language: Optional[str] = None,
        model: str = "small"
    ):
        """
        WebSocket endpoint for WebRTC signaling and audio streaming.
        """
        connection_id = None
        
        try:
            connection_id = gen_uuid_16()
            
            # Accept the WebSocket connection
            await websocket.accept()
            logger.info(f"WebRTC WebSocket connection established: {connection_id}, session: {session_id}")
            
            # Respond with connection confirmation
            await websocket.send_json({
                "type": "connection_confirmed",
                "connection_id": connection_id,
                "session_id": session_id,
                "server_time": time.time(),
                "provider": "signalwire"
            })
            
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
                                if signalwire_client:
                                    signalwire_client.speak_text(session_id, response_text)
                        finally:
                            db.close()
            
            # Connect to audio stream manager
            await stream_manager.connect(
                websocket=websocket,
                session_id=session_id,
                connection_id=connection_id,
                language=language,
                model_name=model,
                callback=transcript_callback
            )
            
            # Main WebSocket message loop
            async for message in websocket.iter_json():
                msg_type = message.get("type")
                
                if msg_type == "webrtc_offer":
                    # Forward SDP offer to SignalWire
                    logger.info(f"Received WebRTC offer for session {session_id}")
                    
                    if signalwire_client:
                        # In real implementation, would create SignalWire WebRTC session
                        # Here we'll just respond with a placeholder
                        await websocket.send_json({
                            "type": "webrtc_answer",
                            "sdp": "v=0\r\no=- 1234567890 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=msid-semantic: WMS\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:someufrag\r\na=ice-pwd:someicepwd\r\na=fingerprint:sha-256 00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF\r\na=setup:actpass\r\na=mid:0\r\na=sendrecv\r\na=rtcp-mux\r\na=rtpmap:111 opus/48000/2\r\na=fmtp:111 minptime=10;useinbandfec=1\r\n"
                        })
                
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
                    
                    if signalwire_client:
                        signalwire_client.hangup_call(session_id)
                    
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
        provider_name = provider or settings.TELEPHONY_PROVIDER
        
        try:
            telephony_provider = get_telephony_provider()
            
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
        
        
@router.websocket("/webrtc/ws/{session_id}")
async def webrtc_websocket(
    websocket: WebSocket, 
    session_id: str,
    language: Optional[str] = None,
    model: str = "small"
):
    """
    WebSocket endpoint for WebRTC signaling and audio streaming.
    """
    connection_id = None
    
    try:
        connection_id = gen_uuid_16()
        
        # Accept the WebSocket connection
        await websocket.accept()
        logger.info(f"WebRTC WebSocket connection established: {connection_id}, session: {session_id}")
        
        # Respond with connection confirmation
        await websocket.send_json({
            "type": "connection_confirmed",
            "connection_id": connection_id,
            "session_id": session_id,
            "server_time": time.time(),
            "provider": "signalwire"
        })
        
        # Get SignalWire client
        sw_provider = get_telephony_provider()
        sw_client = sw_provider.get_client()
        
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
                        # TODO: Process text through NLU
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
                            
                            # Also send via SignalWire TTS
                            if sw_client:
                                sw_client.speak_text(session_id, response_text)
                    finally:
                        db.close()
        
        # Connect to audio stream manager
        await stream_manager.connect(
            websocket=websocket,
            session_id=session_id,
            connection_id=connection_id,
            language=language,
            model_name=model,
            callback=transcript_callback
        )
        
        # Main WebSocket message loop
        async for message in websocket.iter_json():
            msg_type = message.get("type")
            
            if msg_type == "webrtc_offer":
                # Forward SDP offer to SignalWire
                logger.info(f"Received WebRTC offer for session {session_id}")
                
                if sw_client:
                    sdp = message.get("sdp")
                    if sdp:
                        # Create WebRTC session via SignalWire
                        result = sw_client.create_webrtc_session(session_id, sdp)
                        
                        if result and "sdp" in result:
                            await websocket.send_json({
                                "type": "webrtc_answer",
                                "sdp": result["sdp"]
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Failed to create WebRTC session"
                            })
                
            elif msg_type == "ice_candidate":
                # Forward ICE candidate to FreeSWITCH
                logger.info(f"Received ICE candidate for session {session_id}")
                
                # Save the candidate to pass to FreeSWITCH
                candidate = message.get("candidate")
                if sw_client and candidate:
                    # In a real implementation, this would forward to FreeSWITCH
                    # sw_client.add_ice_candidate(session_id, candidate)
                    pass
                
                # Acknowledge receipt of candidate
                await websocket.send_json({
                    "type": "ice_candidate_ack",
                    "success": True
                })
                
                # In a real implementation, FreeSWITCH would also generate
                # its own ICE candidates that we should forward to the client:
                # Simulating a response ICE candidate from FreeSWITCH
                freeswitch_candidate = {
                    "candidate": "candidate:1 1 UDP 2122260223 192.168.1.1 46692 typ host",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0
                }
                
                await websocket.send_json({
                    "type": "ice_candidate",
                    "candidate": freeswitch_candidate
                })
            
            elif msg_type == "audio_data":
                # Process audio data
                audio_data = message.get("data")
                if audio_data:
                    await stream_manager.receive_audio(connection_id, audio_data)
            
            elif msg_type == "end_call":
                # End the call
                logger.info(f"Received end call request for session {session_id}")
                
                if sw_client:
                    sw_client.hangup_call(session_id)
                
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
                