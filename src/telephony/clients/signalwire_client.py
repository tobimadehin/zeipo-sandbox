# src/telephony/clients/signalwire_client.py
from src.telephony.clients.freeswitch_esl import FreeSwitchESL
import asyncio
import json
import threading
import time
import uuid
import websockets
import requests
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from config import settings
from static.constants import logger

class SignalWireClient:
    """
    Client for interacting with FreeSWITCH via ESL.
    Serves as the low-level interface that the SignalWireProvider uses.
    """
    
    def __init__(self):
        """Initialize the SignalWire client with configuration."""
        # Create FreeSWITCH ESL client
        self.esl_client = FreeSwitchESL(
            host=settings.SIGNALWIRE_HOST,
            port=settings.FREESWITCH_PORT,
            password=settings.FREESWITCH_PASSWORD
        )
        
        # Event handling
        self.event_callbacks = {}
        self.active_calls = {}
        
        # Forward ESL callbacks to our callbacks
        self.esl_client.register_callback("call.created", self._on_esl_call_created)
        self.esl_client.register_callback("call.answered", self._on_esl_call_answered)
        self.esl_client.register_callback("call.ended", self._on_esl_call_ended)
        self.esl_client.register_callback("call.dtmf", self._on_esl_call_dtmf)
        self.esl_client.register_callback("call.speech", self._on_esl_call_speech)
        
        logger.info("SignalWire client initialized")
    
    # Add ESL event handlers
    def _on_esl_call_created(self, data):
        """Handle call created event from ESL."""
        self.active_calls[data["session_id"]] = {
            "caller_id": data.get("caller_id"),
            "direction": data.get("direction"),
            "start_time": datetime.now(),
            "state": "created",
            "session_id": data["session_id"]
        }
        
        self._trigger_callback("call.created", data)
    
    def _on_esl_call_answered(self, data):
        """Handle call answered event from ESL."""
        if data["session_id"] in self.active_calls:
            self.active_calls[data["session_id"]]["state"] = "answered"
            self.active_calls[data["session_id"]]["answer_time"] = datetime.now()
        
        self._trigger_callback("call.answered", data)
    
    def _on_esl_call_ended(self, data):
        """Handle call ended event from ESL."""
        if data["session_id"] in self.active_calls:
            del self.active_calls[data["session_id"]]
        
        self._trigger_callback("call.ended", data)
    
    def _on_esl_call_dtmf(self, data):
        """Handle DTMF event from ESL."""
        self._trigger_callback("call.dtmf", data)
    
    def _on_esl_call_speech(self, data):
        """Handle speech event from ESL."""
        self._trigger_callback("call.speech", data)
    
    def _trigger_callback(self, event_type: str, data: Dict[str, Any]):
        """Trigger registered callbacks for an event type."""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback: {str(e)}", exc_info=True)
    
    def register_callback(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for a specific event type."""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        
        self.event_callbacks[event_type].append(callback)
        return True
    
    def make_call(self, destination: str, caller_id: str = None, variables: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Initiate an outbound call through FreeSWITCH.
        """
        variables = variables or {}
        variables["origination_caller_id_number"] = caller_id or "Zeipo AI"
        
        # Add custom session ID if provided
        if "session_id" in variables:
            session_id = variables["session_id"]
        else:
            session_id = f"out_{uuid.uuid4().hex[:12]}"
            variables["session_id"] = session_id
        
        # Make the call using ESL
        result = self.esl_client.originate_call(destination, caller_id, variables)
        
        # Track call in our active calls
        if result.get("status") == "success":
            self.active_calls[session_id] = {
                "caller_id": caller_id,
                "direction": "outbound",
                "start_time": datetime.now(),
                "state": "created",
                "session_id": session_id
            }
        
        return result
    
    def hangup_call(self, session_id: str) -> bool:
        """
        Hang up an active call.
        """
        result = self.esl_client.hangup_call(session_id)
        
        # Remove from active calls if successful
        if result and session_id in self.active_calls:
            del self.active_calls[session_id]
        
        return result
    
    def speak_text(self, session_id: str, text: str, voice: str = "kal") -> bool:
        """
        Speak text on an active call using TTS.
        """
        return self.esl_client.speak_text(session_id, text, voice)
    
    def create_webrtc_session(self, session_id: str, sdp_offer: str) -> Optional[Dict[str, Any]]:
        """
        Create a WebRTC session.
        """
        return self.esl_client.create_webrtc_session(session_id, sdp_offer)
    
    def add_ice_candidate(self, session_id: str, candidate: Dict[str, Any]) -> bool:
        """
        Add an ICE candidate to a WebRTC session.
        
        Args:
            session_id: The session ID
            candidate: ICE candidate object
            
        Returns:
            True if successful, False otherwise
        """
        if not hasattr(self.esl_client, 'add_ice_candidate'):
            # Implement this in FreeSwitchESL class
            logger.warning("ICE candidate handling not implemented")
            return False
        
        return self.esl_client.add_ice_candidate(session_id, candidate)

    def get_ice_candidates(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get ICE candidates from FreeSWITCH for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            List of ICE candidates
        """
        if not hasattr(self.esl_client, 'get_ice_candidates'):
            # Implement this in FreeSwitchESL class
            logger.warning("ICE candidate retrieval not implemented")
            return []
    
        return self.esl_client.get_ice_candidates(session_id)
    
    def stop(self):
        """Stop the client and clean up resources."""
        self.esl_client.stop()
        logger.info("SignalWire client stopped")
        