from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # Comma-separated or list of allowed origins
    ALLOWED_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000"
    
    # Default database URL - supports SQLite and PostgreSQL
    DATABASE_URL: str = "sqlite:///./ipo_intelligence.db"
    
    # Gate dev seeding
    ENABLE_DEV_SEED: bool = True
    
    # Official Source Integrations (NSE & SEBI)
    NSE_BASE_URL: str = "https://www.nseindia.com"
    SEBI_BASE_URL: str = "https://www.sebi.gov.in"
    SEBI_REQUEST_TIMEOUT_SECONDS: int = 30
    SEBI_MAX_DOCUMENT_SIZE_MB: int = 35
    SEBI_MAX_DOCUMENTS_PER_SYNC: int = 15
    INGESTION_SYNC_INTERVAL_MINUTES: int = 15
    ENABLE_SCHEDULED_INGESTION: bool = False
    INGESTION_API_KEY: Union[str, None] = None
    RUN_LIVE_TESTS: bool = False

    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
