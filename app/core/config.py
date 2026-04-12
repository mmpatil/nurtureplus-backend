import logging
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""
    
    # Database
    database_url: str = "postgresql+asyncpg://nurture_user:password123@localhost:5432/nurtureplus_db"
    
    # Firebase
    google_application_credentials: str = "./service-account.json"
    
    # Security
    dev_bypass_auth: bool = False
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    
    # Logging
    log_level: str = "INFO"
    
    # App
    app_title: str = "Nurture+ API"
    app_version: str = "1.0.0"
    
    # Firebase credentials as JSON string (used on Vercel/serverless)
    firebase_service_account_json: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Return allowed origins as a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


settings = Settings()


def setup_logging():
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


logger = setup_logging()
