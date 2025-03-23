# src/streaming/audio_streaming.py
import os
import asyncio
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime
import wave
from fastapi import WebSocket
import webrtcvad

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
        language: Optional[str] = None,
        model_name: str = "small"
    ) -> None:
        """
        Connect a new WebSocket client.
        
        Args:
            websocket: The WebSocket connection
            session_id: The call session ID
            language: Preferred language code (optional)
            model_name: Whisper model to use
        """    
        # Initialize connection data
        file_path = os.path.join(self.recording_dir, f"{session_id}_{connection_id}.wav")
        
        # Prepare audio recording file
        wf = wave.open(file_path, 'wb')
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 2 bytes (16 bits)
        wf.setframerate(16000)  # 16 kHz
        
        # Initialize streaming transcriber
        transcriber = STTProvider(
            model_name=model_name,
            language=language,
            chunk_size_ms=1000,
            buffer_size_ms=5000
        )
        
        # Prepare connection data
        connection_data = {
            "websocket": websocket,
            "session_id": session_id,
            "connection_id": connection_id,
            "file_path": file_path,
            "wave_file": wf,
            "transcriber": transcriber,
            "audio_buffer": bytearray(),
            "start_time": datetime.now(),
            "last_activity": datetime.now(),
            "transcription_results": [],
            "is_finalized": False
        }
        
        # Store connection
        self.active_connections[connection_id] = connection_data
        
        # Start the transcriber
        def transcription_callback(result):
            connection_data["transcription_results"].append(result)
            connection_data["last_activity"] = datetime.now()
        
        transcriber.start(transcription_callback)
        
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