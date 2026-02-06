"""Pydantic schemas for admin integration endpoints."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class ExecutorBase(BaseModel):
    name: str
    type: str
    base_url: str | None = None
    status: str = "inactive"
    weight: int = 1
    max_concurrency: int = 1
    config: dict[str, Any] | None = None
    api_key_ids: list[str] = Field(default_factory=list)


class ExecutorCreate(ExecutorBase):
    id: str | None = None


class ExecutorUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    status: str | None = None
    weight: int | None = None
    max_concurrency: int | None = None
    config: dict[str, Any] | None = None
    api_key_ids: list[str] | None = None


class ExecutorRead(ExecutorBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    health_status: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowBase(BaseModel):
    action: str
    name: str
    version: str = "v1"
    type: str = "generic"
    status: str = "inactive"
    definition: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] | None = None


class WorkflowCreate(WorkflowBase):
    id: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    status: str | None = None
    type: str | None = None
    definition: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class WorkflowRead(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    created_at: datetime
    updated_at: datetime


class WorkflowBindingBase(BaseModel):
    action: str
    workflow_id: str
    executor_id: str
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, Any] | None = None


class WorkflowBindingCreate(WorkflowBindingBase):
    id: str | None = None


class WorkflowBindingUpdate(BaseModel):
    workflow_id: str | None = None
    executor_id: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class WorkflowBindingRead(WorkflowBindingBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    created_at: datetime
    updated_at: datetime


class ApiKeyBase(BaseModel):
    provider: str
    name: str
    key: str
    status: str = "active"
    daily_quota: int | None = None
    expire_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ApiKeyCreate(ApiKeyBase):
    id: str | None = None


class ApiKeyUpdate(BaseModel):
    provider: str | None = None
    name: str | None = None
    key: str | None = None
    status: str | None = None
    daily_quota: int | None = None
    expire_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ApiKeyRead(ApiKeyBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    usage_count: int
    created_at: datetime
    updated_at: datetime


class ComfyuiLoraBase(BaseModel):
    file_name: str = Field(..., description="LoRA 文件名（服务器侧）")
    display_name: str = Field(..., description="对外显示名称")
    description: str | None = Field(default=None, description="备注说明")
    base_model: str | None = Field(default=None, description="适用基座模型（UNET，单值兼容）")
    base_models: list[str] | None = Field(default=None, description="适用基座模型列表（UNET，多选）")
    tags: list[str] | None = Field(default=None, description="标签")
    trigger_words: list[str] | None = Field(default=None, description="触发词/关键词")
    status: str = Field(default="active", description="active/inactive")


class ComfyuiLoraCreate(ComfyuiLoraBase):
    id: int | None = None


class ComfyuiLoraUpdate(BaseModel):
    file_name: str | None = None
    display_name: str | None = None
    description: str | None = None
    base_model: str | None = None
    base_models: list[str] | None = None
    tags: list[str] | None = None
    trigger_words: list[str] | None = None
    status: str | None = None


class ComfyuiLoraRead(ComfyuiLoraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    installed: bool | None = None


class ComfyuiLoraCatalogResponse(BaseModel):
    executorId: str | None = None
    baseUrl: str | None = None
    installedFiles: list[str] | None = None
    untrackedFiles: list[str] | None = None
    items: list[ComfyuiLoraRead]


class ComfyuiModelCatalogBase(BaseModel):
    file_name: str = Field(..., description="模型文件名（与 ComfyUI 内一致）")
    display_name: str = Field(..., description="对外显示名称")
    model_type: str = Field(..., description="模型类型，例如 unet/clip/vae")
    description: str | None = Field(default=None, description="备注说明")
    source_url: str | None = Field(default=None, description="来源地址/文档")
    download_url: str | None = Field(default=None, description="下载地址")
    tags: list[str] | None = Field(default=None, description="标签")
    status: str = Field(default="active", description="active/inactive")


class ComfyuiModelCatalogCreate(ComfyuiModelCatalogBase):
    id: int | None = None


class ComfyuiModelCatalogUpdate(BaseModel):
    file_name: str | None = None
    display_name: str | None = None
    model_type: str | None = None
    description: str | None = None
    source_url: str | None = None
    download_url: str | None = None
    tags: list[str] | None = None
    status: str | None = None


class ComfyuiModelCatalogRead(ComfyuiModelCatalogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ComfyuiModelCatalogResponse(BaseModel):
    items: list[ComfyuiModelCatalogRead]


class ComfyuiPluginCatalogBase(BaseModel):
    node_key: str = Field(..., description="插件节点 key（来自 /object_info）")
    display_name: str = Field(..., description="对外显示名称")
    package_name: str | None = Field(default=None, description="插件包/仓库名称")
    version: str | None = Field(default=None, description="插件版本/commit")
    description: str | None = Field(default=None, description="备注说明")
    source_url: str | None = Field(default=None, description="来源地址/文档")
    download_url: str | None = Field(default=None, description="下载地址")
    tags: list[str] | None = Field(default=None, description="标签")
    status: str = Field(default="active", description="active/inactive")


class ComfyuiPluginCatalogCreate(ComfyuiPluginCatalogBase):
    id: int | None = None


class ComfyuiPluginCatalogUpdate(BaseModel):
    node_key: str | None = None
    display_name: str | None = None
    package_name: str | None = None
    version: str | None = None
    description: str | None = None
    source_url: str | None = None
    download_url: str | None = None
    tags: list[str] | None = None
    status: str | None = None


class ComfyuiPluginCatalogRead(ComfyuiPluginCatalogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ComfyuiPluginCatalogResponse(BaseModel):
    items: list[ComfyuiPluginCatalogRead]


class ComfyuiVersionCatalogBase(BaseModel):
    version: str = Field(..., description="ComfyUI 版本号（tag/commit）")
    commit_sha: str | None = Field(default=None, description="Git commit sha")
    repo_url: str | None = Field(default=None, description="仓库地址")
    source_url: str | None = Field(default=None, description="来源地址/文档")
    download_url: str | None = Field(default=None, description="下载地址（zip/git）")
    released_at: datetime | None = Field(default=None, description="发布时间")
    notes: str | None = Field(default=None, description="备注说明")
    status: str = Field(default="active", description="active/inactive")


class ComfyuiVersionCatalogCreate(ComfyuiVersionCatalogBase):
    id: int | None = None


class ComfyuiVersionCatalogUpdate(BaseModel):
    version: str | None = None
    commit_sha: str | None = None
    repo_url: str | None = None
    source_url: str | None = None
    download_url: str | None = None
    released_at: datetime | None = None
    notes: str | None = None
    status: str | None = None


class ComfyuiVersionCatalogRead(ComfyuiVersionCatalogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ComfyuiVersionCatalogResponse(BaseModel):
    items: list[ComfyuiVersionCatalogRead]


class ComfyuiVersionCatalogSyncResponse(BaseModel):
    repo_url: str = Field(..., description="同步来源仓库")
    fetched_at: datetime = Field(..., description="同步时间")
    total: int = Field(..., description="获取到的版本数量")
    created: int = Field(..., description="新增数量")
    updated: int = Field(..., description="更新数量")


class ComfyuiServerDiffCreate(BaseModel):
    baseline_executor_id: str = Field(..., description="主服务器 executor_id")
    payload: dict[str, Any] = Field(default_factory=dict, description="差异快照 JSON")


class ComfyuiServerDiffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baseline_executor_id: str
    payload: dict[str, Any] | None = None
    created_at: datetime
