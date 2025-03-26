# src/api/asterisk.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import JSONResponse
import asyncio
import logging

from ...main import ari_client  
from static.constants import logger

router = APIRouter(prefix="/asterisk")

@router.post("/media/{channel_id}")
async def handle_external_media(channel_id: str, request: Request):
    """Handle external media from Asterisk"""
    if not ari_client:
        return JSONResponse({"error": "ARI client not initialized"}, status_code=500)
    
    # Get the raw audio data
    audio_data = await request.body()
    
    # Process the audio data
    if channel_id in ari_client.audio_streams:
        ari_client.audio_streams[channel_id].add_audio(audio_data)
    
    return Response(status_code=200)

@router.websocket("/ws/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: str):
    """WebSocket endpoint for bi-directional audio streaming with Asterisk"""
    await websocket.accept()
    
    try:
        # Register websocket with ARI client
        if ari_client and channel_id in ari_client.active_calls:
            # TODO: Implementation details would go here
            pass
        
        # Keep connection open and handle messages
        while True:
            data = await websocket.receive_bytes()
            # Process incoming audio data
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for channel {channel_id}")
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        