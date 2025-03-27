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

from ..provider_base import TelephonyProvider
from ..provider_factory import register_provider

class SignalWireProvider(TelephonyProvider):
    """SignalWire telephony provider implementation."""
    
    def __init__(self):
        """Initialize the SignalWire provider."""
        self.fs_client = None
        self.base_url = f"http://{settings.SIGNALWIRE_HOST}:{settings.SIGNALWIRE_PORT}/api/v1"
        self.ws_url = f"ws://{settings.SIGNALWIRE_HOST}:{settings.SIGNALWIRE_EVENT_PORT}"
        self.auth = (settings.SIGNALWIRE_USERNAME, settings.SIGNALWIRE_PASSWORD)
        self.active_calls = {}
        
        # Start event socket listener
        self._start_event_listener()
        
        logger.info(f"SignalWire provider initialized")
    
    def _start_event_listener(self):
        """Start listening for FreeSWITCH events via websocket."""
        async def connect_to_events():
            async with websockets.connect(self.ws_url) as websocket:
                # Auth with FreeSWITCH
                auth_message = f"auth {settings.SIGNALWIRE_PASSWORD}"
                await websocket.send(auth_message)
                response = await websocket.recv()
                
                if "OK" not in response:
                    logger.error(f"Failed to authenticate with SignalWire: {response}")
                    return
                
                # Subscribe to relevant events
                await websocket.send("event plain CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP DTMF")
                
                while True:
                    event = await websocket.recv()
                    self._process_event(event)
        
        # Run the event listener in a separate thread
        import threading
        threading.Thread(target=lambda: asyncio.run(connect_to_events()), daemon=True).start()
    
    def _process_event(self, event_text):
        """Process FreeSWITCH events."""
        # Parse event data
        event_data = {}
        for line in event_text.split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                event_data[key] = value
        
        event_name = event_data.get("Event-Name")
        session_id = event_data.get("Unique-ID")
        
        if not session_id or not event_name:
            return
            
        if event_name == "CHANNEL_CREATE":
            # New call
            caller_id = event_data.get("Caller-Caller-ID-Number")
            direction = "inbound" if event_data.get("Call-Direction") == "inbound" else "outbound"
            
            self.active_calls[session_id] = {
                "caller_id": caller_id,
                "direction": direction,
                "start_time": datetime.now(),
                "state": "created"
            }
            
            # Log call
            log_call_to_file(
                call_sid=session_id,
                phone_number=caller_id,
                direction=direction,
                status="created",
                additional_data={"provider": "signalwire"}
            )
            
        elif event_name == "CHANNEL_ANSWER":
            if session_id in self.active_calls:
                self.active_calls[session_id]["state"] = "answered"
                
                # Log call
                log_call_to_file(
                    call_sid=session_id,
                    phone_number=self.active_calls[session_id].get("caller_id", "unknown"),
                    direction=self.active_calls[session_id].get("direction", "unknown"),
                    status="answered",
                    additional_data={"provider": "signalwire"}
                )
                
        elif event_name == "CHANNEL_HANGUP":
            if session_id in self.active_calls:
                # Calculate duration
                start_time = self.active_calls[session_id].get("start_time")
                duration = None
                if start_time:
                    duration = int((datetime.now() - start_time).total_seconds())
                
                # Log call end
                log_call_to_file(
                    call_sid=session_id,
                    phone_number=self.active_calls[session_id].get("caller_id", "unknown"),
                    direction=self.active_calls[session_id].get("direction", "unknown"),
                    status="hangup",
                    additional_data={
                        "duration": duration,
                        "hangup_cause": event_data.get("Hangup-Cause"),
                        "provider": "signalwire"
                    }
                )
                
                # Remove from active calls
                del self.active_calls[session_id]
                
        elif event_name == "DTMF":
            if session_id in self.active_calls:
                digit = event_data.get("DTMF-Digit")
                if digit:
                    # Log DTMF
                    log_call_to_file(
                        call_sid=session_id,
                        phone_number=self.active_calls[session_id].get("caller_id", "unknown"),
                        direction=self.active_calls[session_id].get("direction", "unknown"),
                        status="dtmf",
                        additional_data={
                            "dtmf_digit": digit,
                            "provider": "signalwire"
                        }
                    )
    
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
            # Generate XML to connect Africa's Talking to SignalWire via SIP
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
        
        # Default to Africa's Talking XML format
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
                "zeipo_session_id": session_id
            }
            
            if say_text:
                variables["zeipo_say_text"] = say_text
            
            # API parameters
            params = {
                "dial_string": dial_string,
                "api_key": settings.SIGNALWIRE_API_KEY,
                "variables": variables
            }
            
            # Use SignalWire API to originate the call
            response = requests.post(
                f"{self.base_url}/calls",
                json=params,
                auth=self.auth
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to make outbound call: {response.text}")
                return {
                    "status": "error",
                    "message": f"API error: {response.text}"
                }
            
            result = response.json()
            
            # Log outbound call
            log_call_to_file(
                call_sid=session_id,
                phone_number=to_number,
                direction="outbound",
                status="initiated",
                additional_data={
                    "caller_id": caller_id,
                    "provider": "signalwire",
                    "fs_uuid": result.get("uuid")
                }
            )
            
            logger.info(f"Initiated outbound call to {to_number} with session ID {session_id}")
            
            return {
                "status": "initiated",
                "session_id": session_id,
                "call_uuid": result.get("uuid"),
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
        # For Africa's Talking, we can't easily validate
        # For SignalWire webhooks, we could check for specific headers
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
        
        # Return standardized call data
        return {
            "session_id": session_id,
            "phone_number": phone_number,
            "direction": direction,
            "is_active": True,
            "provider": "signalwire",
            "raw_data": request_data
        }
    
    def parse_dtmf_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DTMF webhook data.
        """
        # Extract key information
        session_id = request_data.get("sessionId", request_data.get("session_id", "unknown"))
        digits = request_data.get("dtmfDigits", request_data.get("digits", ""))
        
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

# Register the provider
register_provider("signalwire", SignalWireProvider)
