# src/tts/__init__.py
from typing import Optional
from config import settings
from static.constants import logger
from src.tts.tts_base import TTSProvider
from src.tts.integrations.google_tts import GoogleTTSProvider
from src.tts.integrations.edge_tts import EdgeTTSProvider

# Global TTS provider instance
_tts_provider: Optional[TTSProvider] = None
_edge_provider: Optional[EdgeTTSProvider] = None
_google_provider: Optional[GoogleTTSProvider] = None

def get_edge_provider() -> EdgeTTSProvider:
    """Get or create the Edge TTS provider."""
    global _edge_provider
    if _edge_provider is None:
        _edge_provider = EdgeTTSProvider()
    return _edge_provider

def get_google_provider() -> GoogleTTSProvider:
    """Get or create the Google TTS provider."""
    global _google_provider
    if _google_provider is None:
        _google_provider = GoogleTTSProvider()
    return _google_provider

def get_tts_provider(language_code: str = None) -> TTSProvider:
    """
    Get the configured TTS provider instance.
    
    Args:
        language_code: Optional language code for provider selection
    
    Returns:
        The TTS provider instance
    """
    global _tts_provider
    
    # Always use Edge TTS as primary provider
    if _tts_provider is None:
        try:
            logger.info("Initializing Edge TTS as primary provider")
            _tts_provider = get_edge_provider()
        except Exception as e:
            logger.error(f"Error initializing Edge TTS: {str(e)}")
            logger.warning("Falling back to Google TTS provider")
            _tts_provider = get_google_provider()
    
    return _tts_provider

def get_provider_for_language(language_code: str) -> TTSProvider:
    """
    Get the best provider for a specific language.
    This can be extended with more language-specific logic.
    
    Args:
        language_code: Language code
    
    Returns:
        The most appropriate TTS provider for the language
    """
    # Always default to Edge TTS for now
    return get_tts_provider()