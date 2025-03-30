# src/stt/stt_base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List

class STTProvider(ABC):
    """Abstract base class for STT providers."""
    
    @abstractmethod
    def transcribe(self, audio_file: str, language: Optional[str] = None, task: str = "transcribe", **kwargs) -> Dict[str, Any]:
        """
        Transcribe speech from an audio file.
        
        Args:
            audio_file: Path to the audio file
            language: Language code for the transcription
            task: Task to perform (e.g., "transcribe", "translate")
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dictionary with transcription results
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        Get available models for this provider.
        
        Returns:
            List of available model names
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get supported languages for this provider.
        
        Returns:
            List of language information dictionaries
        """
        pass
        
    @abstractmethod
    def create_streaming_transcriber(
        self, 
        model_name: str = "tiny",
    ):
        """
        Create a streaming transcription instance.
        
        Args:
            model_name: Name of the model to use
        """
        pass
    