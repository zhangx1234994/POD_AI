"""应用配置。"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PODI Backend"
    oss_access_key: str | None = Field(default=None, env=["OSS_ACCESS_KEY", "OSS_AK"])
    oss_secret_key: str | None = Field(default=None, env=["OSS_SECRET_KEY", "OSS_SK"])
    database_url: str = Field(default="sqlite:///./app.db", env="DATABASE_URL")
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
    baidu_api_key: str | None = Field(default=None, env="BAIDU_API_KEY")
    baidu_secret_key: str | None = Field(default=None, env="BAIDU_SECRET_KEY")
    baidu_base_url: str = Field(default="https://aip.baidubce.com", env="BAIDU_BASE_URL")
    volcengine_api_key: str | None = Field(default=None, env="VOLCENGINE_API_KEY")
    volcengine_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com",
        env="VOLCENGINE_BASE_URL",
    )
    executor_config_path: str = Field(default="config/executors.yaml", env="EXECUTOR_CONFIG_PATH")
    ability_task_max_workers: int = Field(default=4, env="ABILITY_TASK_MAX_WORKERS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
