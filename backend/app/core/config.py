import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "NEXUS"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database (Default: local SQLite database file)
    DATABASE_URL: str = "sqlite+aiosqlite:///./nexus.db"
    
    # Gemini AI
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    
    # Network & CORS
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    
    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPIC_SENSORS: str = "nexus/sensors/telemetry"
    
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
