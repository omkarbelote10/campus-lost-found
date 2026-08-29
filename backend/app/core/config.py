from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/clfis_db"
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days; there is no refresh-token flow
    QR_TOKEN_EXPIRE_MINUTES: int = 15
    
    # CORS. Set ALLOWED_ORIGINS in the environment to serve the app from a LAN
    # address; localStorage and CORS are both per-origin, so a host that is not
    # listed here cannot sign in.
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # Campus Email Domain
    CAMPUS_EMAIL_DOMAIN: str = os.getenv("CAMPUS_EMAIL_DOMAIN", "college.edu")
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "backend/uploads"
    
    # ML Models
    SIGLIP_MODEL: str = "google/siglip-base-patch16-224"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
