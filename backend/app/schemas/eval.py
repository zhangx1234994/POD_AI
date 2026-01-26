"""Pydantic schemas for AI ability evaluation."""

from typing import Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EvalWorkflowVersionBase(BaseModel):
    """Base schema for evaluation workflow version."""
    category: str = Field(..., description="能力分类")
    name: str = Field(..., description="展示名称")
    version: str = Field(default="v1", description="版本号")
    coze_base_url: Optional[str] = Field(None, description="Coze基础URL")
    workflow_id: str = Field(..., description="Coze工作流ID")
    parameters_schema: Optional[dict[str, Any]] = Field(None, description="参数schema")
    output_schema: Optional[dict[str, Any]] = Field(None, description="输出schema")
    notes: Optional[str] = Field(None, description="备注")
    status: str = Field(default="active", description="状态")


class EvalWorkflowVersionCreate(EvalWorkflowVersionBase):
    """Schema for creating evaluation workflow version."""
    pass


class EvalWorkflowVersionUpdate(BaseModel):
    """Schema for updating evaluation workflow version."""
    category: Optional[str] = Field(None, description="能力分类")
    name: Optional[str] = Field(None, description="展示名称")
    version: Optional[str] = Field(None, description="版本号")
    coze_base_url: Optional[str] = Field(None, description="Coze基础URL")
    workflow_id: Optional[str] = Field(None, description="Coze工作流ID")
    parameters_schema: Optional[dict[str, Any]] = Field(None, description="参数schema")
    output_schema: Optional[dict[str, Any]] = Field(None, description="输出schema")
    notes: Optional[str] = Field(None, description="备注")
    status: Optional[str] = Field(None, description="状态")


class EvalWorkflowVersionResponse(EvalWorkflowVersionBase):
    """Schema for evaluation workflow version response."""
    id: str = Field(..., description="ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class EvalDatasetItemBase(BaseModel):
    """Base schema for evaluation dataset item."""
    category: str = Field(..., description="分类")
    name: str = Field(..., description="名称")
    oss_url: str = Field(..., description="OSS地址")
    meta_json: Optional[dict[str, Any]] = Field(None, description="元数据")


class EvalDatasetItemCreate(EvalDatasetItemBase):
    """Schema for creating evaluation dataset item."""
    pass


class EvalDatasetItemResponse(EvalDatasetItemBase):
    """Schema for evaluation dataset item response."""
    id: str = Field(..., description="ID")
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class EvalRunBase(BaseModel):
    """Base schema for evaluation run."""
    workflow_version_id: str = Field(..., description="工作流版本ID")
    dataset_item_id: Optional[str] = Field(None, description="样例图ID")
    input_oss_urls_json: Optional[List[str]] = Field(None, description="输入图URL")
    parameters_json: Optional[dict[str, Any]] = Field(None, description="参数")
    status: str = Field(default="queued", description="状态")
    coze_execute_id: Optional[str] = Field(None, description="Coze执行ID")
    coze_debug_url: Optional[str] = Field(None, description="Coze调试URL")
    podi_task_id: Optional[str] = Field(None, description="PODI任务ID")
    result_image_urls_json: Optional[List[str]] = Field(None, description="结果图URL")
    result_output_json: Optional[Any] = Field(None, description="非图片结果（如打标签 JSON）")
    error_message: Optional[str] = Field(None, description="错误信息")
    duration_ms: Optional[int] = Field(None, description="执行时长（毫秒）")


class EvalRunCreate(BaseModel):
    """Schema for creating evaluation run."""
    workflow_version_id: str = Field(..., description="工作流版本ID")
    dataset_item_id: Optional[str] = Field(None, description="样例图ID")
    input_oss_urls_json: Optional[List[str]] = Field(None, description="输入图URL")
    parameters_json: Optional[dict[str, Any]] = Field(None, description="参数")


class EvalRunResponse(EvalRunBase):
    """Schema for evaluation run response."""
    id: str = Field(..., description="ID")
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class EvalRunListResponse(BaseModel):
    """Schema for evaluation run list response."""
    total: int = Field(..., description="总条数")
    items: List[EvalRunResponse] = Field(..., description="列表项")

class EvalRunWithLatestAnnotationResponse(EvalRunResponse):
    """Eval run plus latest annotation (if any), used by the public eval console."""

    latest_annotation: Optional["EvalAnnotationResponse"] = Field(default=None, description="最新标注")


class EvalRunWithLatestAnnotationListResponse(BaseModel):
    total: int = Field(..., description="总条数")
    items: List[EvalRunWithLatestAnnotationResponse] = Field(..., description="列表项")


class EvalAnnotationBase(BaseModel):
    """Base schema for evaluation annotation."""
    rating: int = Field(..., ge=1, le=5, description="评分（1-5）")
    tags_json: Optional[List[str]] = Field(None, description="问题标签")
    comment: Optional[str] = Field(None, description="备注")


class EvalAnnotationCreate(EvalAnnotationBase):
    """Schema for creating evaluation annotation."""
    pass


class EvalAnnotationResponse(EvalAnnotationBase):
    """Schema for evaluation annotation response."""
    id: str = Field(..., description="ID")
    run_id: str = Field(..., description="运行ID")
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


EvalRunWithLatestAnnotationResponse.model_rebuild()
