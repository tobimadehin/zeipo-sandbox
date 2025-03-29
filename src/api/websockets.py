# src/api/websockets.py
import json
import tempfile
import time
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional
import asyncio
from fastapi.websockets import WebSocketState
import numpy as np

from db.session import SessionLocal
from src.api.telephony import WebRTCSignal
from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager
from src.nlp.intent_processor import IntentProcessor
from src.api.router import create_router
from src.utils.helpers import convert_opus_to_pcm, gen_uuid_12, gen_uuid_16

# Create audio stream manager
stream_manager = AudioStreamManager()

# Create intent processor
intent_processor = IntentProcessor()

# Start background task for cleanup
cleanup_task = None

router = create_router("/ws")

@router.websocket("/audio")
async def websocket_audio_endpoint(
    websocket: WebSocket, 
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
        connection_id = gen_uuid_16()
        session_id = gen_uuid_12()
        
        await websocket.accept()
        logger.info(f"New WebSocket connection established for session: {session_id}")
        
        # Respond with confirmation
        await websocket.send_json({
            "type": "connection_confirmed",
            "connection_id": connection_id,
            "session_id": session_id,
            "server_time": time.time()
        })
        
        # Connect WebSocket
        await stream_manager.connect(
            websocket=websocket, 
            session_id=session_id,
            connection_id=connection_id,
            language=language,
            model_name=model
        )
        
        logger.info(f"Processing audio for session: {session_id}")
        
        greeting_msg = await websocket.receive()
        
        logger.debug(f"Received test data: {greeting_msg}, {type(greeting_msg)}")

        async for data in websocket.iter_bytes():
            if data:  
                logger.debug(f"Received {len(data)} {type(data)} of audio data")
                await stream_manager.receive_audio(connection_id, data)
                
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {session_id}")
        if connection_id:
            final_results = await stream_manager.disconnect(connection_id)
            logger.info(f"Final processing results: {final_results}")
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}", exc_info=True)
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
        
        