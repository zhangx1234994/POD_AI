"""Runtime configuration for vendor-api-ops."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = Field(default="vendor-api-ops", validation_alias="VENDOR_API_OPS_SERVICE_NAME")
    admin_token: str | None = Field(default=None, validation_alias="VENDOR_API_OPS_ADMIN_TOKEN")
    allowed_clients: str = Field(
        default="127.0.0.1,::1,testclient,114.55.0.56,117.50.80.158",
        validation_alias="VENDOR_API_ALLOWED_CLIENTS",
    )
    request_timeout_seconds: float = Field(default=180.0, validation_alias="VENDOR_API_OPS_REQUEST_TIMEOUT_SECONDS")
    database_path: str = Field(default="runtime/vendor-api-ops.sqlite3", validation_alias="VENDOR_API_OPS_DATABASE_PATH")
    key_encryption_secret: str | None = Field(default=None, validation_alias="VENDOR_API_KEY_ENCRYPTION_SECRET")

    openai_base_url: str = Field(default="https://api.openai.com", validation_alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_compatible_base_url: str | None = Field(default=None, validation_alias="OPENAI_COMPATIBLE_BASE_URL")
    openai_compatible_api_key: str | None = Field(default=None, validation_alias="OPENAI_COMPATIBLE_API_KEY")
    kie_base_url: str = Field(default="https://api.kie.ai", validation_alias="KIE_BASE_URL")
    kie_api_key: str | None = Field(default=None, validation_alias="KIE_API_KEY")
    volcengine_base_url: str = Field(default="https://ark.cn-beijing.volces.com", validation_alias="VOLCENGINE_BASE_URL")
    volcengine_api_key: str | None = Field(default=None, validation_alias="VOLCENGINE_API_KEY")
    baidu_base_url: str = Field(default="https://aip.baidubce.com", validation_alias="BAIDU_BASE_URL")
    baidu_api_key: str | None = Field(default=None, validation_alias="BAIDU_API_KEY")
    baidu_secret_key: str | None = Field(default=None, validation_alias="BAIDU_SECRET_KEY")

    def resolved_database_path(self) -> Path:
        path = Path(self.database_path)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[1] / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
