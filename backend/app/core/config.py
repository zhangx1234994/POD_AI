"""应用配置。"""

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ignore unknown env keys so stale/optional integrations don't prevent boot.
    # Always load `backend/.env` no matter where uvicorn is started from.
    _backend_env_file = (Path(__file__).resolve().parents[2] / ".env").as_posix()
    model_config = SettingsConfigDict(env_file=_backend_env_file, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PODI Backend"
    oss_access_key: str | None = Field(default=None, env=["OSS_ACCESS_KEY", "OSS_AK"])
    oss_secret_key: str | None = Field(default=None, env=["OSS_SECRET_KEY", "OSS_SK"])
    database_url: str = Field(..., env="DATABASE_URL")
    oss_role_arn: str | None = Field(default=None, env="OSS_ROLE_ARN")
    oss_bucket: str = Field(default="pod-oss-private", env="OSS_BUCKET")
    oss_region: str = Field(default="oss-cn-hangzhou", env="OSS_REGION")
    oss_endpoint: str = Field(default="oss-cn-hangzhou.aliyuncs.com", env="OSS_ENDPOINT")
    oss_callback_host: str | None = Field(default=None, env="OSS_CALLBACK_HOST")
    oss_root_prefix: str = Field(default="uploads", env="OSS_ROOT_PREFIX")
    download_domain: str = Field(default="https://oss-mock.local", env="OSS_DOWNLOAD_DOMAIN")
    oss_public_domain: str | None = Field(default=None, env=["OSS_PUBLIC_DOMAIN", "OSS_DOWNLOAD_DOMAIN"])
    oss_sts_duration: int = Field(default=900, env="OSS_STS_DURATION")
    upload_token_secret: str = Field(default="change-me", env="UPLOAD_TOKEN_SECRET")
    upload_token_ttl: int = Field(default=3600, env="UPLOAD_TOKEN_TTL")
    admin_api_token: str | None = Field(default=None, env="ADMIN_API_TOKEN")
    jwt_secret_key: str = Field(default="super-secret", env="JWT_SECRET_KEY")
    jwt_access_token_expires: int = Field(default=3600, env="JWT_ACCESS_TOKEN_EXPIRES")
    jwt_refresh_token_expires: int = Field(default=604800, env="JWT_REFRESH_TOKEN_EXPIRES")
    service_api_token: str | None = Field(default=None, env="SERVICE_API_TOKEN")
    # When Coze Studio runs on a different machine, its requests will not look like "internal"
    # (127.x/10.x/192.168.x/172.16.x). Allowlist its source IP(s) here.
    # Comma-separated, e.g. "1.2.3.4,5.6.7.8".
    coze_trusted_ips: str | None = Field(default=None, env="COZE_TRUSTED_IPS")
    baidu_api_key: str | None = Field(default=None, env="BAIDU_API_KEY")
    baidu_secret_key: str | None = Field(default=None, env="BAIDU_SECRET_KEY")
    baidu_base_url: str = Field(default="https://aip.baidubce.com", env="BAIDU_BASE_URL")
    volcengine_api_key: str | None = Field(default=None, env="VOLCENGINE_API_KEY")
    volcengine_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com",
        env="VOLCENGINE_BASE_URL",
    )
    coze_base_url: str | None = Field(default=None, env="COZE_BASE_URL")
    coze_api_token: str | None = Field(default=None, env="COZE_API_TOKEN")
    coze_default_timeout: int = Field(default=180, env="COZE_DEFAULT_TIMEOUT")
    coze_loop_base_url: str | None = Field(default=None, env="COZE_LOOP_BASE_URL")
    # Internal URL that Coze containers can use to call back into this backend.
    # Default is host.docker.internal for Lima/Docker setups.
    podi_internal_base_url: str = Field(default="http://host.docker.internal:8099", env="PODI_INTERNAL_BASE_URL")
    executor_config_path: str = Field(default="config/executors.yaml", env="EXECUTOR_CONFIG_PATH")
    ability_task_max_workers: int = Field(default=4, env="ABILITY_TASK_MAX_WORKERS")
    eval_run_max_workers: int = Field(default=6, env="EVAL_RUN_MAX_WORKERS")
    # Fan-out concurrency for "裂变数量" runs (Coze async submit + polling).
    # Default to 1 (sequential) for stability; increase when infra is ready.
    eval_fanout_max_workers: int = Field(default=1, env="EVAL_FANOUT_MAX_WORKERS")
    eval_public_enabled: bool = Field(default=False, env="EVAL_PUBLIC_ENABLED")
    # Optional shared secret for public evaluation APIs. If unset and
    # eval_public_enabled=true, the endpoints are open (intended for internal LAN).
    eval_public_token: str | None = Field(default=None, env="EVAL_PUBLIC_TOKEN")
    # Admin token for maintaining eval workflow display name/notes/categories without login.
    # Default is set for local/internal use; override via env in real deployments.
    eval_admin_token: str | None = Field(default="Chrd5@0987", env="EVAL_ADMIN_TOKEN")
    # If a Coze workflow returns a raw ComfyUI task id (not a PODI ability_task id),
    # we can fall back to another workflow to resolve images.
    coze_comfyui_callback_workflow_id: str | None = Field(default=None, env="COZE_COMFYUI_CALLBACK_WORKFLOW_ID")
    # When set, force all ComfyUI abilities to route to a single executor id.
    # Useful for testing (single ComfyUI server) to avoid node/plugin mismatch.
    comfyui_default_executor_id: str | None = Field(default=None, env="COMFYUI_DEFAULT_EXECUTOR_ID")
    # Enable queue-aware routing across multiple ComfyUI executors.
    # Keep False until all ComfyUI servers are standardized.
    comfyui_route_by_queue: bool = Field(default=False, env="COMFYUI_ROUTE_BY_QUEUE")
    # Soft target for ComfyUI queue depth per executor. Router will prefer nodes under this value.
    # Business-side schedulers can use this as a batch size hint.
    comfyui_queue_batch_size: int = Field(default=10, env="COMFYUI_QUEUE_BATCH_SIZE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
