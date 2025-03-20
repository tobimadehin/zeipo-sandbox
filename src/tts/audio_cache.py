# src/tts/audio_cache.py
import os
import hashlib
import json
from typing import Dict, Optional
from static.constants import logger

class TTSAudioCache:
    """Cache for TTS audio to avoid regenerating the same speech."""
    
    def __init__(self, cache_dir: str):
        """
        Initialize the audio cache.
        
        Args:
            cache_dir: Directory to store cached audio files
        """
        self.cache_dir = cache_dir
        self.index_file = os.path.join(cache_dir, "cache_index.json")
        self.cache_index: Dict[str, str] = {}
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            
        # Load cache index if it exists
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r') as f:
                    self.cache_index = json.load(f)
            except Exception as e:
                logger.error(f"Error loading TTS cache index: {str(e)}")
                self.cache_index = {}
    
    def _generate_key(self, text: str, voice_id: str, language_code: str) -> str:
        """Generate a cache key from the text and voice parameters."""
        key_string = f"{text}|{voice_id}|{language_code}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_cached_audio_path(self, text: str, voice_id: str, language_code: str) -> Optional[str]:
        """
        Get the path to cached audio if it exists.
        
        Args:
            text: The text that was synthesized
            voice_id: The voice ID used
            language_code: The language code used
            
        Returns:
            Path to the cached audio file, or None if not found
        """
        key = self._generate_key(text, voice_id, language_code)
        file_path = self.cache_index.get(key)
        
        if file_path and os.path.exists(file_path):
            return file_path
        return None
    
    def cache_audio(self, text: str, voice_id: str, language_code: str, audio_path: str) -> str:
        """
        Add an audio file to the cache.
        
        Args:
            text: The text that was synthesized
            voice_id: The voice ID used
            language_code: The language code used
            audio_path: Path to the audio file
            
        Returns:
            Path to the cached audio file
        """
        key = self._generate_key(text, voice_id, language_code)
        self.cache_index[key] = audio_path
        
        # Save updated index
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.cache_index, f)
        except Exception as e:
            logger.error(f"Error saving TTS cache index: {str(e)}")
        
        return audio_path
    
    def clear_cache(self) -> None:
        """Clear the entire cache, removing all files."""
        for _, file_path in self.cache_index.items():
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing cached file {file_path}: {str(e)}")
        
        self.cache_index = {}
        
        # Save empty index
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.cache_index, f)
        except Exception as e:
            logger.error(f"Error saving empty TTS cache index: {str(e)}")
            