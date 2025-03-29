# src/telephony/clients/freeswitch_esl.py
import ESL
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import json
import uuid

from config import settings
from src.utils.helpers import gen_uuid_12, gen_uuid_16
from static.constants import logger

class FreeSwitchESL:
    """
    Client for interacting with FreeSWITCH via Event Socket Library (ESL).
    """
    
    def __init__(self, host=None, port=None, password=None):
        """Initialize the FreeSWITCH ESL client."""
        self.host = host or settings.FREESWITCH_HOST or "localhost"
        self.port = port or settings.FREESWITCH_PORT or 8021
        self.password = password or settings.FREESWITCH_PASSWORD or "ClueCon"
        
        self.esl_connection = None
        self.running = False
        self.event_thread = None
        self.callbacks = {}
        self.active_calls = {}
        
        # Start connection and event listener
        self._connect()
        self._start_event_listener()
        
        logger.info(f"FreeSWITCH ESL client initialized - {self.host}:{self.port}")
    
    def _connect(self):
        """Connect to FreeSWITCH ESL."""
        try:
            self.esl_connection = ESL.ESLconnection(self.host, self.port, self.password)
            if not self.esl_connection.connected():
                logger.error("Failed to connect to FreeSWITCH ESL")
                return False
            
            logger.info("Connected to FreeSWITCH ESL")
            return True
        except Exception as e:
            logger.error(f"Error connecting to FreeSWITCH ESL: {str(e)}")
            return False
    
    def _start_event_listener(self):
        """Start a background thread for ESL events."""
        if self.running:
            return
        
        self.running = True
        self.event_thread = threading.Thread(
            target=self._event_loop,
            daemon=True
        )
        self.event_thread.start()
    
    def _event_loop(self):
        """Listen for events from FreeSWITCH."""
        try:
            # Subscribe to events
            if not self.esl_connection.connected():
                if not self._connect():
                    logger.error("Not connected to FreeSWITCH, can't subscribe to events")
                    return
            
            self.esl_connection.events("plain", "all")
            logger.info("Subscribed to FreeSWITCH events")
            
            while self.running and self.esl_connection.connected():
                event = self.esl_connection.recvEvent()
                if event:
                    self._process_event(event)
                else:
                    # If recvEvent returns None, the connection may have been lost
                    logger.warning("Lost connection to FreeSWITCH")
                    time.sleep(5)
                    self._connect()
        except Exception as e:
            logger.error(f"Error in event loop: {str(e)}")
        finally:
            self.running = False
    
    def _process_event(self, event):
        """Process a FreeSWITCH event."""
        event_name = event.getHeader("Event-Name")
        
        if not event_name:
            return
        
        # Get UUID for call tracking
        session_id = event.getHeader("Unique-ID")
        
        # Process different event types
        if event_name == "CHANNEL_CREATE":
            # New call
            caller_id = event.getHeader("Caller-Caller-ID-Number")
            direction = event.getHeader("Call-Direction")
            
            self.active_calls[session_id] = {
                "caller_id": caller_id,
                "direction": direction,
                "start_time": datetime.now(),
                "state": "created",
                "session_id": session_id
            }
            
            self._trigger_callback("call.created", {
                "session_id": session_id,
                "caller_id": caller_id,
                "direction": direction
            })
        
        elif event_name == "CHANNEL_ANSWER":
            # Call answered
            if session_id in self.active_calls:
                self.active_calls[session_id]["state"] = "answered"
                self.active_calls[session_id]["answer_time"] = datetime.now()
                
                self._trigger_callback("call.answered", {
                    "session_id": session_id,
                    "caller_id": self.active_calls[session_id].get("caller_id"),
                    "direction": self.active_calls[session_id].get("direction")
                })
        
        elif event_name == "CHANNEL_HANGUP":
            # Call ended
            if session_id in self.active_calls:
                hangup_cause = event.getHeader("Hangup-Cause")
                
                # Calculate duration
                duration = None
                start_time = self.active_calls[session_id].get("start_time")
                if start_time:
                    duration = int((datetime.now() - start_time).total_seconds())
                
                self._trigger_callback("call.ended", {
                    "session_id": session_id,
                    "caller_id": self.active_calls[session_id].get("caller_id"),
                    "direction": self.active_calls[session_id].get("direction"),
                    "duration": duration,
                    "hangup_cause": hangup_cause
                })
                
                # Remove from active calls
                del self.active_calls[session_id]
        
        elif event_name == "DTMF":
            # DTMF keypress
            if session_id in self.active_calls:
                digit = event.getHeader("DTMF-Digit")
                
                if digit:
                    self._trigger_callback("call.dtmf", {
                        "session_id": session_id,
                        "digit": digit
                    })
        
        elif event_name == "DETECTED_SPEECH":
            # Speech detected (if using mod_pocketsphinx or similar)
            if session_id in self.active_calls:
                speech_type = event.getHeader("Speech-Type")
                speech_text = event.getHeader("Speech-Text")
                
                if speech_text:
                    self._trigger_callback("call.speech", {
                        "session_id": session_id,
                        "text": speech_text,
                        "type": speech_type
                    })
    
    def _trigger_callback(self, event_type, data):
        """Trigger registered callbacks for event."""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback: {str(e)}")
    
    def register_callback(self, event_type, callback):
        """Register a callback for a specific event type."""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        
        self.callbacks[event_type].append(callback)
        return True
    
    def send_command(self, command):
        """Send a command to FreeSWITCH."""
        if not self.esl_connection.connected():
            if not self._connect():
                logger.error("Not connected to FreeSWITCH, can't send command")
                return False
        
        result = self.esl_connection.api(command)
        return result.getBody()
    
    def originate_call(self, destination, caller_id, variables=None):
        """Originate a call."""
        variables = variables or {}
        variable_str = ""
        
        for key, value in variables.items():
            variable_str += f"{{{key}='{value}'}}"
        
        call_uuid = gen_uuid_12()
        
        # Build the originate command
        if destination.startswith("+"):
            # Route through Africa's Talking gateway
            command = f"originate {variable_str}sofia/gateway/africas_talking/{destination[1:]} &park()"
        else:
            # Direct SIP call
            command = f"originate {variable_str}sofia/external/{destination} &park()"
        
        # Execute the command
        result = self.send_command(command)
        
        if result and not result.startswith("-ERR"):
            # Successfully originated call
            return {
                "status": "success",
                "session_id": call_uuid,
                "destination": destination
            }
        else:
            logger.error(f"Error originating call: {result}")
            return {
                "status": "error",
                "message": result
            }
    
    def hangup_call(self, session_id):
        """Hang up a call."""
        command = f"uuid_kill {session_id}"
        result = self.send_command(command)
        
        return result and not result.startswith("-ERR")
    
    def speak_text(self, session_id, text, voice="kal"):
        """Use TTS to speak text on an active call."""
        # Escape single quotes in the text
        safe_text = text.replace("'", "\\'")
        
        # Send speak command
        command = f"uuid_speak {session_id} {voice} {safe_text}"
        result = self.send_command(command)
        
        return result and not result.startswith("-ERR")
    
    def join_conference(self, session_id, conference_name):
        """Join a call to a conference."""
        command = f"uuid_transfer {session_id} conference:{conference_name}"
        result = self.send_command(command)
        
        return result and not result.startswith("-ERR")
    
    def create_webrtc_session(self, session_id, sdp_offer):
        """
        Create a WebRTC session using Verto.
        
        Args:
            session_id: Unique session ID
            sdp_offer: SDP offer from browser
            
        Returns:
            Dictionary with SDP answer
        """
        try:
            # This is a simplified approach - in a real implementation,
            # you would use the Verto module's API or a WebSocket connection
            # to create the WebRTC session
            
            # For now, we'll use a placeholder with FreeSWITCH command
            uuid = gen_uuid_16()
            
            # Save SDP to a temporary file
            sdp_file = f"/tmp/sdp_offer_{uuid}.txt"
            with open(sdp_file, "w") as f:
                f.write(sdp_offer)
            
            # Command to create a WebRTC endpoint (using mod_verto)
            command = f"verto_contact {session_id} {sdp_file}"
            result = self.send_command(command)
            
            if result and not result.startswith("-ERR"):
                # Parse the result to get the SDP answer
                # This is a placeholder - you would parse the actual response
                return {
                    "status": "success",
                    "sdp": result
                }
            else:
                logger.error(f"Error creating WebRTC session: {result}")
                return None
        except Exception as e:
            logger.error(f"Error creating WebRTC session: {str(e)}")
            return None
    
    def stop(self):
        """Stop the ESL client and clean up resources."""
        self.running = False
        
        if self.esl_connection and self.esl_connection.connected():
            self.esl_connection.disconnect()
        
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5.0)
        
        logger.info("FreeSWITCH ESL client stopped")
        