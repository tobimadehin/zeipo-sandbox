# src/tts/edge_tts.py
import asyncio
import os
import uuid
from typing import Dict, List, Optional, Any
import edge_tts

from config import settings
import concurrent.futures
from src.utils.helpers import gen_uuid_16
from static.constants import logger
from ..tts_base import TTSProvider
from ..audio_cache import TTSAudioCache

class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS provider implementation."""
    
    def __init__(self):
        """Initialize the Edge TTS provider and cache."""
        self.cache = TTSAudioCache(settings.TTS_CACHE_DIR)
        self.default_voice = settings.EDGE_TTS_DEFAULT_VOICE
        
        logger.info(f"Edge TTS initialized with default voice: {self.default_voice}")
    
    async def _synthesize_async(self, text: str, voice_id: str) -> bytes:
        """
        Asynchronous implementation of TTS synthesis.
        
        Args:
            text: The text to synthesize
            voice_id: The voice ID to use
            
        Returns:
            Audio data as bytes
        """
        try:
            communicate = edge_tts.Communicate(text, voice_id)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data
        except Exception as e:
            logger.error(f"Error in Edge TTS synthesis: {str(e)}")
            raise
    
    def synthesize(self, text: str, voice_id: str = None, language_code: str = None) -> bytes:
        """
        Synthesize speech from text using Edge TTS.
        
        Args:
            text: The text to synthesize
            voice_id: The specific voice ID to use
            language_code: The language code (used to select voice if voice_id not provided)
            
        Returns:
            Audio data as bytes
        """
        # Determine voice ID based on parameters and defaults
        selected_voice = voice_id or self._get_voice_for_language(language_code) or self.default_voice
        
        logger.debug(f"Selected voice: {selected_voice}")
        
        # Check cache first
        cache_path = self.cache.get_cached_audio_path(text, selected_voice, language_code or "")
        if cache_path:
            logger.info(f"Using cached TTS audio for: {text[:30]}...")
            with open(cache_path, 'rb') as f:
                return f.read()
        
        try:
            loop = asyncio.get_event_loop()
        
            if loop.is_running():
                # We're inside a running event loop (FastAPI context)
                # Use a ThreadPoolExecutor to run the async code in a separate thread
                
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.new_event_loop().run_until_complete(
                        self._synthesize_async(text, selected_voice)))
                    audio_content = future.result()
            else:
                # No event loop running, use this one directly
                audio_content = loop.run_until_complete(self._synthesize_async(text, selected_voice))

            
            # Save to cache
            cache_file = os.path.join(
                settings.TTS_CACHE_DIR,
                f"tts_{gen_uuid_16()}.mp3"
            )
            with open(cache_file, 'wb') as f:
                f.write(audio_content)
            
            self.cache.cache_audio(text, selected_voice, language_code or "", cache_file)
            
            return audio_content
            
        except Exception as e:
            logger.error(f"Error in Edge TTS synthesis: {str(e)}")
            
            # Try with fallback voice if original fails
            if selected_voice != self.default_voice:
                logger.info(f"Attempting TTS with fallback voice: {self.default_voice}")
                try:
                    return self.synthesize(text, self.default_voice, None)
                except Exception as fallback_error:
                    logger.error(f"Error in fallback TTS synthesis: {str(fallback_error)}")
            
            # If everything fails, raise the original error
            raise
    
    def _get_voice_for_language(self, language_code: Optional[str]) -> Optional[str]:
        """
        Get the appropriate voice ID for a language code.
        
        Args:
            language_code: The language code
            
        Returns:
            A voice ID suitable for the language
        """
        if not language_code:
            return None
            
        # African language mappings
        voice_mappings = {
            "en-NG": "en-NG-EzinneNeural",  # Nigerian English (female)
            "en-NG-female": "en-NG-EzinneNeural",
            "en-NG-male": "en-NG-AbeoNeural",
            "en-KE": "en-KE-AsiliaNeural",  # Kenyan English
            "en-TZ": "en-TZ-ImaniNeural",   # Tanzanian English
            "en-ZA": "en-ZA-LeahNeural",    # South African English
            "sw": "sw-TZ-RehemaNeural",     # Swahili (Tanzania)
            "sw-KE": "sw-KE-ZuriNeural",    # Swahili (Kenya)
            "yo": "en-NG-EzinneNeural",     # Yoruba (fallback to Nigerian English)
            "ha": "en-NG-AbeoNeural",       # Hausa (fallback to Nigerian English)
            "ar": "ar-EG-SalmaNeural",      # Arabic (Egypt)
        }
        
        # Try exact match
        if language_code in voice_mappings:
            return voice_mappings[language_code]
            
        # Try language part only
        if '-' in language_code:
            lang_part = language_code.split('-')[0]
            if lang_part in voice_mappings:
                return voice_mappings[lang_part]
        
        # Return None if no mapping found
        return None
    
    async def _list_voices_async(self) -> List[Dict[str, Any]]:
        """Async method to list available voices."""
        try:
            voices = await edge_tts.list_voices()
            return voices
        except Exception as e:
            logger.error(f"Error listing Edge TTS voices: {str(e)}")
            return []
    
    def get_available_voices(self, language_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available voice options.
        
        Args:
            language_code: Optional language code to filter voices
            
        Returns:
            List of voice configurations
        """
        try:
            # Get all voices
            voices = asyncio.run(self._list_voices_async())
            
            # Filter by language if specified
            if language_code:
                voices = [v for v in voices if v["Locale"].startswith(language_code)]
            
            # Format the response
            result = []
            for voice in voices:
                voice_info = {
                    "name": voice["ShortName"],
                    "gender": voice["Gender"],
                    "language_code": voice["Locale"],
                    "display_name": voice["DisplayName"]
                }
                result.append(voice_info)
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing Edge TTS voices: {str(e)}")
            return []
    
    def save_to_file(self, audio_content: bytes, file_path: str) -> str:
        """
        Save audio content to a file.
        
        Args:
            audio_content: Audio data as bytes
            file_path: Path to save the file
            
        Returns:
            Path to the saved file
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write audio content to file
            with open(file_path, 'wb') as f:
                f.write(audio_content)
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving TTS audio to file: {str(e)}")
            raise
