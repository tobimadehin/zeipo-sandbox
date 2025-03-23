# src/api/websockets.py
import json
import time
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional
import asyncio
import numpy as np

from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager
from src.nlp.intent_processor import IntentProcessor
from src.api.router import create_router
from src.utils.helpers import gen_uuid_16

# Create audio stream manager
stream_manager = AudioStreamManager()

# Create intent processor
intent_processor = IntentProcessor()

# Start background task for cleanup
cleanup_task = None

router = create_router("/ws")

@router.websocket("/audio/{session_id}")
async def websocket_audio_endpoint(
    websocket: WebSocket, 
    session_id: str,
    language: Optional[str] = None,
    model: str = "small"
):
    """
    WebSocket endpoint for streaming audio data.
    
    Args:
        websocket: The WebSocket connection
        session_id: The call session ID
        language: Preferred language code (optional)
        model: Whisper model to use (default: small)
    """
    connection_id = None
    
    try:
        await websocket.accept()
        logger.info(f"New WebSocket connection established for session: {session_id}")
        
        # Wait for initial message from client
        initial_message = await websocket.receive_json()
        
        # Extract connection ID
        connection_id = initial_message.get('connection_id')
        
        # Respond with confirmation
        await websocket.send_json({
            "type": "connection_confirmed",
            "connection_id": connection_id,
            "server_time": time.time()
        })
        
        # Connect WebSocket
        await stream_manager.connect(
            websocket=websocket, 
            session_id=session_id,
            language=language,
            model_name=model
        )
        
        logger.info(f"Processing audio for session: {session_id}")
        
        # Handle incoming data
        async for data in websocket.iter_bytes():
            if data:
                # Extract connection ID from first message
                if connection_id is None:
                    try:
                        # First message should be JSON with connection_id
                        text_data = data.decode('utf-8', errors='ignore')
                        if '{' in text_data and '}' in text_data:
                            try:
                                text_data = data.decode('utf-8', errors='ignore')
                                if '{' in text_data and '}' in text_data:
                                    json_data = json.loads(text_data)
                                    client_conn_id = json_data.get('connection_id')
                                    if client_conn_id:
                                        logger.info(f"Client identified: {client_conn_id}")
                                        await websocket.send_json({
                                            "type": "connection_confirmed",
                                            "connection_id": client_conn_id
                                        })
                                    continue
                            except Exception:
                                # If not JSON, assume it's binary audio data
                                logger.debug(f"Not JSON data: {str(e)}")
                        
                        # Handle binary audio data
                        logger.debug(f"Received {len(data)} bytes of audio data")
                        
                        # If we reach here, either text wasn't JSON or couldn't be parsed
                        # Generate a connection ID for the client
                        connection_id = gen_uuid_16()
                        await websocket.send_json({
                            "type": "audio_received",
                            "bytes": len(data),
                            "connection_id": connection_id
                        })
                        
                        logger.info(f"Processing audio for connection with ID: {connection_id}")
                        
                        # Process the first data chunk
                        await stream_manager.receive_audio(connection_id, data)
                
                    except Exception as e:
                        logger.error(f"Error handling initial connection data: {str(e)}")
                        # Generate a connection ID as fallback
                        connection_id = gen_uuid_16()
                        await websocket.send_json({
                            "type": "connection_confirmed",
                            "connection_id": connection_id
                        })
                else:
                    # Process audio data
                    await stream_manager.receive_audio(connection_id, data)

    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {session_id}")
        if connection_id:
            final_results = await stream_manager.disconnect(connection_id)
            logger.info(f"Final processing results: {final_results}")
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        if connection_id:
            await stream_manager.disconnect(connection_id)

# Function to start cleanup task
async def start_cleanup_task():
    global cleanup_task
    cleanup_task = asyncio.create_task(stream_manager.cleanup_stale_connections())

# Function to stop cleanup task
async def stop_cleanup_task():
    global cleanup_task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        