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
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=1800, env="DATABASE_POOL_RECYCLE")
    oss_role_arn: str | None = Field(default=None, env="OSS_ROLE_ARN")
    oss_bucket: str = Field(default="pod-oss-private", env="OSS_BUCKET")
    oss_region: str = Field(default="oss-cn-hangzhou", env="OSS_REGION")
    # Public/browser-facing endpoint. This value is returned to web clients for
    # direct STS uploads, so it must remain reachable from users' browsers.
    oss_endpoint: str = Field(default="oss-cn-hangzhou.aliyuncs.com", env="OSS_ENDPOINT")
    # Optional server-side endpoint for backend OSS reads/writes. On Aliyun ECS
    # in the same region/VPC as OSS, set this to the internal endpoint while
    # keeping OSS_ENDPOINT public for browser uploads.
    oss_internal_endpoint: str | None = Field(default=None, env="OSS_INTERNAL_ENDPOINT")
    oss_callback_host: str | None = Field(default=None, env="OSS_CALLBACK_HOST")
    oss_root_prefix: str = Field(default="uploads", env="OSS_ROOT_PREFIX")
    download_domain: str = Field(default="https://oss-mock.local", env="OSS_DOWNLOAD_DOMAIN")
    oss_public_domain: str | None = Field(default=None, env=["OSS_PUBLIC_DOMAIN", "OSS_DOWNLOAD_DOMAIN"])
    oss_sts_duration: int = Field(default=900, env="OSS_STS_DURATION")
    oss_connect_timeout: int = Field(default=120, env="OSS_CONNECT_TIMEOUT")
    oss_upload_retries: int = Field(default=3, env="OSS_UPLOAD_RETRIES")
    oss_resumable_threshold_mb: int = Field(default=8, env="OSS_RESUMABLE_THRESHOLD_MB")
    oss_resumable_part_size_mb: int = Field(default=8, env="OSS_RESUMABLE_PART_SIZE_MB")
    oss_resumable_threads: int = Field(default=2, env="OSS_RESUMABLE_THREADS")
    # Default DPI/PPI metadata written to generated raster images before they are
    # persisted to OSS. Set to 0 to keep model/vendor output bytes untouched.
    output_image_default_dpi: int = Field(default=150, env="OUTPUT_IMAGE_DEFAULT_DPI")
    upload_token_secret: str = Field(default="change-me", env="UPLOAD_TOKEN_SECRET")
    upload_token_ttl: int = Field(default=3600, env="UPLOAD_TOKEN_TTL")
    admin_api_token: str | None = Field(default=None, env="ADMIN_API_TOKEN")
    agent_jwt_secrets: str = Field(default="default:change-me", env="AGENT_JWT_SECRETS")
    agent_jwt_default_kid: str = Field(default="default", env="AGENT_JWT_DEFAULT_KID")
    agent_task_token_ttl: int = Field(default=600, env="AGENT_TASK_TOKEN_TTL")
    agent_heartbeat_token_ttl: int = Field(default=3600, env="AGENT_HEARTBEAT_TOKEN_TTL")
    agent_task_timeout_seconds: int = Field(default=3600, env="AGENT_TASK_TIMEOUT_SECONDS")
    agent_enroll_code_ttl_seconds: int = Field(default=600, env="AGENT_ENROLL_CODE_TTL_SECONDS")
    agent_bootstrap_heartbeat_interval: int = Field(default=60, env="AGENT_BOOTSTRAP_HEARTBEAT_INTERVAL")
    agent_bootstrap_install_key: str | None = Field(default=None, env="AGENT_BOOTSTRAP_INSTALL_KEY")
    kie_task_timeout_seconds: int = Field(default=900, env="KIE_TASK_TIMEOUT_SECONDS")
    agent_debug_tokens: str | None = Field(default=None, env="AGENT_DEBUG_TOKENS")
    jwt_secret_key: str = Field(default="super-secret", env="JWT_SECRET_KEY")
    jwt_access_token_expires: int = Field(default=3600, env="JWT_ACCESS_TOKEN_EXPIRES")
    jwt_refresh_token_expires: int = Field(default=604800, env="JWT_REFRESH_TOKEN_EXPIRES")
    service_api_token: str | None = Field(default=None, env="SERVICE_API_TOKEN")
    wallet_callback_token: str | None = Field(default=None, env="WALLET_CALLBACK_TOKEN")
    wallet_callback_signing_secret: str | None = Field(default=None, env="WALLET_CALLBACK_SIGNING_SECRET")
    wallet_callback_signature_ttl_seconds: int = Field(default=300, env="WALLET_CALLBACK_SIGNATURE_TTL_SECONDS")
    wallet_auto_expense_enabled: bool = Field(default=True, env="WALLET_AUTO_EXPENSE_ENABLED")
    wallet_points_per_usd: int = Field(default=100, env="WALLET_POINTS_PER_USD")
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
    vendor_api_enabled: bool = Field(default=True, env="VENDOR_API_ENABLED")
    vendor_api_base_url: str = Field(default="http://127.0.0.1:8310", env="VENDOR_API_BASE_URL")
    vendor_api_token: str | None = Field(default=None, env="VENDOR_API_TOKEN")
    vendor_api_timeout_seconds: int = Field(default=180, env="VENDOR_API_TIMEOUT_SECONDS")
    # Keep a deploy-time escape hatch while migrating existing Baidu/Volcengine/KIE
    # handlers. Set to false after vendor-api-ops is verified on the target host.
    vendor_api_legacy_fallback_enabled: bool = Field(default=True, env="VENDOR_API_LEGACY_FALLBACK_ENABLED")
    coze_base_url: str | None = Field(default=None, env="COZE_BASE_URL")
    coze_api_token: str | None = Field(default=None, env="COZE_API_TOKEN")
    coze_default_timeout: int = Field(default=180, env="COZE_DEFAULT_TIMEOUT")
    coze_loop_base_url: str | None = Field(default=None, env="COZE_LOOP_BASE_URL")
    # Internal URL that Coze containers can use to call back into this backend.
    # Default is host.docker.internal for Lima/Docker setups.
    podi_internal_base_url: str = Field(default="http://host.docker.internal:8099", env="PODI_INTERNAL_BASE_URL")
    # Base URL exposed to ComfyUI agents for fetching manifests from this backend.
    agent_manifest_base_url: str | None = Field(default=None, env="AGENT_MANIFEST_BASE_URL")
    # Local storage for uploaded desktop installer files (served by backend download endpoint).
    desktop_release_storage_dir: str = Field(
        default="runtime/desktop_releases",
        env="DESKTOP_RELEASE_STORAGE_DIR",
    )
    # Local storage for business project export packages. Packages currently
    # contain manifest/evidence files and reference media through controlled URLs.
    business_export_storage_dir: str = Field(
        default="runtime/business_exports",
        env="BUSINESS_EXPORT_STORAGE_DIR",
    )
    # Optional planner for business Agent capabilities. When the key is absent
    # or the planner call fails, the lightweight rule planner keeps test flows usable.
    business_agent_planner_enabled: bool = Field(default=True, env="BUSINESS_AGENT_PLANNER_ENABLED")
    business_agent_planner_model: str = Field(default="gpt-5.5", env="BUSINESS_AGENT_PLANNER_MODEL")
    business_agent_openai_api_key: str | None = Field(
        default=None,
        env=["BUSINESS_AGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
    )
    business_agent_openai_base_url: str = Field(
        default="https://api.openai.com",
        env=["BUSINESS_AGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"],
    )
    business_agent_planner_timeout_seconds: int = Field(default=30, env="BUSINESS_AGENT_PLANNER_TIMEOUT_SECONDS")
    executor_config_path: str = Field(default="config/executors.yaml", env="EXECUTOR_CONFIG_PATH")
    # Controls in-process background consumers/finalizers.
    # "auto" keeps production/Linux hosts enabled, but prevents local macOS
    # dev backends from consuming remote/production queues by accident.
    background_workers_enabled: str = Field(default="auto", env="BACKGROUND_WORKERS_ENABLED")
    ability_task_max_workers: int = Field(default=24, env="ABILITY_TASK_MAX_WORKERS")
    # Legacy total worker cap for eval runs (kept for backward compatibility).
    # Keep this higher than the largest provider lane so eval can feed downstream
    # queues instead of becoming the hidden bottleneck.
    eval_run_max_workers: int = Field(default=12, env="EVAL_RUN_MAX_WORKERS")
    # Eval run worker caps by provider lane. ComfyUI now has two standardized
    # nodes with queue-aware routing; executor.max_concurrency remains the final
    # per-node safety gate.
    eval_comfyui_run_max_workers: int = Field(default=10, env="EVAL_COMFYUI_RUN_MAX_WORKERS")
    eval_commercial_run_max_workers: int = Field(default=4, env="EVAL_COMMERCIAL_RUN_MAX_WORKERS")
    eval_default_run_max_workers: int = Field(default=2, env="EVAL_DEFAULT_RUN_MAX_WORKERS")
    # Fan-out concurrency for "裂变数量" runs (Coze async submit + polling).
    # Default to 1 (sequential) for stability; increase when infra is ready.
    eval_fanout_max_workers: int = Field(default=1, env="EVAL_FANOUT_MAX_WORKERS")
    eval_public_enabled: bool = Field(default=False, env="EVAL_PUBLIC_ENABLED")
    # Optional shared secret for public evaluation APIs. If unset and
    # eval_public_enabled=true, the endpoints are open (intended for internal LAN).
    eval_public_token: str | None = Field(default=None, env="EVAL_PUBLIC_TOKEN")
    # Admin token for maintaining eval workflow display name/notes/categories without login.
    # Must be supplied by the target environment; no real token should live in code.
    eval_admin_token: str | None = Field(default=None, env="EVAL_ADMIN_TOKEN")
    # If a Coze workflow returns a raw ComfyUI task id (not a PODI ability_task id),
    # we can fall back to another workflow to resolve images.
    coze_comfyui_callback_workflow_id: str | None = Field(default=None, env="COZE_COMFYUI_CALLBACK_WORKFLOW_ID")
    # When set, force all ComfyUI abilities to route to a single executor id.
    # Useful for testing (single ComfyUI server) to avoid node/plugin mismatch.
    comfyui_default_executor_id: str | None = Field(default=None, env="COMFYUI_DEFAULT_EXECUTOR_ID")
    # Enable queue-aware routing across multiple ComfyUI executors.
    # Keep False until all ComfyUI servers are standardized.
    comfyui_route_by_queue: bool = Field(default=True, env="COMFYUI_ROUTE_BY_QUEUE")
    # Soft target for ComfyUI queue depth per executor. Router will prefer nodes under this value.
    # Business-side schedulers can use this as a batch size hint.
    comfyui_queue_batch_size: int = Field(default=10, env="COMFYUI_QUEUE_BATCH_SIZE")
    comfyui_backend_running_grace_seconds: int = Field(default=300, env="COMFYUI_BACKEND_RUNNING_GRACE_SECONDS")
    # Optional external image-ops service for self-built atomic image tools such as
    # upscale / dpi / expand-mask. When unset, backend keeps using local implementations.
    image_ops_base_url: str | None = Field(default=None, env="IMAGE_OPS_BASE_URL")
    image_ops_service_token: str | None = Field(default=None, env="IMAGE_OPS_SERVICE_TOKEN")
    image_ops_timeout_seconds: int = Field(default=120, env="IMAGE_OPS_TIMEOUT_SECONDS")
    image_ops_local_fallback_enabled: bool = Field(default=True, env="IMAGE_OPS_LOCAL_FALLBACK_ENABLED")
    # Fengniao / Humcustom fulfillment credentials. These remain environment-only.
    humcustom_api_base_url: str = Field(default="https://openapi.humcustom.com", env="HUMCUSTOM_API_BASE_URL")
    humcustom_app_key: str | None = Field(default=None, env="HUMCUSTOM_APP_KEY")
    humcustom_app_secret: str | None = Field(default=None, env="HUMCUSTOM_APP_SECRET")
    humcustom_access_token: str | None = Field(default=None, env="HUMCUSTOM_ACCESS_TOKEN")
    humcustom_timeout_seconds: int = Field(default=20, env="HUMCUSTOM_TIMEOUT_SECONDS")
    # Control-plane hosts (for example the future Coze+backend shared host) should not
    # run memory-heavy local image utilities. When enabled, local upscale requests fail
    # fast and must be routed to dedicated executors instead of consuming host memory.
    disable_local_heavy_image_tasks: bool = Field(default=False, env="DISABLE_LOCAL_HEAVY_IMAGE_TASKS")
    # ComfyUI repo info for version catalog sync.
    comfyui_repo_url: str = Field(default="https://github.com/comfyanonymous/ComfyUI", env="COMFYUI_REPO_URL")
    comfyui_repo_api_base: str = Field(default="https://api.github.com", env="COMFYUI_REPO_API_BASE")
    comfyui_repo_api_token: str | None = Field(default=None, env="COMFYUI_REPO_API_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()
