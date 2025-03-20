# src/tts/voice_profiles.py
from typing import Dict, List, Optional
from enum import Enum

class VoiceGender(Enum):
    """Enumeration of voice genders."""
    MALE = "MALE"
    FEMALE = "FEMALE"

# Voice profiles for African languages
# Maps language codes to preferred voice settings
AFRICAN_VOICE_PROFILES = {

}

# Default voice configuration
DEFAULT_VOICE_PROFILE = {
    "name": "en-US-Neural2-F",
    "gender": VoiceGender.FEMALE,
    "fallback": "en-US-Neural2-J"
}

def get_voice_for_language(language_code: str) -> Dict:
    """
    Get the most appropriate voice for a language.
    
    Args:
        language_code: Language code (e.g., 'en-US', 'sw', 'yo')
        
    Returns:
        Voice profile dictionary
    """
    # Try exact match
    if language_code in AFRICAN_VOICE_PROFILES:
        return AFRICAN_VOICE_PROFILES[language_code]
    
    # Try language part only (e.g., 'en' from 'en-US')
    if '-' in language_code:
        lang_part = language_code.split('-')[0]
        if lang_part in AFRICAN_VOICE_PROFILES:
            return AFRICAN_VOICE_PROFILES[lang_part]
    
    # Return default
    return DEFAULT_VOICE_PROFILE
