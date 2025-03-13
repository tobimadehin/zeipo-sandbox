"""
Information about languages supported by Whisper, with special focus on African languages.
"""

# Whisper language codes dictionary
# Maps language codes to full language names
WHISPER_LANGUAGES = {
    "en": "english",
    "zh": "chinese",
    "de": "german",
    "es": "spanish",
    "ru": "russian",
    "ko": "korean",
    "fr": "french",
    "ja": "japanese",
    "pt": "portuguese",
    "tr": "turkish",
    "pl": "polish",
    "ca": "catalan",
    "nl": "dutch",
    "ar": "arabic",
    "sv": "swedish",
    "it": "italian",
    "id": "indonesian",
    "hi": "hindi",
    "fi": "finnish",
    "vi": "vietnamese",
    "he": "hebrew",
    "uk": "ukrainian",
    "el": "greek",
    "ms": "malay",
    "cs": "czech",
    "ro": "romanian",
    "da": "danish",
    "hu": "hungarian",
    "ta": "tamil",
    "no": "norwegian",
    "th": "thai",
    "ur": "urdu",
    "hr": "croatian",
    "bg": "bulgarian",
    "lt": "lithuanian",
    "la": "latin",
    "mi": "maori",
    "ml": "malayalam",
    "cy": "welsh",
    "sk": "slovak",
    "te": "telugu",
    "fa": "persian",
    "lv": "latvian",
    "bn": "bengali",
    "sr": "serbian",
    "az": "azerbaijani",
    "sl": "slovenian",
    "kn": "kannada",
    "et": "estonian",
    "mk": "macedonian",
    "br": "breton",
    "eu": "basque",
    "is": "icelandic",
    "hy": "armenian",
    "ne": "nepali",
    "mn": "mongolian",
    "bs": "bosnian",
    "kk": "kazakh",
    "sq": "albanian",
    "sw": "swahili",
    "gl": "galician",
    "mr": "marathi",
    "pa": "punjabi",
    "si": "sinhala",
    "km": "khmer",
    "sn": "shona",
    "yo": "yoruba",
    "so": "somali",
    "af": "afrikaans",
    "oc": "occitan",
    "ka": "georgian",
    "be": "belarusian",
    "tg": "tajik",
    "sd": "sindhi",
    "gu": "gujarati",
    "am": "amharic",
    "yi": "yiddish",
    "lo": "lao",
    "uz": "uzbek",
    "fo": "faroese",
    "ht": "haitian creole",
    "ps": "pashto",
    "tk": "turkmen",
    "nn": "nynorsk",
    "mt": "maltese",
    "sa": "sanskrit",
    "lb": "luxembourgish",
    "my": "myanmar",
    "bo": "tibetan",
    "tl": "tagalog",
    "mg": "malagasy",
    "as": "assamese",
    "tt": "tatar",
    "haw": "hawaiian",
    "ln": "lingala",
    "ha": "hausa",
    "ba": "bashkir",
    "jw": "javanese",
    "su": "sundanese",
    "yue": "cantonese",
}

# List of African languages supported by Whisper
AFRICAN_LANGUAGES = {
    "af": "afrikaans",      # South Africa, Namibia
    "am": "amharic",        # Ethiopia
    "ar": "arabic",         # North Africa
    "ha": "hausa",          # Nigeria, Niger, Ghana
    "ln": "lingala",        # DR Congo, Congo
    "mg": "malagasy",       # Madagascar
    "sn": "shona",          # Zimbabwe
    "so": "somali",         # Somalia, Ethiopia
    "sw": "swahili",        # East Africa
    "yo": "yoruba",         # Nigeria, Benin
}

# Languages important for Zeipo.ai based on project documents
ZEIPO_TARGET_LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "ha": "Hausa",
    "sw": "Swahili",
    "yo": "Yoruba",
}

# Check if a language is supported by Whisper
def is_language_supported(language_code):
    """Check if a language code is supported by Whisper."""
    return language_code.lower() in WHISPER_LANGUAGES

# Get the full language name from a code
def get_language_name(language_code):
    """Get the full language name from a language code."""
    if is_language_supported(language_code):
        return WHISPER_LANGUAGES[language_code.lower()]
    return "unknown"