# src/tts/__init__.py
from typing import Optional
from config import settings
from static.constants import logger
from .tts_base import TTSProvider
from .integrations.google_tts import GoogleTTSProvider

# Global TTS provider instance
_tts_provider: Optional[TTSProvider] = None

def get_tts_provider() -> TTSProvider:
    """
    Get the configured TTS provider instance.
    
    Returns:
        The TTS provider instance
    """
    global _tts_provider
    
    if _tts_provider is None:
        # Initialize based on configuration
        if settings.GOOGLE_TTS_ENABLED:
            logger.info("Initializing Google TTS provider")
            _tts_provider = GoogleTTSProvider()
        else:
            logger.warning("No TTS provider enabled, using Google TTS as fallback")
            _tts_provider = GoogleTTSProvider()
    
    return _tts_provider
