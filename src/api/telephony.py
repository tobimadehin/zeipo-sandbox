# app/src/api/telephony.py
import asyncio
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
from ...main import ari_client  

stream_manager = AudioStreamManager()
intent_processor = IntentProcessor()

router = APIRouter(prefix="/telephony")

# Add these models for WebRTC signaling
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
    settings.TELEPHONY_PROVIDER = "signalwire"
    
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
        
        # Special handling for Asterisk if needed
        if provider_name == "asterisk" and ari_client:
            # Ensure ARI client is set on provider if it's AsteriskProvider
            if hasattr(telephony_provider, 'set_ari_client') and not telephony_provider.ari_client:
                telephony_provider.set_ari_client(ari_client)
            
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
    
# Add ARI/Asterisk-specific routes
@router.post("/asterisk/events/{event_type}")
async def asterisk_events(
    event_type: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook for Asterisk ARI events.
    This endpoint receives events directly from Asterisk ARI.
    
    Args:
        event_type: Type of event (e.g., StasisStart, StasisEnd, etc.)
        request: The request object
    """
    # Get the request data
    data = await request.json()
    
    logger.info(f"Received Asterisk {event_type} event: {data}")
    
    # Update telephony provider to Asterisk (for this request)
    settings.TELEPHONY_PROVIDER = "asterisk"
    
    try:
        # Handle the event based on its type
        if event_type == "StasisStart":
            # A new call entered the Stasis application
            channel_id = data.get("channel", {}).get("id")
            caller_id = data.get("channel", {}).get("caller", {}).get("number")
            
            # Create a session ID for this call
            session_id = gen_uuid_12()
            
            # Create a call session in the database
            await CallHandler.create_call_session(
                phone_number=caller_id or "asterisk-direct",
                provider_name="asterisk", 
                session_id=session_id
            )
            
            # Return a successful response
            return {"status": "success", "session_id": session_id, "channel_id": channel_id}
            
        elif event_type == "StasisEnd":
            # Call left the Stasis application
            channel_id = data.get("channel", {}).get("id")
            
            # Find session by channel ID and update its status
            # This is a simplified approach - in a real implementation, you'd store
            # the mapping between channel_id and session_id
            
            return {"status": "success", "message": "Call ended"}
            
        elif event_type == "ChannelDtmfReceived":
            # DTMF digit received
            channel_id = data.get("channel", {}).get("id")
            digit = data.get("digit")
            
            # Process the DTMF digit
            # This would normally trigger some application logic
            
            return {"status": "success", "channel_id": channel_id, "digit": digit}
        
        else:
            # Other event types
            return {"status": "success", "event_type": event_type}
    
    except Exception as e:
        logger.error(f"Error handling Asterisk event: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# Add WebRTC signaling endpoints for web client
@router.post("/webrtc/offer")
async def webrtc_offer(signal: WebRTCSignal):
    """
    Receive WebRTC offer from client.
    
    Args:
        signal: The WebRTC offer signal
    """
    if not ari_client:
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": "ARI client not available"}
        )
    
    try:
        # Generate session ID if not provided
        session_id = signal.session_id or gen_uuid_12()
        
        # Validate SDP offer
        if not signal.sdp:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing SDP offer"}
            )
            
        # Create a dynamic Asterisk WebRTC endpoint via ARI
        headers = {"Content-Type": "application/json"}
        endpoint_name = f"WebRTC_{session_id}"
        
        # First create a PJSIP endpoint 
        endpoint_params = {
            "tech": "PJSIP",
            "resource": endpoint_name,
            "variables": {
                "endpoint_name": "webrtc-endpoint",  # Use template from pjsip.conf
                "session_id": session_id,
                "caller_id": f"WebRTC Client <{endpoint_name}>"
            }
        }
        
        # Create the endpoint via ARI
        endpoint_url = f"{settings.ASTERISK_ARI_URL}/endpoints/create"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint_url,
                json=endpoint_params,
                headers=headers,
                auth=aiohttp.BasicAuth(
                    settings.ASTERISK_ARI_USERNAME,
                    settings.ASTERISK_ARI_PASSWORD
                )
            ) as response:
                endpoint_result = await response.json()
                if response.status != 200:
                    raise Exception(f"Failed to create endpoint: {endpoint_result}")
        
        # Now create a channel using this endpoint
        channel_params = {
            "endpoint": f"PJSIP/{endpoint_name}",
            "app": ari_client.app_name,
            "appArgs": f"session_{session_id}",
            "variables": {
                "PJSIP_MEDIA_OFFER": signal.sdp,
                "JITTERBUFFER(fixed)": "60",
                "CHANNEL_DIRECTION": "inbound"
            }
        }
        
        # Create the channel via ARI
        channel_url = f"{settings.ASTERISK_ARI_URL}/channels"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                channel_url,
                json=channel_params,
                headers=headers,
                auth=aiohttp.BasicAuth(
                    settings.ASTERISK_ARI_USERNAME,
                    settings.ASTERISK_ARI_PASSWORD
                )
            ) as response:
                channel_result = await response.json()
                if response.status != 200:
                    raise Exception(f"Failed to create channel: {channel_result}")
        
        # Get channel ID and extract SDP answer
        channel_id = channel_result.get("id")
        
        # Get the SDP answer from the channel's media offer
        media_url = f"{settings.ASTERISK_ARI_URL}/channels/{channel_id}/media"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                media_url,
                headers=headers,
                auth=aiohttp.BasicAuth(
                    settings.ASTERISK_ARI_USERNAME,
                    settings.ASTERISK_ARI_PASSWORD
                )
            ) as response:
                media_result = await response.json()
                if response.status != 200:
                    raise Exception(f"Failed to get media info: {media_result}")
        
        # Extract SDP answer
        sdp_answer = media_result.get("answer", {}).get("sdp")
        if not sdp_answer:
            # Give Asterisk a moment to generate the answer and try again
            await asyncio.sleep(1)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    media_url,
                    headers=headers,
                    auth=aiohttp.BasicAuth(
                        settings.ASTERISK_ARI_USERNAME,
                        settings.ASTERISK_ARI_PASSWORD
                    )
                ) as response:
                    media_result = await response.json()
                    sdp_answer = media_result.get("answer", {}).get("sdp")
        
        if not sdp_answer:
            raise Exception("Failed to get SDP answer from Asterisk")
        
        # Store channel info in ari_client for future reference
        if hasattr(ari_client, 'active_calls'):
            ari_client.active_calls[channel_id] = {
                'channel': None,  # Will be populated by Stasis
                'caller_id': "webrtc-client",
                'start_time': time.time(),
                'state': 'new',
                'session_id': session_id,
                'is_webrtc': True
            }
        
        # Log the successful WebRTC offer handling
        logger.info(f"Created WebRTC endpoint for session {session_id}, channel {channel_id}")
        
        # Return SDP answer to client
        return {
            "status": "success",
            "session_id": session_id,
            "channel_id": channel_id,
            "type": "answer",
            "sdp": sdp_answer
        }
        
    except Exception as e:
        logger.error(f"Error processing WebRTC offer: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/webrtc/ice-candidate")
async def webrtc_ice_candidate(signal: WebRTCSignal):
    """
    Handle ICE candidate from WebRTC client and relay to Asterisk.
    """
    if not signal.session_id or not signal.candidate:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing session_id or candidate"}
        )
    
    try:
        # Find channel_id for this session
        channel_id = None
        if ari_client and hasattr(ari_client, 'active_calls'):
            for cid, call_data in ari_client.active_calls.items():
                if call_data.get('session_id') == signal.session_id:
                    channel_id = cid
                    break
        
        if not channel_id:
            logger.warning(f"No channel found for session {signal.session_id}")
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No active channel for this session"}
            )
        
        # Format the ICE candidate for Asterisk
        candidate = signal.candidate
        formatted_candidate = {
            "candidate": candidate.get("candidate"),
            "sdpMid": candidate.get("sdpMid"),
            "sdpMLineIndex": candidate.get("sdpMLineIndex"),
            "usernameFragment": candidate.get("usernameFragment")
        }
        
        # Send the ICE candidate to Asterisk via ARI
        headers = {"Content-Type": "application/json"}
        ice_url = f"{settings.ASTERISK_ARI_URL}/channels/{channel_id}/media/ice"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ice_url,
                json={"candidates": [formatted_candidate]},
                headers=headers,
                auth=aiohttp.BasicAuth(
                    settings.ASTERISK_ARI_USERNAME,
                    settings.ASTERISK_ARI_PASSWORD
                )
            ) as response:
                result = await response.json()
                if response.status != 200:
                    raise Exception(f"Failed to send ICE candidate: {result}")
        
        logger.info(f"Sent ICE candidate for session {signal.session_id}, channel {channel_id}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing ICE candidate: {str(e)}", exc_info=True)
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
            "provider": "asterisk"
        })
        
        # Set up transcript callback for speech processing
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
                            
                            # Find Asterisk channel and play response
                            channel_id = None
                            if ari_client:
                                for cid, call_data in ari_client.active_calls.items():
                                    if call_data.get('session_id') == session_id:
                                        channel_id = cid
                                        break
                                
                                if channel_id:
                                    # Generate TTS and play on the channel
                                    ari_client._play_message(channel_id, response_text)
                                    logger.info(f"Played response on channel {channel_id}")
                    finally:
                        db.close()
        
        # Connect to audio stream manager with callback
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
                # Create Asterisk WebRTC endpoint with the offer
                offer_response = await webrtc_offer(WebRTCSignal(
                    type="offer",
                    sdp=message.get("sdp"),
                    session_id=session_id
                ))
                
                # Send answer back to client
                await websocket.send_json({
                    "type": "webrtc_answer",
                    "sdp": offer_response.get("sdp")
                })
                
            elif msg_type == "ice_candidate":
                # Forward ICE candidate to Asterisk
                await webrtc_ice_candidate(WebRTCSignal(
                    type="candidate",
                    candidate=message.get("candidate"),
                    session_id=session_id
                ))
                
            elif msg_type == "end_call":
                # Terminate the call
                channel_id = None
                if ari_client:
                    for cid, call_data in ari_client.active_calls.items():
                        if call_data.get('session_id') == session_id:
                            channel_id = cid
                            break
                    
                    if channel_id:
                        ari_client._end_call(channel_id)
                
                # Close the WebSocket
                await websocket.close()
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebRTC WebSocket disconnected: {connection_id}")
    
    except Exception as e:
        logger.error(f"Error in WebRTC WebSocket: {str(e)}", exc_info=True)
    
    finally:
        # Clean up connection
        if connection_id and connection_id in stream_manager.active_connections:
            await stream_manager.disconnect(connection_id)
