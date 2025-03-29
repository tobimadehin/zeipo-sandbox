# app/src/telephony/integrations/at.py
import os
import uuid
import json
from typing import Dict, List, Optional, Any
import africastalking
from config import settings
from static.constants import logger
from src.utils.helpers import gen_uuid_12
from src.tts import get_tts_provider
from src.utils.at_utils import log_call_to_file

from src.telephony.provider_base import TelephonyProvider
from src.telephony.provider_factory import register_provider

class AfricasTalkingProvider(TelephonyProvider):
    """Africa's Talking telephony provider implementation."""
    
    def __init__(self):
        """Initialize the Africa's Talking SDK."""
        # Initialize Africa's Talking SDK
        africastalking.initialize(settings.AT_USER, settings.AT_API_KEY)
        self.voice = africastalking.Voice
        logger.info(f"Africa's Talking provider initialized with user: {settings.AT_USER}")
    
    def build_voice_response(
        self, 
        say_text: Optional[str] = None, 
        play_url: Optional[str] = None, 
        get_digits: Optional[Dict[str, Any]] = None,
        record: bool = False,
        **kwargs
    ) -> str:
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
            try:
                # Generate TTS audio
                tts_provider = get_tts_provider()
                audio_content = tts_provider.synthesize(
                    say_text, 
                    voice_id=kwargs.get("voice_id"),
                    language_code=kwargs.get("language_code")
                )
                
                # Save to file
                filename = f"tts_{gen_uuid_12()}.mp3"
                output_dir = "data/tts_output"
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, filename)
                
                tts_provider.save_to_file(audio_content, file_path)
                
                # Use the webhook base URL to create a public URL
                audio_url = f"{settings.BASE_URL}{settings.API_V1_STR}/tts/audio/{filename}"
                
                # Use Play instead of Say for TTS audio
                response += f'<Play url="{audio_url}"/>'
            except Exception as e:
                logger.error(f"Error using TTS in AT response: {str(e)}")
                # Fallback to Say if TTS fails
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
    
    def make_outbound_call(
        self, 
        to_number: str, 
        client_name: str = "Zeipo AI", 
        say_text: str = None
    ) -> Dict[str, Any]:
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
            callback_url = f"{settings.BASE_URL}{settings.API_V1_STR}/at/events"
            
            # Build response XML if say_text is provided
            xml = None
            if say_text:
                xml = self.build_voice_response(say_text=say_text)
            
            # Make the call
            call_response = self.voice.call(
                callFrom=settings.AT_PHONE,
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
    
    def is_valid_webhook_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate if an incoming webhook request is authentic.
        For Africa's Talking, assume all requests are valid for now
        since they don't provide easy webhook validation.
        
        Args:
            request_data: The webhook request data
            
        Returns:
            True for all requests currently
        """
        # In a production system, you would validate the request
        # based on Africa's Talking documentation
        return True
    
    def parse_call_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming call webhook data from Africa's Talking.
        
        Args:
            request_data: Raw webhook data from Africa's Talking
            
        Returns:
            Standardized call data dictionary
        """
        # Log the raw data
        session_id = request_data.get("sessionId", "unknown")
        phone_number = request_data.get("callerNumber", "anonymous")
        direction = request_data.get("direction", "inbound")
        
        # Log call to file
        log_call_to_file(
            call_sid=session_id,
            phone_number=phone_number,
            direction=direction,
            status="received",
            additional_data=request_data
        )
        
        # Return standardized call data
        return {
            "session_id": session_id,
            "phone_number": phone_number,
            "direction": direction,
            "is_active": request_data.get("isActive", "1") == "1",
            "provider": "at",
            "raw_data": request_data
        }
    
    def parse_dtmf_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DTMF webhook data from Africa's Talking.
        
        Args:
            request_data: Raw webhook data from Africa's Talking
            
        Returns:
            Standardized DTMF data dictionary
        """
        session_id = request_data.get("sessionId", "unknown")
        digits = request_data.get("dtmfDigits", "")
        
        # Log DTMF to file
        log_call_to_file(
            call_sid=session_id,
            phone_number="unknown",
            direction="inbound",
            status="dtmf",
            additional_data={"dtmf_digits": digits, **request_data}
        )
        
        return {
            "session_id": session_id,
            "digits": digits,
            "provider": "at",
            "raw_data": request_data
        }
    
    def parse_event_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse call event webhook data from Africa's Talking.
        
        Args:
            request_data: Raw webhook data from Africa's Talking
            
        Returns:
            Standardized event data dictionary
        """
        session_id = request_data.get("sessionId", "unknown")
        status = request_data.get("status", "unknown")
        duration = request_data.get("durationInSeconds")
        
        # Log event to file
        log_call_to_file(
            call_sid=session_id,
            phone_number="unknown",
            direction="inbound",
            status=status,
            additional_data=request_data
        )
        
        return {
            "session_id": session_id,
            "status": status,
            "duration": int(duration) if duration else None,
            "provider": "at",
            "raw_data": request_data
        }

# Register the provider
register_provider("at", AfricasTalkingProvider)