# src/tts/tts_base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import os

class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    def synthesize(self, text: str, voice_id: str = None, language_code: str = None) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: The text to synthesize
            voice_id: Specific voice identifier
            language_code: Language code if different from default
            
        Returns:
            Audio data as bytes
        """
        pass
    
    @abstractmethod
    def get_available_voices(self, language_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available voice options.
        
        Args:
            language_code: Optional language code to filter voices
            
        Returns:
            List of voice configurations
        """
        pass
    
    @abstractmethod
    def save_to_file(self, audio_content: bytes, file_path: str) -> str:
        """
        Save audio content to a file.
        
        Args:
            audio_content: Audio data as bytes
            file_path: Path to save the file
            
        Returns:
            Path to the saved file
        """
        pass
    