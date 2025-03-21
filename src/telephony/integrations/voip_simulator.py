# app/src/telephony/providers/voip_simulator.py
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import settings
from static.constants import logger
from src.utils.helpers import gen_uuid_12

from ..provider_base import TelephonyProvider
from ..provider_factory import register_provider

class VoipSimulatorProvider(TelephonyProvider):
    """
    Simulated VoIP telephony provider for testing purposes.
    This provider is designed to work with the Zeipo VoIP Client mobile app.
    """
    
    def __init__(self):
        """Initialize the VoIP simulator provider."""
        logger.info("VoIP Simulator provider initialized")
        
        # Optional: keep track of active calls
        self.active_calls: Dict[str, Dict[str, Any]] = {}
    
    def build_voice_response(
        self, 
        say_text: Optional[str] = None, 
        play_url: Optional[str] = None, 
        get_digits: Optional[Dict[str, Any]] = None,
        record: bool = False,
        **kwargs
    ) -> str:
        """
        Build a JSON response for the VoIP simulator.
        
        Args:
            say_text: Text to be spoken
            play_url: URL of audio file to play
            get_digits: Configuration for collecting digits
            record: Whether to record the call
            **kwargs: Additional parameters for specific actions
        
        Returns:
            JSON string with the voice response
        """
        response = {
            "actions": []
        }
        
        # Add say action if text is provided
        if say_text:
            response["actions"].append({
                "type": "say",
                "text": say_text,
                "voice": kwargs.get("voice_id", "default"),
                "language": kwargs.get("language_code", "en-US")
            })
        
        # Add play action if URL is provided
        if play_url:
            response["actions"].append({
                "type": "play",
                "url": play_url
            })
        
        # Add gather digits action if configured
        if get_digits:
            digits_action = {
                "type": "gather_digits",
                "timeout": get_digits.get("config", {}).get("timeout", 30),
                "finish_on_key": get_digits.get("config", {}).get("finishOnKey", "#"),
                "num_digits": get_digits.get("config", {}).get("numDigits")
            }
            
            # Add nested prompt if provided
            if "say" in get_digits:
                digits_action["prompt"] = {
                    "type": "say",
                    "text": get_digits["say"]
                }
            elif "play" in get_digits:
                digits_action["prompt"] = {
                    "type": "play",
                    "url": get_digits["play"]
                }
            
            response["actions"].append(digits_action)
        
        # Add record action if requested
        if record:
            response["actions"].append({
                "type": "record",
                "finish_on_key": kwargs.get("finishOnKey", "#"),
                "max_length": kwargs.get("maxLength", 10),
                "timeout": kwargs.get("timeout", 10),
                "trim_silence": kwargs.get("trimSilence", True),
                "play_beep": kwargs.get("playBeep", True)
            })
        
        # Add hangup action if requested
        if kwargs.get("hangup", False):
            response["actions"].append({
                "type": "hangup"
            })
        
        # Return the response as a JSON string
        return json.dumps(response)
    
    def make_outbound_call(
        self, 
        to_number: str, 
        client_name: str = "Zeipo AI", 
        say_text: str = None
    ) -> Dict[str, Any]:
        """
        Simulate making an outbound call using VoIP.
        For the simulator, this doesn't actually make a call
        but returns a structured response as if it did.
        
        Args:
            to_number: The phone number to call (client ID in VoIP context)
            client_name: Caller ID to display
            say_text: Text to be spoken when call is answered
        
        Returns:
            Simulated call response
        """
        # Generate a session ID for the call
        session_id = f"voip_{gen_uuid_12()}"
        
        # Record the call in our active calls list
        call_record = {
            "session_id": session_id,
            "to": to_number,
            "from": client_name,
            "status": "initiated",
            "start_time": datetime.now().isoformat(),
            "initial_text": say_text
        }
        
        self.active_calls[session_id] = call_record
        logger.info(f"Initiated simulated outbound call to {to_number}")
        
        # Return a response similar to what a real provider might give
        return {
            "status": "initiated",
            "session_id": session_id,
            "to": to_number,
            "from": client_name,
            "provider": "voip_simulator"
        }
    
    def is_valid_webhook_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate if an incoming webhook request is authentic.
        For the simulator, we'll assume all requests are valid
        since it's just for testing.
        
        Args:
            request_data: The webhook request data
            
        Returns:
            True for all requests from the simulator
        """
        # In a real implementation, I'd validate based on signatures or tokens
        # For testing, we'll just check if the provider field is present
        return request_data.get("provider") == "voip_simulator"
    
    def parse_call_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming call webhook data from VoIP simulator.
        
        Args:
            request_data: Raw webhook data
            
        Returns:
            Standardized call data dictionary
        """
        # Extract key information from the request
        session_id = request_data.get("session_id", f"voip_{gen_uuid_12()}")
        client_id = request_data.get("client_id", "anonymous")
        
        # Log the call (could use your existing log_call_to_file function)
        logger.info(f"Incoming VoIP call: session_id={session_id}, client_id={client_id}")
        
        # Track active call
        self.active_calls[session_id] = {
            "session_id": session_id,
            "client_id": client_id,
            "status": "connected",
            "start_time": datetime.now().isoformat()
        }
        
        # Return standardized call data
        return {
            "session_id": session_id,
            "phone_number": client_id,  # In VoIP context, this is the client ID
            "direction": "inbound",
            "is_active": True,
            "provider": "voip_simulator",
            "raw_data": request_data
        }
    
    def parse_dtmf_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DTMF input data from VoIP simulator.
        
        Args:
            request_data: Raw webhook data
            
        Returns:
            Standardized DTMF data dictionary
        """
        session_id = request_data.get("session_id", "unknown")
        digits = request_data.get("digits", "")
        
        logger.info(f"VoIP DTMF input: session_id={session_id}, digits={digits}")
        
        return {
            "session_id": session_id,
            "digits": digits,
            "provider": "voip_simulator",
            "raw_data": request_data
        }
    
    def parse_event_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse call event data from VoIP simulator.
        
        Args:
            request_data: Raw webhook data
            
        Returns:
            Standardized event data dictionary
        """
        session_id = request_data.get("session_id", "unknown")
        event_type = request_data.get("event", "unknown")
        
        # Map VoIP events to standard status names
        status_mapping = {
            "connect": "in-progress",
            "disconnect": "completed",
            "error": "failed",
            "mute": "muted",
            "unmute": "unmuted"
        }
        
        status = status_mapping.get(event_type, event_type)
        duration = request_data.get("duration")
        
        # Update active calls record
        if session_id in self.active_calls:
            if status == "completed":
                # Call ended, calculate duration if not provided
                if duration is None and "start_time" in self.active_calls[session_id]:
                    start_time = datetime.fromisoformat(self.active_calls[session_id]["start_time"])
                    duration_seconds = (datetime.now() - start_time).total_seconds()
                    duration = int(duration_seconds)
                
                # Remove from active calls
                self.active_calls.pop(session_id, None)
            else:
                # Update status
                self.active_calls[session_id]["status"] = status
        
        logger.info(f"VoIP call event: session_id={session_id}, event={event_type}, status={status}")
        
        return {
            "session_id": session_id,
            "status": status,
            "duration": duration,
            "provider": "voip_simulator",
            "raw_data": request_data
        }

# Register the provider
register_provider("voip_simulator", VoipSimulatorProvider)