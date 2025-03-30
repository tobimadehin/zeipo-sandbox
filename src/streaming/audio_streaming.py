# src/streaming/audio_streaming.py
import os
import asyncio
import threading
import time
from fastapi.websockets import WebSocketState
import numpy as np
from typing import Callable, Dict, Optional, Any
from datetime import datetime
import wave
from fastapi import WebSocket
import webrtcvad

from src.stt import get_stt_provider
from src.utils.helpers import gen_uuid_16
from static.constants import RECORDING_DIR, logger
from src.stt.stt_base import STTProvider

class AudioStreamManager:
    """
    Manager for handling audio WebSocket streams.
    This class manages active connections and processes audio streams.
    """
    
    def __init__(self):
        """Initialize the audio stream manager."""
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.recording_dir = RECORDING_DIR
        
        # Ensure recording directory exists
        os.makedirs(self.recording_dir, exist_ok=True)
    
    async def connect(
        self, 
        websocket: WebSocket, 
        session_id: str,
        connection_id: str,
        model_name: str = "tiny",
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Connect a new WebSocket client.
        
        Args:
            websocket: The WebSocket connection
            session_id: The call session ID
            connection_id: Unique identifier for this connection
            model_name: Whisper model to use
            callback: Optional external callback for transcription results
        """    
        # Initialize connection data
        file_path = os.path.join(self.recording_dir, f"{session_id}_{connection_id}.wav")
        
        # Prepare audio recording file
        wf = wave.open(file_path, 'wb')
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 2 bytes (16 bits)
        wf.setframerate(16000)  # 16 kHz
        
        # Get STT provider
        provider = get_stt_provider()
        
        # Initialize streaming transcriber
        provider.create_streaming_transcriber(model_name=model_name)
        
        # Prepare connection data
        connection_data = {
            "websocket": websocket,
            "session_id": session_id,
            "connection_id": connection_id,
            "file_path": file_path,
            "wave_file": wf,
            "audio_buffer": bytearray(),
            "start_time": datetime.now(),
            "last_activity": datetime.now(),
            "transcription_results": [],
            "is_finalized": False,
            "external_callback": callback,
        }
        
        # Store connection
        self.active_connections[connection_id] = connection_data
        
        # Start the transcriber
        def transcription_callback_wrapper(result):
            logger.debug(f"Transcription callback called for {connection_id}")
            
            connection_data["transcription_results"].append(result)
            connection_data["last_activity"] = datetime.now()
            
            # Get the loop from the connection data and run the coroutine in that loop
            loop = connection_data["loop"]
            asyncio.run_coroutine_threadsafe(send_transcript_update(result), loop)
            
            # Call external callback if provided
            if connection_data.get("external_callback"):
                asyncio.run_coroutine_threadsafe(connection_data["external_callback"](result), loop)
                
        # Sent transcript updates to the client
        async def send_transcript_update(result):
            try:
                if connection_data["websocket"].client_state == WebSocketState.CONNECTED:
                    await connection_data["websocket"].send_json({
                        "type": "audio_stream",
                        "connection_id": connection_id,
                        "session_id": session_id,
                        "text": result["text"],
                        "is_final": result["is_final"]
                    })
            except Exception as e:
                logger.error(f"Error sending transcript update: {str(e)}", exc_info=True)
        
        # Store the event loop in connection data
        connection_data["loop"] = asyncio.get_event_loop()
        
        logger.debug(f"Attempting to start transcription for {connection_id}")

        self.start(transcription_callback_wrapper)
        
        logger.info(f"WebSocket connection established: {connection_id} for session {session_id}")
        
        # Send acknowledgment to client
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "session_id": session_id,
            "message": "Successfully connected to audio stream"
        })
    
    async def receive_audio(self, connection_id: str, data: bytes) -> None:
        """
        Receive and process audio data from the client.
        
        Args:
            connection_id: The connection ID
            data: Binary audio data
        """
        if connection_id not in self.active_connections:
            logger.error(f"Connection not found: {connection_id}")
            return
        
        logger.debug(f"Received {len(data)} of {type(data)} from {connection_id}")
        
        connection = self.active_connections[connection_id]
        
        # Update last activity timestamp
        connection["last_activity"] = datetime.now()
        
        try:
            # Write to WAV file
            connection["wave_file"].writeframes(data)
            
            # Process audio for transcription
            # For WebM/Opus from mobile, we need to decode first
            if connection.get("is_mobile_client", False):
                try:
                    # This is a simplified example - actual implementation would depend on
                    # the audio format sent by the mobile client
                    # Process through VAD to determine speech segments
                    vad = webrtcvad.Vad(3)  # Aggressiveness level
                    is_speech = vad.is_speech(data, 16000)
                    
                    if is_speech:
                        # Convert to format expected by Whisper
                        audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        connection["transcriber"].add_audio_chunk(audio_array)
                except ImportError:
                    # Fallback if webrtcvad not available
                    audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    connection["transcriber"].add_audio_chunk(audio_array)
            else:
                # Standard processing for non-mobile clients
                audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                connection["transcriber"].add_audio_chunk(audio_array)
            
            # Store in buffer
            connection["audio_buffer"].extend(data)
    
        except Exception as e:
            logger.error(f"Error processing audio data: {str(e)}")

    
    async def disconnect(self, connection_id: str) -> Dict[str, Any]:
        """
        Disconnect a WebSocket client and finalize processing.
        
        Args:
            connection_id: The connection ID
            
        Returns:
            Final processing results
        """
        if connection_id not in self.active_connections:
            logger.error(f"Connection not found: {connection_id}")
            return {"error": "Connection not found"}
        
        connection = self.active_connections[connection_id]
        
        # Finalize transcription
        final_result = connection["transcriber"].stop()
        
        # Close the WAV file
        if connection["wave_file"]:
            connection["wave_file"].close()
        
        # Mark as finalized
        connection["is_finalized"] = True
        
        # Calculate duration
        duration = (datetime.now() - connection["start_time"]).total_seconds()
        
        # Prepare final results
        results = {
            "connection_id": connection_id,
            "session_id": connection["session_id"],
            "duration": duration,
            "recording_path": connection["file_path"],
            "transcription": final_result,
            "finalized_at": datetime.now().isoformat()
        }
        
        # Clean up connection
        del self.active_connections[connection_id]
        
        logger.info(f"WebSocket connection closed: {connection_id}")
        
        return results
    
    async def cleanup_stale_connections(self, max_idle_time: int = 300) -> None:
        """
        Periodically clean up stale connections that have been idle for too long.
        
        Args:
            max_idle_time: Maximum idle time in seconds before considering a connection stale
        """
        while True:
            try:
                current_time = datetime.now()
                stale_connections = []
                
                # Find stale connections
                for connection_id, connection in self.active_connections.items():
                    idle_time = (current_time - connection["last_activity"]).total_seconds()
                    if idle_time > max_idle_time:
                        stale_connections.append(connection_id)
                
                # Disconnect stale connections
                for connection_id in stale_connections:
                    logger.warning(f"Cleaning up stale connection: {connection_id}")
                    try:
                        await self.disconnect(connection_id)
                    except Exception as e:
                        logger.error(f"Error disconnecting stale connection {connection_id}: {str(e)}")
                
                # Sleep before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in stale connection cleanup: {str(e)}")
                await asyncio.sleep(60)
                
    def start(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Start streaming transcription with callback for results."""
        self.streaming_callback = callback
        self.is_streaming = True
        self.audio_buffer = []
        self.last_process_time = time.time()
        
        # Start background processing thread
        self.process_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
        self.process_thread.start()
        
        logger.info("Started streaming transcription")

    def add_audio_chunk(self, audio_chunk: np.ndarray) -> None:
        """Add audio chunk to streaming buffer."""
        if not self.is_streaming:
            return
        
        self.audio_buffer.append(audio_chunk)
        
    def stop(self) -> Dict[str, Any]:
        """Stop streaming transcription and return final results."""
        self.is_streaming = False
        
        # Wait for processing thread to finish
        if hasattr(self, 'process_thread') and self.process_thread.is_alive():
            self.process_thread.join(timeout=5.0)
        
        # Process remaining audio
        if self.audio_buffer:
            combined_audio = np.concatenate(self.audio_buffer)
            model = self.get_model(self.model_name)
            final_result = model.transcribe(combined_audio)
            return final_result
        
        return {"text": "", "segments": []}

    def _process_audio_loop(self):
        """Background thread to process audio chunks periodically."""
        while self.is_streaming:
            # Process audio when enough has accumulated
            current_time = time.time()
            if (current_time - self.last_process_time >= 2.0) and self.audio_buffer:
                try:
                    combined_audio = np.concatenate(self.audio_buffer)
                    model = self.get_model(self.model_name)
                    result = model.transcribe(combined_audio)
                    
                    if self.streaming_callback:
                        self.streaming_callback({
                            "text": result["text"],
                            "is_final": False
                        })
                    
                    self.audio_buffer = []
                    self.last_process_time = current_time
                    
                except Exception as e:
                    logger.error(f"Error processing audio: {str(e)}")
            
            time.sleep(0.1)
        