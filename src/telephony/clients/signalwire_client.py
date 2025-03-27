# src/telephony/clients/signalwire_client.py
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
    Client for interacting with SignalWire's APIs and handling real-time events.
    Serves as the low-level interface that the SignalWireProvider uses.
    """
    
    def __init__(self):
        """Initialize the SignalWire client with configuration."""
        # API endpoints
        self.base_url = f"http://{settings.SIGNALWIRE_HOST}:{settings.SIGNALWIRE_PORT}/api/v1"
        self.ws_url = f"ws://{settings.SIGNALWIRE_HOST}:{settings.SIGNALWIRE_EVENT_PORT}"
        
        # Authentication
        self.auth = (settings.SIGNALWIRE_USERNAME, settings.SIGNALWIRE_PASSWORD)
        
        # Event handling
        self.event_callbacks = {}
        self.active_calls = {}
        self.event_socket = None
        self.event_thread = None
        self.running = False
        
        # Start event listener
        self._start_event_listener()
        
        logger.info("SignalWire client initialized")
    
    def _start_event_listener(self):
        """Start a background thread for the event WebSocket connection."""
        self.running = True
        self.event_thread = threading.Thread(
            target=self._event_loop_runner,
            daemon=True
        )
        self.event_thread.start()
    
    def _event_loop_runner(self):
        """Run the asyncio event loop in a separate thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._listen_for_events())
        except Exception as e:
            logger.error(f"Event listener error: {str(e)}", exc_info=True)
        finally:
            loop.close()
    
    async def _listen_for_events(self):
        """WebSocket connection handler for SignalWire events."""
        retry_delay = 1
        max_retry_delay = 30
        
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.event_socket = websocket
                    logger.info("Connected to SignalWire event socket")
                    
                    # Authenticate
                    auth_message = f"auth {settings.SIGNALWIRE_PASSWORD}"
                    await websocket.send(auth_message)
                    response = await websocket.recv()
                    
                    if "OK" not in response:
                        logger.error(f"Authentication failed: {response}")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, max_retry_delay)
                        continue
                    
                    # Subscribe to events
                    await websocket.send("event plain CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CHANNEL_BRIDGE DTMF CUSTOM")
                    
                    # Reset retry delay on successful connection
                    retry_delay = 1
                    
                    # Process events
                    while self.running:
                        try:
                            event_data = await websocket.recv()
                            self._process_event(event_data)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Event socket connection closed")
                            break
            
            except Exception as e:
                logger.error(f"Event socket error: {str(e)}", exc_info=True)
                
                # Exponential backoff for reconnection
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
    
    def _process_event(self, event_text: str):
        """Parse and process FreeSWITCH event data."""
        # Parse event headers
        event_data = {}
        for line in event_text.split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                event_data[key] = value
        
        # Extract key fields
        event_name = event_data.get("Event-Name")
        session_id = event_data.get("Unique-ID")
        
        if not event_name or not session_id:
            return
        
        # Process different event types
        if event_name == "CHANNEL_CREATE":
            # New call being created
            caller_id = event_data.get("Caller-Caller-ID-Number")
            direction = "inbound" if event_data.get("Call-Direction") == "inbound" else "outbound"
            
            # Extract Zeipo session ID if present
            session_id = event_data.get("variable_session_id", session_id)
            
            self.active_calls[session_id] = {
                "caller_id": caller_id,
                "direction": direction,
                "start_time": datetime.now(),
                "state": "created",
                "session_id": session_id
            }
            
            # Trigger callbacks
            self._trigger_callback("call.created", {
                "session_id": session_id,
                "caller_id": caller_id,
                "direction": direction
            })
            
        elif event_name == "CHANNEL_ANSWER":
            # Call was answered
            if session_id in self.active_calls:
                self.active_calls[session_id]["state"] = "answered"
                self.active_calls[session_id]["answer_time"] = datetime.now()
                
                # Get session ID
                session_id = self.active_calls[session_id].get("session_id", session_id)
                
                # Trigger callbacks
                self._trigger_callback("call.answered", {
                    "session_id": session_id,
                    "caller_id": self.active_calls[session_id].get("caller_id"),
                    "direction": self.active_calls[session_id].get("direction")
                })
                
                # Check for initial TTS message
                initial_tts = event_data.get("variable_initial_tts")
                if initial_tts:
                    # Slight delay to ensure call is fully established
                    time.sleep(0.5)
                    self.speak_text(session_id, initial_tts)
        
        elif event_name == "CHANNEL_HANGUP":
            # Call ended
            if session_id in self.active_calls:
                hangup_cause = event_data.get("Hangup-Cause")
                
                # Calculate duration if we have start time
                duration = None
                start_time = self.active_calls[session_id].get("start_time")
                if start_time:
                    duration = int((datetime.now() - start_time).total_seconds())
                
                # Get Zeipo session ID
                session_id = self.active_calls[session_id].get("session_id", session_id)
                
                # Trigger callbacks
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
            # DTMF key pressed
            if session_id in self.active_calls:
                digit = event_data.get("DTMF-Digit")
                
                if digit:
                    # Get Zeipo session ID
                    session_id = self.active_calls[session_id].get("session_id", session_id)
                    
                    self._trigger_callback("call.dtmf", {
                        "session_id": session_id,
                        "digit": digit
                    })
        
        elif event_name == "CUSTOM":
            # Custom events, including speech recognition results
            event_subclass = event_data.get("Event-Subclass")
            
            if event_subclass == "SPEECH_DETECTED":
                speech_text = event_data.get("Speech-Text")
                
                if speech_text and session_id in self.active_calls:
                    # Get Zeipo session ID
                    session_id = self.active_calls[session_id].get("session_id", session_id)
                    
                    self._trigger_callback("call.speech", {
                        "session_id": session_id,
                        "text": speech_text
                    })
    
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
        Initiate an outbound call through SignalWire.
        
        Args:
            destination: Destination number or SIP URI
            caller_id: Caller ID to display
            variables: Additional channel variables
            
        Returns:
            Dictionary with call details including session_id
        """
        try:
            # Generate a session ID
            session_id = f"out_{uuid.uuid4().hex[:12]}"
            
            # Default variables
            call_vars = {
                "session_id": session_id,
                "origination_caller_id_number": caller_id or "Zeipo AI"
            }
            
            # Add custom variables
            if variables:
                call_vars.update(variables)
            
            # Determine dial string based on destination format
            if destination.startswith("+"):
                # International format for Africa's Talking
                dial_string = f"sofia/gateway/africas_talking/{destination[1:]}"
            elif destination.startswith("sip:"):
                # Direct SIP URI
                dial_string = destination
            else:
                # Assume extension or local number
                dial_string = f"sofia/external/{destination}@{settings.SIGNALWIRE_HOST}:5080"
            
            # API request data
            request_data = {
                "dial_string": dial_string,
                "api_key": settings.SIGNALWIRE_API_KEY,
                "variables": call_vars
            }
            
            # Make API request
            response = requests.post(
                f"{self.base_url}/calls",
                json=request_data,
                auth=self.auth
            )
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"API error: {response.text}",
                    "code": response.status_code
                }
            
            result = response.json()
            
            # Return success response
            return {
                "status": "success",
                "session_id": session_id,
                "uuid": result.get("uuid"),
                "destination": destination
            }
            
        except Exception as e:
            logger.error(f"Error making call: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def hangup_call(self, session_id: str) -> bool:
        """
        Hang up an active call.
        
        Args:
            session_id: The session ID of the call to hang up
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID for this session
            fs_uuid = None
            
            # Check in our active calls mapping
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                logger.warning(f"No active call found for session ID: {session_id}")
                return False
            
            # Hang up the call via API
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/hangup",
                auth=self.auth
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to hang up call: {response.text}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error hanging up call: {str(e)}", exc_info=True)
            return False
    
    def play_audio(self, session_id: str, audio_file: str) -> bool:
        """
        Play an audio file on an active call.
        
        Args:
            session_id: The session ID of the call
            audio_file: Path to the audio file to play
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to play audio
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/play",
                json={"file": audio_file},
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error playing audio: {str(e)}", exc_info=True)
            return False
    
    def speak_text(self, session_id: str, text: str, voice: str = "female") -> bool:
        """
        Speak text on an active call using TTS.
        
        Args:
            session_id: The session ID of the call
            text: Text to speak
            voice: Voice to use (male/female)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to speak text
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/speak",
                json={
                    "text": text,
                    "engine": "flite",
                    "voice": voice
                },
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error speaking text: {str(e)}", exc_info=True)
            return False
    
    def start_recognition(self, session_id: str) -> bool:
        """
        Start speech recognition on an active call.
        
        Args:
            session_id: The session ID of the call
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to start recognition
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/detect_speech",
                json={
                    "engine": "pocketsphinx",
                    "grammar": "default"
                },
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error starting recognition: {str(e)}", exc_info=True)
            return False
    
    def stop_recognition(self, session_id: str) -> bool:
        """
        Stop speech recognition on an active call.
        
        Args:
            session_id: The session ID of the call
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to stop recognition
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/detect_speech",
                json={"action": "stop"},
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error stopping recognition: {str(e)}", exc_info=True)
            return False
    
    def send_dtmf(self, session_id: str, digits: str) -> bool:
        """
        Send DTMF tones to an active call.
        
        Args:
            session_id: The session ID of the call
            digits: DTMF digits to send (0-9, *, #)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to send DTMF
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/dtmf",
                json={"digits": digits},
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error sending DTMF: {str(e)}", exc_info=True)
            return False
    
    def create_conference(self, conference_name: str) -> Dict[str, Any]:
        """
        Create a conference room.
        
        Args:
            conference_name: Name of the conference to create
            
        Returns:
            Conference response details
        """
        try:
            # API request to create conference
            response = requests.post(
                f"{self.base_url}/conferences",
                json={"name": conference_name},
                auth=self.auth
            )
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"API error: {response.text}",
                    "code": response.status_code
                }
            
            result = response.json()
            
            return {
                "status": "success",
                "conference_name": conference_name,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error creating conference: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def join_conference(self, session_id: str, conference_name: str) -> bool:
        """
        Join a call to a conference.
        
        Args:
            session_id: The session ID of the call
            conference_name: Name of the conference to join
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to join conference
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/conference",
                json={"conference_name": conference_name},
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error joining conference: {str(e)}", exc_info=True)
            return False
    
    def record_call(self, session_id: str, file_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Start recording a call.
        
        Args:
            session_id: The session ID of the call
            file_name: Optional custom filename (without extension)
            
        Returns:
            Recording details
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return {
                    "status": "error",
                    "message": f"No active call found for session ID: {session_id}"
                }
            
            # Generate filename if not provided
            if not file_name:
                file_name = f"rec_{session_id}_{int(time.time())}"
            
            # API request to start recording
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/record",
                json={"file_name": file_name},
                auth=self.auth
            )
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"API error: {response.text}",
                    "code": response.status_code
                }
            
            result = response.json()
            
            return {
                "status": "success",
                "session_id": session_id,
                "recording_path": result.get("recording_path"),
                "file_name": file_name
            }
            
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def stop_recording(self, session_id: str) -> bool:
        """
        Stop recording a call.
        
        Args:
            session_id: The session ID of the call
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the FreeSWITCH UUID
            fs_uuid = None
            for uuid, call_data in self.active_calls.items():
                if call_data.get("session_id") == session_id:
                    fs_uuid = uuid
                    break
            
            if not fs_uuid:
                return False
            
            # API request to stop recording
            response = requests.post(
                f"{self.base_url}/calls/{fs_uuid}/record/stop",
                auth=self.auth
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error stopping recording: {str(e)}", exc_info=True)
            return False
    
    def stop(self):
        """Stop the client and clean up resources."""
        self.running = False
        
        # Wait for event thread to terminate
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5.0)
        
        logger.info("SignalWire client stopped")
        