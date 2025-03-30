# src/telephony/integrations/signalwire.py
import os
import uuid
import json
import requests
import asyncio
import websockets
from typing import Dict, List, Optional, Any
import time
from datetime import datetime
import xml.etree.ElementTree as ET

from config import settings
from static.constants import logger
from src.utils.helpers import gen_uuid_12
from src.utils.at_utils import log_call_to_file
from src.telephony.clients.signalwire_client import SignalWireClient
from src.nlp.intent_processor import IntentProcessor
from db.session import SessionLocal
from src.api.telephony import CallHandler
import asyncio
from src.nlp.intent_processor import IntentProcessor
from db.models import CallSession

from src.telephony.provider_base import TelephonyProvider
from src.telephony.provider_factory import register_provider

class SignalWireProvider(TelephonyProvider):
    """SignalWire telephony provider implementation."""
    
    def __init__(self):
        """Initialize the SignalWire provider."""
        self.client = SignalWireClient()
        
        # Register event callbacks
        self.client.register_callback("call.created", self._on_call_created)
        self.client.register_callback("call.answered", self._on_call_answered)
        self.client.register_callback("call.ended", self._on_call_ended)
        self.client.register_callback("call.dtmf", self._on_call_dtmf)
        self.client.register_callback("call.speech", self._on_call_speech)
        
        logger.info(f"SignalWire provider initialized")
    
    def _on_call_created(self, data: Dict[str, Any]):
        """Handle call created event."""
        session_id = data.get("session_id", "unknown")
        caller_id = data.get("caller_id", "unknown")
        direction = data.get("direction", "unknown")
        
        # Create call session in database if it doesn't exist
        try:
            loop = asyncio.new_event_loop()
            session_id = loop.run_until_complete(
                CallHandler.create_call_session(
                    phone_number=caller_id,
                    provider_name="signalwire",
                    session_id=session_id
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"Error creating call session in database: {str(e)}")
        
        # Log call creation
        log_call_to_file(
            call_sid=session_id,
            phone_number=caller_id,
            direction=direction,
            status="created",
            additional_data={"provider": "signalwire"}
        )
        
        logger.info(f"Call created: session_id={session_id}, caller_id={caller_id}")
    
    def _on_call_answered(self, data: Dict[str, Any]):
        """Handle call answered event."""
        session_id = data.get("session_id", "unknown")
        caller_id = data.get("caller_id", "unknown")
        
        # Log call answer
        log_call_to_file(
            call_sid=session_id,
            phone_number=caller_id,
            direction=data.get("direction", "unknown"),
            status="answered",
            additional_data={"provider": "signalwire"}
        )
        
        logger.info(f"Call answered: session_id={session_id}")
        
        # Play initial greeting
        self.client.speak_text(session_id, "Welcome to Zeipo AI. How can I help you today?")
        
        # Start speech recognition
        self.client.start_recognition(session_id)
    
    def _on_call_ended(self, data: Dict[str, Any]):
        """Handle call ended event."""
        session_id = data.get("session_id", "unknown")
        duration = data.get("duration")
        hangup_cause = data.get("hangup_cause", "unknown")
        
        # Log call end
        log_call_to_file(
            call_sid=session_id,
            phone_number=data.get("caller_id", "unknown"),
            direction=data.get("direction", "unknown"),
            status="ended",
            additional_data={
                "provider": "signalwire",
                "duration": duration,
                "hangup_cause": hangup_cause
            }
        )
        
        logger.info(f"Call ended: session_id={session_id}, duration={duration}s, cause={hangup_cause}")
    
    def _on_call_dtmf(self, data: Dict[str, Any]):
        """Handle DTMF input."""
        session_id = data.get("session_id", "unknown")
        digit = data.get("digit", "")
        
        # Log DTMF
        log_call_to_file(
            call_sid=session_id,
            phone_number="unknown",
            direction="unknown",
            status="dtmf",
            additional_data={
                "provider": "signalwire",
                "digit": digit
            }
        )
        
        logger.info(f"DTMF received: session_id={session_id}, digit={digit}")
    
    def _on_call_speech(self, data: Dict[str, Any]):
        """Handle speech recognition results."""
        session_id = data.get("session_id", "unknown")
        text = data.get("text", "")
        
        logger.info(f"Speech recognized: session_id={session_id}, text={text}")
        
        # Process this through your NLU system
        try:
            # Create DB session
            db = SessionLocal()
            try:
                # Process text
                intent_processor = IntentProcessor()
                nlu_results, response_text = intent_processor.process_text(
                    text=text,
                    session_id=session_id,
                    db=db
                )
                
                # Generate response
                if response_text and response_text.strip():
                    self.client.speak_text(session_id, response_text)
                    logger.info(f"Response sent: {response_text[:50]}...")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error processing speech: {str(e)}")
            # Send a fallback response
            self.client.speak_text(session_id, "I'm sorry, I'm having trouble understanding. Could you please try again?")
    
    def build_voice_response(
        self, 
        say_text: Optional[str] = None, 
        play_url: Optional[str] = None, 
        get_digits: Optional[Dict[str, Any]] = None,
        record: bool = False,
        **kwargs
    ) -> str:
        """
        Build a voice response for telephony service.
        Returns XML for Africa's Talking or JSON for direct clients.
        """
        # Check for special case: SIP dialing for Africa's Talking
        if "dial_sip" in kwargs:
            # Generate XML to connect to SignalWire via SIP
            sip_uri = kwargs.get("dial_sip")
            xml_response = '<?xml version="1.0" encoding="UTF-8"?><Response>'
            xml_response += f'<Dial phoneNumbers="" recordCall="true">'
            xml_response += f'<Sip>{sip_uri}</Sip>'
            xml_response += '</Dial></Response>'
            return xml_response
        
        # For direct SignalWire control, use JSON
        if kwargs.get("format", "json") == "json":
            response = {
                "actions": []
            }
            
            if say_text:
                response["actions"].append({
                    "type": "speak",
                    "text": say_text,
                    "voice": kwargs.get("voice_id", "female")
                })
            
            if play_url:
                response["actions"].append({
                    "type": "play",
                    "url": play_url
                })
            
            if get_digits:
                response["actions"].append({
                    "type": "get_digits",
                    "timeout": get_digits.get("config", {}).get("timeout", 30),
                    "terminators": get_digits.get("config", {}).get("finishOnKey", "#"),
                    "max": get_digits.get("config", {}).get("numDigits")
                })
            
            if record:
                response["actions"].append({
                    "type": "record",
                    "terminators": kwargs.get("finishOnKey", "#"),
                    "max_length": kwargs.get("maxLength", 60),
                    "timeout": kwargs.get("timeout", 10)
                })
            
            return json.dumps(response)
        
        # Default to SignalWire XML format
        xml_response = '<?xml version="1.0" encoding="UTF-8"?><Response>'
        
        if say_text:
            xml_response += f'<Say>{say_text}</Say>'
        
        if play_url:
            xml_response += f'<Play url="{play_url}"/>'
        
        if get_digits:
            timeout = get_digits.get("config", {}).get("timeout", 30)
            finish_on_key = get_digits.get("config", {}).get("finishOnKey", "#")
            num_digits = get_digits.get("config", {}).get("numDigits")
            
            xml_response += f'<GetDigits timeout="{timeout}" finishOnKey="{finish_on_key}"'
            if num_digits:
                xml_response += f' numDigits="{num_digits}"'
            xml_response += '>'
            
            if "say" in get_digits:
                xml_response += f'<Say>{get_digits["say"]}</Say>'
            
            if "play" in get_digits:
                xml_response += f'<Play url="{get_digits["play"]}"/>'
            
            xml_response += '</GetDigits>'
        
        if record:
            xml_response += f'<Record/>'
        
        # Add speech recognition for dialog apps
        if kwargs.get("get_speech", False):
            xml_response += '<GetSpeech action="/api/v1/telephony/speech" speechTimeout="5" playBeep="true">'
            xml_response += '</GetSpeech>'
        
        xml_response += '</Response>'
        return xml_response
    
    def make_outbound_call(
        self, 
        to_number: str, 
        caller_id: str = "Zeipo AI", 
        say_text: str = None
    ) -> Dict[str, Any]:
        """
        Make an outbound call using SignalWire.
        """
        try:
            # Create a session_id
            session_id = gen_uuid_12()
            
            # Prepare dial string for FreeSWITCH
            if to_number.startswith("+"):
                # International format - route through Africa's Talking SIP trunk
                dial_string = f"sofia/gateway/africas_talking/{to_number[1:]}"
            else:
                # Use direct SIP if not international (for testing)
                dial_string = f"sofia/external/{to_number}@{settings.SIGNALWIRE_HOST}:5080"
            
            # Additional variables
            variables = {
                "origination_caller_id_number": caller_id,
                "origination_caller_id_name": caller_id,
                "session_id": session_id
            }
            
            if say_text:
                variables["initial_tts"] = say_text
            
            # Make the call via the client
            result = self.client.make_call(
                destination=to_number,
                caller_id=caller_id,
                variables=variables
            )
            
            # Log outbound call
            log_call_to_file(
                call_sid=session_id,
                phone_number=to_number,
                direction="outbound",
                status="initiated",
                additional_data={
                    "caller_id": caller_id,
                    "provider": "signalwire",
                    "say_text": say_text
                }
            )
            
            logger.info(f"Initiated outbound call to {to_number} with session ID {session_id}")
            
            # Return result from client with some additional info
            if isinstance(result, dict) and "status" in result:
                # Client already returned a dict
                result["session_id"] = session_id
                result["provider"] = "signalwire"
                return result
            else:
                # Create a new response
                return {
                    "status": "initiated",
                    "session_id": session_id,
                    "call_uuid": getattr(result, "uuid", None),
                    "to": to_number,
                    "provider": "signalwire"
                }
            
        except Exception as e:
            logger.error(f"Failed to make outbound call: {str(e)}", exc_info=True)
            return {
                "status": "error", 
                "message": str(e)
            }
    
    def is_valid_webhook_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate if an incoming webhook request is authentic.
        """
        # For SignalWire, we can validate based on known parameters
        # In production, you might want to add API key validation or other security measures
        required_fields = []
        
        # For voice webhooks
        if "sessionId" in request_data:
            required_fields = ["sessionId", "callerNumber", "direction"]
        # For speech webhooks
        elif "speechResult" in request_data:
            required_fields = ["sessionId", "speechResult"]
        # For DTMF webhooks
        elif "dtmfDigits" in request_data:
            required_fields = ["sessionId", "dtmfDigits"]
        # For event webhooks
        elif "status" in request_data:
            required_fields = ["sessionId", "status"]
        
        # If we identified the webhook type, validate required fields
        if required_fields:
            return all(field in request_data for field in required_fields)
        
        # Default validation (no specific webhook type identified)
        return True
    
    def parse_call_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming call webhook data.
        """
        # Extract key information from the request
        session_id = request_data.get("sessionId", request_data.get("session_id", gen_uuid_12()))
        phone_number = request_data.get("callerNumber", request_data.get("phone_number", "anonymous"))
        direction = request_data.get("direction", "inbound")
        
        # Log call to file
        log_call_to_file(
            call_sid=session_id,
            phone_number=phone_number,
            direction=direction,
            status="received",
            additional_data={
                "provider": "signalwire",
                "raw_data": request_data
            }
        )
        
        # Speech results handling
        if "speechResult" in request_data:
            speech_text = request_data.get("speechResult", "")
            logger.info(f"Speech detected for session {session_id}: {speech_text}")
            
            # Process speech through NLU if applicable
            try:
                # Create DB session
                db = SessionLocal()
                try:
                    # Process text
                    intent_processor = IntentProcessor()
                    nlu_results, response_text = intent_processor.process_text(
                        text=speech_text,
                        session_id=session_id,
                        db=db
                    )
                    
                    # Store the response text for later use
                    request_data["nlu_response"] = response_text
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error processing speech through NLU: {str(e)}")
        
        # Return standardized call data
        return {
            "session_id": session_id,
            "phone_number": phone_number,
            "direction": direction,
            "is_active": True,
            "provider": "signalwire",
            "speech_text": request_data.get("speechResult"),
            "nlu_response": request_data.get("nlu_response"),
            "raw_data": request_data
        }
    
    def parse_dtmf_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DTMF webhook data.
        """
        # Extract key information
        session_id = request_data.get("sessionId", request_data.get("session_id", "unknown"))
        digits = request_data.get("dtmfDigits", request_data.get("digits", ""))
        
        # Process DTMF with SignalWire client if configured
        # Note: In real implementation, this would trigger application logic
        if hasattr(self, 'client') and session_id != "unknown":
            try:
                # Log DTMF to SignalWire logs
                logger.info(f"DTMF input for session {session_id}: {digits}")
                
                # You could trigger specific logic here based on the digits
                # For example, if "1" is for a specific menu option:
                if digits == "1":
                    # Option 1 selected - e.g., speak a specific message
                    self.client.speak_text(session_id, "You've selected option 1.")
                elif digits == "2":
                    # Option 2 selected
                    self.client.speak_text(session_id, "You've selected option 2.")
                # etc.
            except Exception as e:
                logger.error(f"Error processing DTMF with SignalWire: {str(e)}")
        
        # Log DTMF to file
        log_call_to_file(
            call_sid=session_id,
            phone_number="unknown",
            direction="inbound",
            status="dtmf",
            additional_data={
                "dtmf_digits": digits,
                "provider": "signalwire",
                "raw_data": request_data
            }
        )
        
        return {
            "session_id": session_id,
            "digits": digits,
            "provider": "signalwire",
            "raw_data": request_data
        }
    
    def parse_event_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse call event webhook data.
        """
        # Extract key information
        session_id = request_data.get("sessionId", request_data.get("session_id", "unknown"))
        status = request_data.get("status", "unknown")
        duration = request_data.get("durationInSeconds", request_data.get("duration"))
        
        # Handle call completion for database updates
        if status in ["completed", "failed", "no-answer", "busy", "rejected"]:
            try:      
                # Create DB session
                db = SessionLocal()
                try:
                    # Find call session in database
                    call_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()
                    
                    if call_session:
                        # Update with end time and duration
                        call_session.end_time = datetime.now()
                        if duration is not None:
                            try:
                                call_session.duration_seconds = int(duration)
                            except ValueError:
                                pass
                        
                        # Save changes
                        db.commit()
                        logger.info(f"Updated call session {session_id} with end time and duration")
                    else:
                        logger.warning(f"Call session not found for {session_id}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error updating call session: {str(e)}")
        
        # Log event to file
        log_call_to_file(
            call_sid=session_id,
            phone_number="unknown",
            direction="unknown",
            status=status,
            additional_data={
                "duration": duration,
                "provider": "signalwire",
                "raw_data": request_data
            }
        )
        
        return {
            "session_id": session_id,
            "status": status,
            "duration": duration,
            "provider": "signalwire",
            "raw_data": request_data
        }
        
    def handle_webrtc_offer(self, session_id, sdp):
        """
        Handle WebRTC offer from browser and connect to FreeSWITCH.
        
        Args:
            session_id: Unique session ID
            sdp: SDP offer from browser
            
        Returns:
            SDP answer from FreeSWITCH
        """
        # Get the FreeSWITCH client
        client = self.get_client()
        
        # Create WebRTC session in FreeSWITCH
        # This would call a method to send the SDP to FreeSWITCH via ESL
        # and get an answer back
        result = client.create_webrtc_session(session_id, sdp)
        
        if result and "sdp" in result:
            return result["sdp"]
        else:
            logger.error(f"Failed to create WebRTC session for {session_id}")
            return None

    def get_client(self):
        """Get the SignalWire client instance."""
        return self.client
    
    def set_client(self, client):
        """Set the SignalWire client instance."""
        self.client = client
        return True
    
    def stop(self) -> None:
        """Stop the provider and clean up resources."""
        # Stop the SignalWire client
        if hasattr(self, 'client') and self.client:
            self.client.stop()
        logger.info("Stopped SignalWire provider")

# Register the provider
register_provider("signalwire", SignalWireProvider)
