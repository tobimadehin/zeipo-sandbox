# src/stt/__init__.py
from typing import Optional
from config import settings
from static.constants import logger
from .stt_base import STTProvider
from .integrations.whisper_stt import WhisperSTTProvider

# Global STT provider instance
_stt_provider: Optional[STTProvider] = None
_whisper_provider: Optional[WhisperSTTProvider] = None

def get_whisper_provider() -> WhisperSTTProvider:
    """Get or create the Whisper STT provider."""
    global _whisper_provider
    if _whisper_provider is None:
        _whisper_provider = WhisperSTTProvider()
    return _whisper_provider

def get_stt_provider(language_code: str = None) -> STTProvider:
    """
    Get the configured STT provider instance.
    
    Args:
        language_code: Optional language code for provider selection
    
    Returns:
        The STT provider instance
    """
    global _stt_provider
    
    # Always use Whisper as primary provider for now
    if _stt_provider is None:
        try:
            logger.info("Initializing Whisper as primary STT provider")
            _stt_provider = get_whisper_provider()
        except Exception as e:
            logger.error(f"Error initializing Whisper STT: {str(e)}")
            raise
    
    return _stt_provider

def get_provider_for_language(language_code: str) -> STTProvider:
    """
    Get the best provider for a specific language.
    This can be extended with more language-specific logic.
    
    Args:
        language_code: Language code
    
    Returns:
        The most appropriate STT provider for the language
    """
    # Default to Whisper for now
    return get_stt_provider() 