import ari
import threading
import logging
import uuid
import os
import time
import asyncio
import json
from typing import Dict, Any, Optional, List, Callable
import numpy as np
import wave

from src.stt.stt_base import STTProvider
from src.nlp.intent_processor import IntentProcessor
from src.tts import get_tts_provider
from static.constants import logger
from config import settings

class AudioStream:
    """Manages the audio for a particular channel"""
    
    def __init__(self, channel_id: str, callback: Optional[Callable] = None):
        self.channel_id = channel_id
        self.callback = callback
        self.audio_buffer = bytearray()
        self.recording_file = None
        self.wave_file = None
        self.stt_provider = None
        self.is_active = True
        
    def start(self, model_name: str = "small", language: Optional[str] = None):
        """Start audio processing"""
        # Create recording directory if not exists
        os.makedirs("data/call_recordings", exist_ok=True)
        
        # Prepare recording file
        recording_path = f"data/call_recordings/zeipo-{self.channel_id}.wav"
        self.recording_file = recording_path
        self.wave_file = wave.open(recording_path, 'wb')
        self.wave_file.setnchannels(1)  # Mono
        self.wave_file.setsampwidth(2)  # 16-bit
        self.wave_file.setframerate(16000)  # 16kHz
        
        # Initialize STT provider
        self.stt_provider = STTProvider(
            model_name=model_name,
            language=language,
            chunk_size_ms=500,
            buffer_size_ms=5000
        )
        
        # Start transcription
        self.stt_provider.start(self._on_transcription)
        
        logger.info(f"Started audio processing for channel {self.channel_id}")
        
    def stop(self):
        """Stop audio processing"""
        self.is_active = False
        
        # Stop STT provider
        if self.stt_provider:
            self.stt_provider.stop()
        
        # Close wave file
        if self.wave_file:
            self.wave_file.close()
        
        logger.info(f"Stopped audio processing for channel {self.channel_id}")
        
    def add_audio(self, audio_data: bytes):
        """Add audio data to the stream"""
        if not self.is_active:
            return
            
        try:
            # Write to recording file
            if self.wave_file:
                self.wave_file.writeframes(audio_data)
            
            # Convert to format expected by STT
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Add to STT provider
            if self.stt_provider:
                self.stt_provider.add_audio_chunk(audio_array)
                
        except Exception as e:
            logger.error(f"Error processing audio data: {str(e)}", exc_info=True)
    
    def _on_transcription(self, result: Dict[str, Any]):
        """Handle transcription result"""
        if self.callback and self.is_active:
            self.callback(self.channel_id, result)


class ZeipoARIClient:
    """ARI client for Zeipo AI telephony integration"""
    
    def __init__(
        self,
        url: str = None,
        username: str = None,
        password: str = None,
        app_name: str = "zeipo"
    ):
        # Use settings if not provided
        self.url = url or settings.ASTERISK_ARI_URL
        self.username = username or settings.ASTERISK_ARI_USERNAME
        self.password = password or settings.ASTERISK_ARI_PASSWORD
        self.app_name = app_name
        
        # Client initialization
        self.client = None
        self.running = False
        self.event_thread = None
        
        # Call state tracking
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.audio_streams: Dict[str, AudioStream] = {}
        
        # Initialize the intent processor
        self.intent_processor = IntentProcessor()
        
        # TTS provider
        self.tts_provider = get_tts_provider()
        
    def start(self):
        """Start the ARI client"""
        try:
            logger.info(f"Connecting to Asterisk ARI at {self.url}")
            self.client = ari.connect(
                self.url,
                self.username,
                self.password
            )
            
            # Register event handlers
            self.client.on_channel_event('StasisStart', self._on_stasis_start)
            self.client.on_channel_event('StasisEnd', self._on_stasis_end)
            self.client.on_channel_event('ChannelDtmfReceived', self._on_dtmf)
            self.client.on_channel_event('ChannelHangupRequest', self._on_hangup_request)
            
            # Start the event loop in a separate thread
            self.running = True
            self.event_thread = threading.Thread(
                target=self._event_loop,
                daemon=True
            )
            self.event_thread.start()
            
            logger.info("ARI client started successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Asterisk ARI: {str(e)}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the ARI client"""
        self.running = False
        
        # Stop all active calls
        for channel_id in list(self.active_calls.keys()):
            self._end_call(channel_id)
        
        # Wait for event thread to terminate
        # This happens through unhandled exception or optional timeout
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5.0)
        
        logger.info("ARI client stopped")
    
    def _event_loop(self):
        """Run the ARI client event loop"""
        try:
            logger.info(f"Starting ARI event loop for application '{self.app_name}'")
            self.client.run(apps=self.app_name)
        except Exception as e:
            logger.error(f"ARI event loop terminated with error: {str(e)}", exc_info=True)
            self.running = False
    
    def _on_stasis_start(self, channel_obj, event):
        """Handle new call entering the Stasis application"""
        channel_id = channel_obj.id
        caller_id = channel_obj.json.get('caller', {}).get('number')
        dialed_number = channel_obj.json.get('dialplan', {}).get('exten')
        
        logger.info(f"Call entering Stasis: {channel_id} from {caller_id} to {dialed_number}")
        
        # Store call information
        self.active_calls[channel_id] = {
            'channel': channel_obj,
            'caller_id': caller_id,
            'dialed_number': dialed_number,
            'start_time': time.time(),
            'state': 'new'
        }
        
        # Answer call if not already answered
        if channel_obj.json.get('state') != 'Up':
            channel_obj.answer()
        
        # Play welcome message
        self._play_welcome(channel_id)
        
        # Start audio processing
        audio_stream = AudioStream(channel_id, self._on_transcription_result)
        audio_stream.start()
        self.audio_streams[channel_id] = audio_stream
        
        # Set up audio capture through ARI
        self._setup_audio_capture(channel_obj)
        
        # Update call state
        self.active_calls[channel_id]['state'] = 'active'
    
    def _on_stasis_end(self, channel_obj, event):
        """Handle call exiting the Stasis application"""
        channel_id = channel_obj.id
        
        if channel_id in self.active_calls:
            logger.info(f"Call exiting Stasis: {channel_id}")
            self._end_call(channel_id)
    
    def _on_hangup_request(self, channel_obj, event):
        """Handle hangup request"""
        channel_id = channel_obj.id
        
        if channel_id in self.active_calls:
            logger.info(f"Hangup requested for call: {channel_id}")
            self._end_call(channel_id)
    
    def _on_dtmf(self, channel_obj, event):
        """Handle DTMF input"""
        channel_id = channel_obj.id
        digit = event.get('digit')
        
        if channel_id in self.active_calls:
            logger.info(f"DTMF received on call {channel_id}: {digit}")
            
            # Special DTMF handling can be added here
            # For example: # to end call, * for special functions
            if digit == '#':
                # End call on # key
                self._play_message(channel_id, "Thank you for calling. Goodbye!")
                self._end_call(channel_id, delay=2)
    
    def _setup_audio_capture(self, channel):
        """Set up audio capture for a channel"""
        try:
            # Create a bi-directional snoop channel
            snoop = channel.externalMedia(
                app='zeipo',
                external_host='127.0.0.1',  # Use internal Docker network address
                format='slin16'  # 16-bit signed linear PCM
            )
            
            # TODO: Complete the external media setup
            # This is placeholder - actual implementation depends on
            # how you want to capture audio from Asterisk
            
            logger.info(f"Set up audio capture for channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Failed to set up audio capture: {str(e)}", exc_info=True)
    
    def _play_welcome(self, channel_id):
        """Play welcome message to the caller"""
        welcome_text = "Welcome to Zeipo AI. How can I help you today?"
        self._play_message(channel_id, welcome_text)
    
    def _play_message(self, channel_id, text):
        """Generate TTS and play a message to the caller"""
        if channel_id not in self.active_calls:
            logger.warning(f"Cannot play message - channel {channel_id} not found")
            return
            
        try:
            # Generate TTS audio
            audio_content = self.tts_provider.synthesize(text)
            
            # Save to temporary file
            temp_file = f"/tmp/zeipo_tts_{channel_id}_{int(time.time())}.slin16"
            with open(temp_file, 'wb') as f:
                f.write(audio_content)
            
            # Play the file through Asterisk
            channel = self.active_calls[channel_id]['channel']
            channel.play(media=f'sound:{temp_file}')
            
            logger.info(f"Playing message on channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Failed to play message: {str(e)}", exc_info=True)
    
    def _end_call(self, channel_id, delay=0):
        """End a call gracefully"""
        if channel_id not in self.active_calls:
            return
            
        # Stop audio processing
        if channel_id in self.audio_streams:
            self.audio_streams[channel_id].stop()
            del self.audio_streams[channel_id]
        
        # Hang up the channel after delay
        if delay > 0:
            def delayed_hangup():
                time.sleep(delay)
                try:
                    channel = self.active_calls[channel_id]['channel']
                    channel.hangup()
                except:
                    pass
                
                # Remove from active calls
                if channel_id in self.active_calls:
                    del self.active_calls[channel_id]
            
            threading.Thread(target=delayed_hangup, daemon=True).start()
        else:
            # Hang up immediately
            try:
                channel = self.active_calls[channel_id]['channel']
                channel.hangup()
            except Exception as e:
                logger.error(f"Error hanging up call {channel_id}: {str(e)}", exc_info=True)
            
            # Remove from active calls
            del self.active_calls[channel_id]
    
    def _on_transcription_result(self, channel_id: str, result: Dict[str, Any]):
        """Handle transcription result"""
        if channel_id not in self.active_calls:
            return
            
        text = result.get('text', '')
        is_final = result.get('is_final', False)
        
        # Skip empty or short texts
        if not text or len(text) < 3:
            return
            
        logger.info(f"Transcription for {channel_id}: {text} (final: {is_final})")
        
        # Process through NLU if this is a final result
        if is_final:
            try:
                # Process through intent processor
                nlu_results, response_text = self.intent_processor.process_text(
                    text=text,
                    session_id=channel_id
                )
                
                # Check if we have a response
                if response_text and len(response_text) > 0:
                    # Play response back to caller
                    self._play_message(channel_id, response_text)
                
            except Exception as e:
                logger.error(f"Error processing intent: {str(e)}", exc_info=True)
                
                # Provide a fallback response
                self._play_message(channel_id, "I'm sorry, I'm having trouble understanding. Could you please repeat that?")
                