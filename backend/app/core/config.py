from pydantic_settings import BaseSettings
from typing import List, Optional
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    #Application
    APP_NAME: str = "AI-Powered API Security System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = True

    #SERVER
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # CORS - Allow frontend origins
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",      # React default
        "http://localhost:5173",      # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://localhost:3001",
        "https://api-security-system.vercel.app",
        "https://uncohesively-homeliest-briella.ngrok-free.dev"
    ]

    #Database
    DATABASE_URL: str

    #Redis
    REDIS_URL: str

    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    BCRYPT_ROUNDS: int = 12
    MAX_FAILED_LOGIN_ATTEMPTS: int = 10
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # Frontend URL (for reset/email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # SMTP Email Settings (optional — leave blank for dev/log-only mode)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    #Security
    RATE_LIMIT_WINDOW: int = 60 #seconds
    MAX_REQUESTS_PER_MINUTE: int = 100

    #Block Durations(seconds)
    BLOCK_SOFT_DURATION: int = 7200 #2 hours
    BLOCK_MEDIUM_DURATION: int = 21600 #6 hours
    BLOCK_HARD_DURATION: int = 43200 #12 hour

    #Logging
    LOG_LEVEL: str = "INFO"

    #Feature thresholds
    HIGH_REQUEST_THRESHOLD: int = 50
    HIGH_RATIO_THRESHOLD: float = 0.8
    HIGH_ENTROPY_THRESHOLD: float = 0.7

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
