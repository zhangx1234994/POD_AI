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
    metadata: Optional[dict[str, Any]] = Field(None, description="内部元数据")
    presentation: Optional[dict[str, Any]] = Field(None, description="业务展示层覆盖")
    usage: Optional[dict[str, Any]] = Field(None, description="业务使用方式覆盖")
    deprecation: Optional[dict[str, Any]] = Field(None, description="下线/替代信息覆盖")
    governance: Optional[dict[str, Any]] = Field(None, description="目录治理信息覆盖")


class EvalWorkflowResourceBinding(BaseModel):
    field: str = Field(..., description="参数字段名")
    resource_type: str = Field(..., alias="resourceType", description="资源类型：lora/model/plugin")
    source: str = Field(..., description="数据来源")


class EvalWorkflowVersionResponse(EvalWorkflowVersionBase):
    """Schema for evaluation workflow version response."""
    id: str = Field(..., description="ID")
    metadata: Optional[dict[str, Any]] = Field(None, description="内部元数据")
    presentation: Optional[dict[str, Any]] = Field(None, description="业务展示层")
    usage: Optional[dict[str, Any]] = Field(None, description="业务使用方式")
    deprecation: Optional[dict[str, Any]] = Field(None, description="下线/替代信息")
    governance: Optional[dict[str, Any]] = Field(None, description="目录治理信息")
    resource_bindings: list[EvalWorkflowResourceBinding] = Field(
        default_factory=list,
        alias="resourceBindings",
        description="工作流参数与资源目录绑定",
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True
        populate_by_name = True


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
    submit_status: Optional[str] = Field(
        None, description="提交阶段状态：pending/submitting/submit_failed/submitted"
    )
    callback_status: Optional[str] = Field(
        None, description="回调阶段状态：waiting/running/success/failed/not_configured"
    )
    final_status: Optional[str] = Field(
        None, description="最终状态：pending/running/success/failed/canceled"
    )
    error_code: Optional[str] = Field(None, description="标准错误码（可为空）")
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


class EvalRunPurgeResponse(BaseModel):
    deleted_runs: int = Field(..., description="已删除的运行记录数")
    deleted_annotations: int = Field(..., description="已删除的标注记录数")


class EvalOperationsRunItem(BaseModel):
    runId: str
    workflowId: Optional[str] = None
    workflowName: Optional[str] = None
    category: Optional[str] = None
    status: str
    ageMinutes: int
    cozeExecuteId: Optional[str] = None
    podiTaskId: Optional[str] = None
    imageCount: int = 0
    hasOutput: bool = False
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


class EvalOperationsIssue(BaseModel):
    severity: str = Field(..., description="严重程度：healthy/warning/critical")
    code: str = Field(..., description="问题编码")
    title: str = Field(..., description="中文标题")
    message: str = Field(..., description="可读说明")
    count: int = Field(..., description="命中数量")


class EvalOperationsHealthResponse(BaseModel):
    generatedAt: datetime
    status: str = Field(..., description="整体状态：healthy/warning/critical")
    staleMinutes: int
    submitGraceMinutes: int
    recentHours: int
    recentRunTotal: int = Field(..., description="最近窗口内运行总数")
    recentSuccessCount: int = Field(..., description="最近窗口内成功数量")
    recentFailureCount: int = Field(..., description="最近窗口内有效失败数量")
    activeWorkflowCount: int
    totalWorkflowCount: int
    statusCounts: dict[str, int]
    recentStatusCounts: dict[str, int]
    staleRunning: List[EvalOperationsRunItem]
    submitStalled: List[EvalOperationsRunItem]
    succeededWithoutOutput: List[EvalOperationsRunItem]
    recentFailures: List[EvalOperationsRunItem]
    errorCounts: dict[str, int]
    issues: List[EvalOperationsIssue]


class EvalBatchCreate(BaseModel):
    """Create a LoRA batch session."""

    workflow_version_id: str = Field(..., description="工作流版本ID")
    repeat_count: int = Field(1, ge=1, le=20, description="每张图重复次数")
    parameters_json: Optional[dict[str, Any]] = Field(None, description="批次默认参数")
    metadata: Optional[dict[str, Any]] = Field(None, description="附加元数据")


class EvalBatchSubmitRequest(BaseModel):
    """Submit uploaded assets into runnable items."""

    parameters_json: Optional[dict[str, Any]] = Field(None, description="本次提交覆盖参数")
    only_pending: bool = Field(True, description="仅提交待处理项")


class EvalBatchSessionResponse(BaseModel):
    id: str
    workflow_version_id: Optional[str] = None
    created_by: str
    status: str
    planned_image_count: int
    repeat_count: int
    planned_run_count: int
    uploaded_count: int
    upload_failed_count: int
    submitted_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    canceled_count: int
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    extra_metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvalBatchSessionListResponse(BaseModel):
    total: int
    items: List[EvalBatchSessionResponse]


class EvalBatchAssetUpsertItem(BaseModel):
    source_key: str = Field(..., description="素材唯一标识")
    file_name: str = Field(..., description="文件名")
    oss_url: Optional[str] = Field(None, description="素材 OSS URL")
    object_key: Optional[str] = Field(None, description="OSS object key")
    size_bytes: Optional[int] = Field(None, ge=0, description="文件大小")
    width: Optional[int] = Field(None, ge=0, description="宽")
    height: Optional[int] = Field(None, ge=0, description="高")
    upload_status: str = Field("uploaded", description="上传状态")
    upload_error_code: Optional[str] = Field(None, description="上传错误码")
    upload_error_message: Optional[str] = Field(None, description="上传错误信息")


class EvalBatchAssetUpsertRequest(BaseModel):
    items: List[EvalBatchAssetUpsertItem]


class EvalBatchAssetResponse(BaseModel):
    id: str
    batch_session_id: str
    source_key: str
    file_name: str
    oss_url: Optional[str] = None
    object_key: Optional[str] = None
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    upload_status: str
    upload_error_code: Optional[str] = None
    upload_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvalBatchAssetListResponse(BaseModel):
    total: int
    items: List[EvalBatchAssetResponse]


class EvalBatchRunItemResponse(BaseModel):
    id: str
    batch_session_id: str
    asset_id: str
    asset_source_key: Optional[str] = None
    asset_file_name: Optional[str] = None
    asset_oss_url: Optional[str] = None
    repeat_index: int
    eval_run_id: Optional[str] = None
    status: str
    run_status: Optional[str] = None
    run_prompt: Optional[str] = None
    run_output_urls_json: Optional[List[str]] = None
    run_output_reviews_json: Optional[List["EvalBatchOutputReviewResponse"]] = None
    run_error_message: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvalBatchRunItemListResponse(BaseModel):
    total: int
    items: List[EvalBatchRunItemResponse]


class EvalBatchOutputReviewResponse(BaseModel):
    id: str
    batch_session_id: str
    run_item_id: str
    eval_run_id: Optional[str] = None
    output_index: int
    verdict: str
    reason: Optional[str] = None
    note: Optional[str] = None
    updated_by: str
    updated_at: datetime

    class Config:
        from_attributes = True


class EvalBatchOutputReviewUpsertItem(BaseModel):
    run_item_id: str = Field(..., description="批次执行条目ID")
    output_index: int = Field(..., ge=1, le=50, description="输出序号（从1开始）")
    verdict: str = Field("pending", description="pending/satisfied/unsatisfied")
    reason: Optional[str] = Field(None, description="不满意原因（可选）")
    note: Optional[str] = Field(None, description="备注（可选）")


class EvalBatchOutputReviewUpsertRequest(BaseModel):
    items: List[EvalBatchOutputReviewUpsertItem]


class EvalBatchOutputReviewListResponse(BaseModel):
    total: int
    items: List[EvalBatchOutputReviewResponse]


class EvalBatchReviewProgress(BaseModel):
    page_size: int = Field(20, description="分页大小（固定20）")
    current_page: int = Field(1, ge=1, description="当前页")
    completed_page: int = Field(0, ge=0, description="已完成页（默认满意）")
    updated_at: Optional[datetime] = Field(None, description="进度更新时间")


class EvalBatchReviewOutputItem(BaseModel):
    run_item_id: str
    run_id: Optional[str] = None
    output_index: int
    url: str
    run_status: Optional[str] = None
    review: Optional[EvalBatchOutputReviewResponse] = None


class EvalBatchReviewGroupItem(BaseModel):
    asset_id: str
    source_key: str
    file_name: str
    input_url: Optional[str] = None
    group_status: str = Field(..., description="has_output/no_output/failed")
    run_total: int
    completed: int
    failed: int
    waiting: int
    outputs: List[EvalBatchReviewOutputItem]
    last_error: Optional[str] = None


class EvalBatchReviewGroupListResponse(BaseModel):
    batch_id: str
    page: int
    page_size: int
    total_groups: int
    total_pages: int
    review_progress: EvalBatchReviewProgress
    items: List[EvalBatchReviewGroupItem]


class EvalBatchReviewProgressRequest(BaseModel):
    current_page: int = Field(..., ge=1, description="当前页")
    completed_page: int = Field(..., ge=0, description="已完成页")
    page_size: int = Field(20, ge=1, description="分页大小（固定20）")


class EvalBatchReviewProgressResponse(BaseModel):
    batch_id: str
    review_progress: EvalBatchReviewProgress


class EvalBatchStopResponse(BaseModel):
    batch_id: str
    stopped_run_items: int
    stopped_eval_runs: int
    stopped_ability_tasks: int


class EvalBatchSubmitResponse(BaseModel):
    batch_id: str
    created_items: int
    submitted_items: int
    failed_items: int


EvalRunWithLatestAnnotationResponse.model_rebuild()
EvalBatchRunItemResponse.model_rebuild()
