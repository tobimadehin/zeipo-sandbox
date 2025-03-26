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
    
    ASTERISK_HOST: str = "localhost"
    AT_SIP_DOMAIN: str = "ke.sip.africastalking.com"
    AT_SIP_USERNAME: str = ""  
    AT_SIP_PASSWORD: str = "" 

    WEBHOOK_URL: str = "http://localhost:8000"
    
    WS_URL: str = "ws://localhost:8000/api/v1/ws"
    
    GOOGLE_TTS_ENABLED: bool = False
    GOOGLE_TTS_DEFAULT_VOICE_LOCALE: str = "en-US"
    GOOGLE_TTS_DEFAULT_VOICE_NAME: str = "en-US-Neural2-F"
    
    EDGE_TTS_DEFAULT_VOICE: str = "en-NG-EzinneNeural"
    TTS_CACHE_DIR: str = "data/tts_cache"
    
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    GF_SECURITY_ADMIN_USER: str = ""
    GF_SECURITY_ADMIN_PASSWORD: str = ""
    GF_USERS_ALLOW_SIGN_UP: bool = False
    GF_INSTALL_PLUGINS: str = ""
    
    ASTERISK_ARI_URL: str = ""
    ASTERISK_ARI_USERNAME: str = ""
    ASTERISK_ARI_PASSWORD: str = ""
    
    ASTERISK_UID=1000
    ASTERISK_GID=1000
    
    class Config:
        env_file = ".env"

settings = Settings()
