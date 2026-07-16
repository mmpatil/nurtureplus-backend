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
    account_delete_reauth_minutes: int = 15
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    
    # Logging
    log_level: str = "INFO"

    # AI-assisted analysis
    openai_api_key: Optional[str] = None
    voice_llm_model: str = "gpt-4o-mini"
    food_ai_model: Optional[str] = None
    food_ai_autosave_threshold: float = 0.85
    voice_autosave_threshold: float = 0.85
    serpapi_api_key: Optional[str] = None
    website_lookup_timeout_seconds: float = 5.0
    website_lookup_enabled: bool = True
    
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

    @property
    def resolved_food_ai_model(self) -> str:
        """Return the configured food model, falling back to the shared voice model."""
        return self.food_ai_model or self.voice_llm_model


settings = Settings()


def setup_logging():
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


logger = setup_logging()
