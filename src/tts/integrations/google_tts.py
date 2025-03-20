# src/tts/google_tts.py
import os
import uuid
from typing import Dict, List, Optional, Any
from google.cloud import texttospeech
from config import settings
from src.utils.helpers import gen_uuid_16
from static.constants import logger

from ..tts_base import TTSProvider
from ..audio_cache import TTSAudioCache
from ..voice_profiles import get_voice_for_language, VoiceGender

class GoogleTTSProvider(TTSProvider):
    """Google Cloud Text-to-Speech provider implementation."""
    
    def __init__(self):
        """Initialize the Google TTS client and cache."""
        self.client = texttospeech.TextToSpeechClient()
        self.cache = TTSAudioCache(settings.TTS_CACHE_DIR)
        self.default_language = settings.GOOGLE_TTS_DEFAULT_VOICE_LOCALE
        self.default_voice = settings.GOOGLE_TTS_DEFAULT_VOICE_NAME
        
        logger.info(f"Google TTS initialized with default language: {self.default_language}")
    
    def synthesize(self, text: str, voice_id: str = None, language_code: str = None) -> bytes:
        """
        Synthesize speech from text using Google TTS.
        
        Args:
            text: The text to synthesize
            voice_id: Specific voice name (e.g., 'en-US-Neural2-F')
            language_code: Language code (e.g., 'en-US', 'sw')
            
        Returns:
            Audio data as bytes
        """
        # Use default language and voice if not specified
        language_code = language_code or self.default_language
        
        # Get voice profile if not explicitly provided
        if voice_id is None:
            voice_profile = get_voice_for_language(language_code)
            voice_id = voice_profile["name"]
        
        # Check cache first
        cache_path = self.cache.get_cached_audio_path(text, voice_id, language_code)
        if cache_path:
            logger.info(f"Using cached TTS audio for: {text[:30]}...")
            with open(cache_path, 'rb') as f:
                return f.read()
        
        try:
            # Set input text
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Get language code from voice name if not provided
            if not language_code and '-' in voice_id:
                language_code = '-'.join(voice_id.split('-')[:2])
            
            # Build voice parameters
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_id
            )
            
            # Set audio config for MP3
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,  # Normal speed
                pitch=0.0,  # Default pitch
                volume_gain_db=0.0  # Default volume
            )
            
            # Call Google TTS API
            logger.info(f"Synthesizing speech for text: {text[:50]}...")
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Save to cache
            audio_content = response.audio_content
            cache_file = os.path.join(
                settings.TTS_CACHE_DIR,
                f"tts_{gen_uuid_16().hex}.mp3"
            )
            with open(cache_file, 'wb') as f:
                f.write(audio_content)
            
            self.cache.cache_audio(text, voice_id, language_code, cache_file)
            
            return audio_content
            
        except Exception as e:
            logger.error(f"Error in Google TTS synthesis: {str(e)}")
            
            # Try with fallback voice if original fails
            if voice_id != self.default_voice:
                logger.info(f"Attempting TTS with fallback voice: {self.default_voice}")
                try:
                    return self.synthesize(text, self.default_voice, self.default_language)
                except Exception as fallback_error:
                    logger.error(f"Error in fallback TTS synthesis: {str(fallback_error)}")
            
            # If everything fails, raise the original error
            raise
    
    def get_available_voices(self, language_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available voice options from Google TTS.
        
        Args:
            language_code: Optional language code to filter voices
            
        Returns:
            List of voice configurations
        """
        try:
            # List available voices
            response = self.client.list_voices(language_code=language_code)
            
            voices = []
            for voice in response.voices:
                # Get language codes and voice name
                voice_info = {
                    "name": voice.name,
                    "language_codes": voice.language_codes,
                    "ssml_gender": str(voice.ssml_gender),
                    "natural_sample_rate_hertz": voice.natural_sample_rate_hertz
                }
                voices.append(voice_info)
            
            return voices
            
        except Exception as e:
            logger.error(f"Error listing Google TTS voices: {str(e)}")
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