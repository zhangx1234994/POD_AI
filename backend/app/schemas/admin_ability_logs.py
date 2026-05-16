"""Schemas for ability invocation logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AbilityInvocationOutputSummary(BaseModel):
    """Human-facing output summary for mixed image/video/text abilities."""

    image_count: int = 0
    video_count: int = 0
    text_count: int = 0
    structured_count: int = 0
    asset_count: int = 0
    primary_kind: str | None = Field(default=None, description="image/video/text/asset")
    primary_url: str | None = None
    text_preview: str | None = None
    has_output: bool = False


def _get_json_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _candidate_url(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("ossUrl", "url", "sourceUrl", "storedUrl"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _classify_asset(value: Any, *, default_kind: str = "asset") -> str:
    record = value if isinstance(value, dict) else {}
    explicit = str(
        record.get("type")
        or record.get("kind")
        or record.get("outputType")
        or record.get("role")
        or ""
    ).lower()
    content_type = str(record.get("contentType") or record.get("mimeType") or "").lower()
    if "image" in explicit or content_type.startswith("image/"):
        return "image"
    if "video" in explicit or content_type.startswith("video/"):
        return "video"
    url = (_candidate_url(value) or "").lower()
    if url.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")) or any(
        marker in url for marker in (".png?", ".jpg?", ".jpeg?", ".webp?", ".gif?", ".bmp?", ".svg?")
    ):
        return "image"
    if url.endswith((".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv")) or any(
        marker in url for marker in (".mp4?", ".mov?", ".webm?", ".m4v?", ".avi?", ".mkv?")
    ):
        return "video"
    return default_kind


def _collect_urls(value: Any, *, default_kind: str) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[tuple[str, str]] = []
    for item in value:
        url = _candidate_url(item)
        if not url:
            continue
        rows.append((url, _classify_asset(item, default_kind=default_kind)))
    return rows


def _collect_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for item in value:
        if isinstance(item, (str, int, float)) and str(item).strip():
            texts.append(str(item).strip())
            continue
        if isinstance(item, dict):
            for key in ("text", "content", "value", "output", "message"):
                candidate = item.get(key)
                if isinstance(candidate, (str, int, float)) and str(candidate).strip():
                    texts.append(str(candidate).strip())
                    break
    return texts


def _dedup_pairs(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for url, kind in rows:
        if not url or url in seen:
            continue
        seen.add(url)
        result.append((url, kind))
    return result


def _has_structured_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(item is not None and (not isinstance(item, str) or item.strip()) for item in value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _build_output_summary(
    *,
    stored_url: str | None,
    response_payload: dict[str, Any] | None,
    result_assets: list[dict[str, Any]] | None,
) -> AbilityInvocationOutputSummary:
    payload = _get_json_record(response_payload)
    url_rows: list[tuple[str, str]] = []
    if stored_url:
        url_rows.append((stored_url, _classify_asset({"url": stored_url}, default_kind="asset")))
    url_rows.extend(_collect_urls(result_assets, default_kind="asset"))
    url_rows.extend(_collect_urls(payload.get("assets"), default_kind="asset"))
    url_rows.extend(_collect_urls(payload.get("storedAssets"), default_kind="asset"))
    url_rows.extend(_collect_urls(payload.get("images"), default_kind="image"))
    url_rows.extend(_collect_urls(payload.get("videos"), default_kind="video"))
    url_rows.extend((url, "image") for url, _ in _collect_urls(payload.get("imageUrls"), default_kind="image"))
    url_rows.extend((url, "video") for url, _ in _collect_urls(payload.get("videoUrls"), default_kind="video"))
    url_rows.extend(_collect_urls(payload.get("resultUrls"), default_kind="asset"))
    for key, default_kind in (("imageUrl", "image"), ("videoUrl", "video"), ("url", "asset")):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            url_rows.append((value.strip(), default_kind))

    url_rows = _dedup_pairs(url_rows)
    texts = []
    if isinstance(payload.get("text"), (str, int, float)) and str(payload.get("text")).strip():
        texts.append(str(payload.get("text")).strip())
    texts.extend(_collect_texts(payload.get("texts")))
    structured_count = 0
    for key in (
        "json",
        "jsonOutput",
        "json_output",
        "outputJson",
        "result",
        "resultPayload",
        "result_payload",
        "resultOutputJson",
        "result_output_json",
        "structuredOutput",
        "structured_output",
    ):
        if key in payload and _has_structured_value(payload.get(key)):
            structured_count = 1
            break

    image_count = sum(1 for _, kind in url_rows if kind == "image")
    video_count = sum(1 for _, kind in url_rows if kind == "video")
    asset_count = sum(1 for _, kind in url_rows if kind not in {"image", "video"})
    primary_url = url_rows[0][0] if url_rows else None
    primary_kind = url_rows[0][1] if url_rows else ("text" if texts else ("structured" if structured_count else None))
    text_preview = texts[0][:117] + "..." if texts and len(texts[0]) > 120 else (texts[0] if texts else None)
    return AbilityInvocationOutputSummary(
        image_count=image_count,
        video_count=video_count,
        text_count=len(texts),
        structured_count=structured_count,
        asset_count=asset_count,
        primary_kind=primary_kind,
        primary_url=primary_url,
        text_preview=text_preview,
        has_output=bool(url_rows or texts or structured_count),
    )


class AbilityInvocationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ability_id: str | None = None
    ability_provider: str
    capability_key: str
    ability_name: str | None = None
    ability_current_template_id: str | None = Field(default=None, description="能力当前模板版本ID")
    ability_template_history_count: int = Field(default=0, description="能力模板历史快照数量")
    ability_template_published: bool = Field(default=False, description="能力是否已发布模板")
    executor_id: str | None = None
    executor_name: str | None = None
    executor_type: str | None = None
    source: str
    task_id: str | None = None
    callback_id: str | None = None
    trace_id: str | None = None
    workflow_run_id: str | None = None
    status: str = Field(description="日志状态：pending/success/failed（日志维度）")
    submit_status: str | None = Field(
        default=None,
        description="提交阶段状态：pending/submitting/submit_failed/submitted",
    )
    final_status: str | None = Field(
        default=None,
        description="最终状态：pending/running/success/failed/canceled",
    )
    error_code: str | None = Field(default=None, description="标准错误码（可为空）")
    duration_ms: int | None = None
    stored_url: str | None = None
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    result_assets: list[dict[str, Any]] | None = None
    output_summary: AbilityInvocationOutputSummary = Field(default_factory=AbilityInvocationOutputSummary)
    error_message: str | None = Field(default=None, description="失败错误码或可读信息")
    callback_status: str | None = Field(
        default=None,
        description="回调状态：success/failed（可为空，表示未配置或未触发）",
    )
    callback_http_status: int | None = None
    callback_payload: dict[str, Any] | None = None
    callback_response: dict[str, Any] | None = None
    callback_error: str | None = None
    callback_started_at: datetime | None = None
    callback_finished_at: datetime | None = None
    billing_unit: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    cost_amount: float | None = None
    created_at: datetime

    @model_validator(mode="after")
    def populate_output_summary(self) -> "AbilityInvocationLogRead":
        self.output_summary = _build_output_summary(
            stored_url=self.stored_url,
            response_payload=self.response_payload,
            result_assets=self.result_assets,
        )
        return self


class AbilityInvocationLogListResponse(BaseModel):
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    items: list[AbilityInvocationLogRead]


class AbilityInvocationLogMetricBucket(BaseModel):
    """Aggregated metrics for ability invocations (best-effort)."""

    ability_provider: str
    capability_key: str
    executor_id: str | None = None

    count: int
    success_count: int
    failed_count: int
    success_rate: float | None = None

    avg_duration_ms: float | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    total_cost: float | None = None
    avg_cost: float | None = None

    last_success_at: datetime | None = None
    last_failed_at: datetime | None = None


class AbilityLogCostSummary(BaseModel):
    key: str
    count: int
    total_cost: float | None = None
    avg_cost: float | None = None


class AbilityInvocationLogMetricsResponse(BaseModel):
    window_hours: int
    total_count: int | None = None
    total_success_count: int | None = None
    total_failed_count: int | None = None
    uncosted_count: int | None = None
    total_cost: float | None = None
    avg_cost_per_call: float | None = None
    provider_totals: list[AbilityLogCostSummary] = Field(default_factory=list)
    currency_totals: list[AbilityLogCostSummary] = Field(default_factory=list)
    buckets: list[AbilityInvocationLogMetricBucket]
