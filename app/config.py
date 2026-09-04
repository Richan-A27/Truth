from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    database_url: str = "postgresql+asyncpg://truth_user:truth_pass@localhost:5432/truth_db"

    semantic_scholar_api_key: str = ""

    gdelt_timeout_seconds: float = 8.0
    semantic_scholar_timeout_seconds: float = 8.0
    wikipedia_timeout_seconds: float = 8.0

    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
