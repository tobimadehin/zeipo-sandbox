# src/stt/providers/whisper_stt.py
import threading
import time
import os
import numpy as np
import whisper
import torch
from typing import Callable, Dict, Optional, Any, List

from static.constants import AVAILABLE_MODELS, logger
from src.stt.stt_base import STTProvider
from src.languages import WHISPER_LANGUAGES

class WhisperSTTProvider(STTProvider):
    """Whisper STT provider implementation."""
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize the Whisper STT provider.
        
        Args:
            device: Device to use (cuda or cpu)
        """
        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing Whisper STT provider with device: {self.device}")
        
        # Model cache
        self.models = {}
    
    def get_model(self, name: str):
        """
        Load and cache the requested model.
        
        Args:
            name: Model name to load
            
        Returns:
            Loaded Whisper model
        """
        if name not in AVAILABLE_MODELS:
            raise ValueError(f"Model {name} not available. Choose from {AVAILABLE_MODELS}")
        
        if name not in self.models:
            logger.info(f"Loading model: {name} on {self.device}")
            start_time = time.time()
            self.models[name] = whisper.load_model(name, device=self.device)
            load_time = time.time() - start_time
            logger.info(f"Model {name} loaded in {load_time:.2f} seconds")
        
        return self.models[name]
    
    def transcribe(self, audio_file: str, language: Optional[str] = None, task: str = "transcribe", model_name: str = "small", **kwargs) -> Dict[str, Any]:
        """
        Transcribe speech from an audio file using Whisper.
        
        Args:
            audio_file: Path to the audio file
            language: Language code for the transcription
            task: Task to perform (transcribe or translate)
            model_name: Name of the model to use
            **kwargs: Additional parameters to pass to Whisper
            
        Returns:
            Dictionary with transcription results
        """
        try:
            # Load model
            model = self.get_model(model_name)
            
            # Set options
            options = {"task": task}
            if language:
                options["language"] = language
                
            # Add additional parameters from kwargs
            options.update(kwargs)
            
            # Transcribe
            start_time = time.time()
            logger.info(f"Starting transcription of {audio_file} with model {model_name}")
            result = model.transcribe(audio_file, **options)
            process_time = time.time() - start_time
            
            # Get audio duration for RTF calculation
            audio = whisper.load_audio(audio_file)
            audio_duration = len(audio) / whisper.audio.SAMPLE_RATE
            rtf = process_time / audio_duration
            
            logger.info(f"Transcription completed in {process_time:.2f}s, RTF: {rtf:.2f}")
            
            # Add performance metrics
            result["_performance"] = {
                "process_time": process_time,
                "audio_duration": audio_duration,
                "real_time_factor": rtf,
                "device": str(model.device)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Whisper transcription: {str(e)}")
            raise
    
    def get_available_models(self) -> List[str]:
        """
        Get available Whisper models.
        
        Returns:
            List of available model names
        """
        return AVAILABLE_MODELS
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get languages supported by Whisper.
        
        Returns:
            List of language information dictionaries
        """
        result = []
        for code, name in WHISPER_LANGUAGES.items():
            result.append({
                "code": code,
                "name": name,
                "native_name": name.title()  # Just capitalize the English name as a fallback
            })
        return result
    
    def create_streaming_transcriber(
        self, 
        model_name: str = "small",
        language: Optional[str] = None,
        chunk_size_ms: int = 1000,
        buffer_size_ms: int = 5000,
        **kwargs
    ) -> Any:
        """
        Create a streaming transcription instance.
        
        Args:
            model_name: Name of the model to use
            language: Language code if known
            chunk_size_ms: Size of audio chunks to process
            buffer_size_ms: Size of the buffer window
            **kwargs: Additional parameters
            
        Returns:
            A streaming transcription instance
        """       
        from src.streaming.audio_streaming import AudioStreamManager
        
        # Load the model if not already loaded
        self.get_model(model_name)
        
        # Create and return a streaming transcriber
        return AudioStreamManager()
    