from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")

    environment: str = "local"
    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:45432/atlas"
    redis_url: str = "redis://localhost:46379/0"
    s3_endpoint_url: str = "http://localhost:49000"
    s3_access_key: str = "atlas"
    s3_secret_key: str = "atlas-local-secret"
    s3_raw_bucket: str = "atlas-raw"
    s3_processing_bucket: str = "atlas-processing"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=48080, ge=1, le=65535)
    admin_api_key: str = "replace-this-local-admin-key"
    redis_stream: str = "atlas.jobs"
    redis_consumer_group: str = "atlas-workers"
    scheduler_poll_seconds: int = Field(default=30, ge=5, le=3600)
    source_ingestion_enabled: bool = False
    geography_config_path: Path | None = None
    local_source_asset_root: Path | None = None
    ember_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "ATLAS_OPENAI_API_KEY"),
    )
    openai_organization: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_ORGANIZATION", "ATLAS_OPENAI_ORGANIZATION"),
    )
    openai_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_PROJECT", "ATLAS_OPENAI_PROJECT"),
    )
    translation_provider: str = "openai"
    translation_target_language: str = "tr"
    translation_requested_by: str = "atlas-intelligence-cli"
    translation_batch_size: int = Field(default=50, ge=1, le=50)
    openai_translation_model: str = "gpt-5.6-terra"
    openai_qa_model: str = "gpt-5.6-sol"
    openai_batch_enabled: bool = True
    multilingual_resolver_v2: bool = True

    def validate_runtime_security(self) -> None:
        if self.environment != "local" and self.admin_api_key == "replace-this-local-admin-key":
            raise ValueError("ATLAS_ADMIN_API_KEY must be changed outside local environment")


@lru_cache
def get_settings() -> Settings:
    return Settings()
