# src/api/websockets.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict
import asyncio
import base64

from db.session import get_db
from db.models import CallSession
from static.constants import logger
from src.streaming.audio_streaming import AudioStreamManager
from src.nlp.intent_processor import IntentProcessor
from src.api.router import router

# Create audio stream manager
stream_manager = AudioStreamManager()

# Create intent processor
intent_processor = IntentProcessor()

# Start background task for cleanup
cleanup_task = None

router.prefix = "/ws"

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
        # Connect WebSocket
        await stream_manager.connect(
            websocket=websocket, 
            session_id=session_id,
            language=language,
            model_name=model
        )
        
        # Handle incoming data
        async for data in websocket.iter_bytes():
            if data:
                # Extract connection ID from first message
                if connection_id is None:
                    try:
                        # First message should be JSON with connection_id
                        text_data = data.decode('utf-8')
                        import json
                        json_data = json.loads(text_data)
                        connection_id = json_data.get('connection_id')
                        
                        # Acknowledge
                        await websocket.send_json({
                            "type": "connection_confirmed",
                            "connection_id": connection_id
                        })
                        continue
                    except Exception:
                        # If not JSON, assume it's binary audio data
                        pass
                
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

# Start the cleanup task when the module is loaded
@router.on_startup
async def startup_event():
    global cleanup_task
    cleanup_task = asyncio.create_task(stream_manager.cleanup_stale_connections())

@router.on_shutdown
async def shutdown_event():
    global cleanup_task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        