# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./zeipo.db"
    API_V1_STR: str = "/api/v1"
    
    AT_USER: str = "sandbox"  
    AT_API_KEY: str = ""
    AT_PHONE: str = ""

    WEBHOOK_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"

settings = Settings()
