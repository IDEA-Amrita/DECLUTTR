import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./decluttr.db")
    
    # File storage
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/decluttr")
    THUMBNAILS_DIR: str = os.getenv("THUMBNAILS_DIR", "/tmp/decluttr/thumbnails")
    
    # Scan settings
    PHASH_THRESHOLD: int = 5  # Distance threshold for near-duplicate detection
    LARGE_FILE_THRESHOLD_MB: int = 50
    THUMBNAIL_SIZE: int = 512
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure directories exist
Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.THUMBNAILS_DIR).mkdir(parents=True, exist_ok=True)