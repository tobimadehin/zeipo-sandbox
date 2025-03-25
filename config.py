# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./zeipo.db"
    API_V1_STR: str = "/api/v1"
    
    TELEPHONY_PROVIDER: str = "voip_simulator"
    DEFAULT_TELEPHONY_PROVIDER: str = "voip_simulator"
    
    AT_USER: str = "sandbox"  
    AT_API_KEY: str = ""
    AT_PHONE: str = ""
    
    VOIP_SIMULATOR_ENABLED: bool = True

    WEBHOOK_URL: str = "http://localhost:8000"
    
    WS_URL: str = "ws://localhost:8000/api/v1/ws"
    
    GOOGLE_TTS_ENABLED: bool = False
    GOOGLE_TTS_DEFAULT_VOICE_LOCALE: str = "en-US"
    GOOGLE_TTS_DEFAULT_VOICE_NAME: str = "en-US-Neural2-F"
    
    EDGE_TTS_DEFAULT_VOICE: str = "en-NG-EzinneNeural"
    TTS_CACHE_DIR: str = "data/tts_cache"
    
    class Config:
        env_file = ".env"

settings = Settings()
