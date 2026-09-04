from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    database_url: str = "postgresql+asyncpg://truth_user:truth_pass@localhost:5432/truth_db"

    semantic_scholar_api_key: str = ""

    # Per-source ceilings, all bounded by evidence_deadline_seconds: whatever
    # has not answered by the deadline is cancelled and the verdict is formed
    # from the sources that did.
    gdelt_timeout_seconds: float = 2.5
    semantic_scholar_timeout_seconds: float = 2.5
    wikipedia_timeout_seconds: float = 2.5
    # Hard cap while no source has answered yet; once one has, the others get
    # only evidence_grace_seconds before they are abandoned.
    evidence_deadline_seconds: float = 2.5
    evidence_grace_seconds: float = 0.25

    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
