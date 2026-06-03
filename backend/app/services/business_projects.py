"""Project context service for business-facing workflows."""

from __future__ import annotations

from datetime import date, datetime
import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4
import zipfile

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import (
    BusinessExportPackage,
    BusinessProject,
    BusinessProjectAsset,
    BusinessProjectRunLink,
    BusinessProjectSelection,
    BusinessRun,
)
from app.models.user import User
from app.schemas.business import (
    BusinessExportPackageCreateRequest,
    BusinessProjectAssetCreateRequest,
    BusinessProjectCreateRequest,
    BusinessProjectSelectionCreateRequest,
    BusinessProjectUpdateRequest,
    BusinessRunCreateRequest,
)


logger = logging.getLogger(__name__)

PROJECT_STATUSES = {"draft", "active", "paused", "ready_to_export", "exported", "archived"}
PROJECT_ASSET_TYPES = {
    "input_image",
    "pattern",
    "variant",
    "product_image",
    "angle_image",
    "model_image",
    "video",
    "text",
    "other",
}
PROJECT_EXPORT_STATUSES = {"pending", "building", "ready", "failed"}
PROJECT_SCENARIO_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class BusinessProjectService:
    def create_project(self, payload: BusinessProjectCreateRequest, *, user: User | None = None) -> dict[str, Any]:
        name = self._required_text(payload.name, "PROJECT_NAME_REQUIRED", max_length=128)
        scenario = self._normalize_scenario(payload.scenario)
        tenant_id, client_id = self._resolve_scope(
            user=user,
            tenant_id=payload.tenantId,
            client_id=payload.clientId,
        )
        now = datetime.utcnow()
        with get_session() as session:
            row = BusinessProject(
                id=f"proj_{uuid4().hex[:16]}",
                name=name,
                scenario=scenario,
                status="draft",
                tenant_id=tenant_id,
                client_id=client_id,
                owner_user_id=self._safe_user_id(user),
                owner_user_name=self._actor_username(user),
                current_flow_step_key=self._short_text(payload.currentFlowStepKey, 64),
                flow_template_id=self._short_text(payload.flowTemplateId, 64),
                extra_metadata=self._clean_metadata(payload.metadata),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._project_to_dict(row, session=session)

    def list_projects(
        self,
        *,
        user: User | None = None,
        scenario: str | None = None,
        status: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        with get_session() as session:
            stmt = select(BusinessProject)
            stmt = self._apply_access_filters(stmt, user=user)
            if scenario:
                stmt = stmt.where(BusinessProject.scenario == self._normalize_scenario(scenario))
            if status:
                stmt = stmt.where(BusinessProject.status == self._normalize_project_status(status))
            if tenant_id and self._is_privileged_business_user(user):
                stmt = stmt.where(BusinessProject.tenant_id == self._short_text(tenant_id, 64))
            if client_id and self._is_privileged_business_user(user):
                stmt = stmt.where(BusinessProject.client_id == self._short_text(client_id, 64))
            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
            rows = (
                session.execute(
                    stmt.order_by(BusinessProject.updated_at.desc(), BusinessProject.created_at.desc())
                    .offset(max(0, int(offset)))
                    .limit(max(1, min(int(limit), 100)))
                )
                .scalars()
                .all()
            )
            return int(total), [self._project_to_dict(row, session=session) for row in rows]

    def get_project_detail(self, project_id: str, *, user: User | None = None) -> dict[str, Any]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            assets = (
                session.execute(
                    select(BusinessProjectAsset)
                    .where(BusinessProjectAsset.project_id == project.id)
                    .order_by(BusinessProjectAsset.created_at.desc())
                    .limit(200)
                )
                .scalars()
                .all()
            )
            links = (
                session.execute(
                    select(BusinessProjectRunLink)
                    .where(BusinessProjectRunLink.project_id == project.id)
                    .order_by(BusinessProjectRunLink.created_at.desc())
                    .limit(200)
                )
                .scalars()
                .all()
            )
            selections = (
                session.execute(
                    select(BusinessProjectSelection)
                    .where(BusinessProjectSelection.project_id == project.id)
                    .order_by(BusinessProjectSelection.created_at.desc())
                    .limit(100)
                )
                .scalars()
                .all()
            )
            packages = (
                session.execute(
                    select(BusinessExportPackage)
                    .where(BusinessExportPackage.project_id == project.id)
                    .order_by(BusinessExportPackage.created_at.desc())
                    .limit(50)
                )
                .scalars()
                .all()
            )
            return {
                "project": self._project_to_dict(project, session=session),
                "assets": [self._asset_to_dict(row) for row in assets],
                "runs": [self._run_link_to_dict(row, session=session) for row in links],
                "selections": [self._selection_to_dict(row) for row in selections],
                "export_packages": [self._export_package_to_dict(row) for row in packages],
            }

    def update_project(
        self,
        project_id: str,
        payload: BusinessProjectUpdateRequest,
        *,
        user: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            if payload.name is not None:
                project.name = self._required_text(payload.name, "PROJECT_NAME_REQUIRED", max_length=128)
            if payload.scenario is not None:
                project.scenario = self._normalize_scenario(payload.scenario)
            if payload.status is not None:
                project.status = self._normalize_project_status(payload.status)
            if "flowTemplateId" in payload.model_fields_set or "flow_template_id" in payload.model_fields_set:
                project.flow_template_id = self._short_text(payload.flowTemplateId, 64)
            if "currentFlowStepKey" in payload.model_fields_set or "current_flow_step_key" in payload.model_fields_set:
                project.current_flow_step_key = self._short_text(payload.currentFlowStepKey, 64)
            if "metadata" in payload.model_fields_set or "extra_metadata" in payload.model_fields_set:
                project.extra_metadata = self._clean_metadata(payload.metadata)
            session.add(project)
            session.commit()
            session.refresh(project)
            return self._project_to_dict(project, session=session)

    def create_asset(
        self,
        project_id: str,
        payload: BusinessProjectAssetCreateRequest,
        *,
        user: User | None = None,
    ) -> dict[str, Any]:
        asset_type = self._normalize_asset_type(payload.assetType)
        url = self._validate_asset_url(payload.url)
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            row = BusinessProjectAsset(
                id=f"asset_{uuid4().hex[:16]}",
                project_id=project.id,
                asset_type=asset_type,
                url=url,
                content_type=self._short_text(payload.contentType, 64),
                file_name=self._short_text(payload.fileName, 255),
                source_flow_step_key=self._short_text(payload.flowStepKey, 64),
                input_tags=self._normalize_text_list(payload.inputTags),
                issue_tags=self._normalize_text_list(payload.issueTags),
                selected=False,
                extra_metadata=self._clean_metadata(payload.metadata),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._asset_to_dict(row)

    def list_assets(
        self,
        project_id: str,
        *,
        user: User | None = None,
        asset_type: str | None = None,
        selected: bool | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            stmt = select(BusinessProjectAsset).where(BusinessProjectAsset.project_id == project.id)
            if asset_type:
                stmt = stmt.where(BusinessProjectAsset.asset_type == self._normalize_asset_type(asset_type))
            if selected is not None:
                stmt = stmt.where(BusinessProjectAsset.selected.is_(bool(selected)))
            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
            rows = (
                session.execute(stmt.order_by(BusinessProjectAsset.created_at.desc()).limit(200))
                .scalars()
                .all()
            )
            return int(total), [self._asset_to_dict(row) for row in rows]

    def list_project_runs(self, project_id: str, *, user: User | None = None) -> tuple[int, list[dict[str, Any]]]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            stmt = select(BusinessProjectRunLink).where(BusinessProjectRunLink.project_id == project.id)
            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
            rows = (
                session.execute(stmt.order_by(BusinessProjectRunLink.created_at.desc()).limit(200))
                .scalars()
                .all()
            )
            return int(total), [self._run_link_to_dict(row, session=session) for row in rows]

    def create_selection(
        self,
        project_id: str,
        payload: BusinessProjectSelectionCreateRequest,
        *,
        user: User | None = None,
    ) -> list[dict[str, Any]]:
        asset_ids = self._normalize_id_list([payload.assetId, *payload.assetIds])
        if not asset_ids:
            raise HTTPException(status_code=400, detail="PROJECT_SELECTION_ASSET_REQUIRED")
        target_flow_step_key = self._short_text(payload.targetFlowStepKey, 64)
        if not target_flow_step_key:
            raise HTTPException(status_code=400, detail="PROJECT_SELECTION_TARGET_REQUIRED")
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            rows: list[BusinessProjectSelection] = []
            for asset_id in asset_ids:
                asset = session.get(BusinessProjectAsset, asset_id)
                if not asset or asset.project_id != project.id:
                    raise HTTPException(status_code=400, detail="PROJECT_SELECTION_ASSET_INVALID")
                asset.selected = True
                asset.updated_at = datetime.utcnow()
                row = BusinessProjectSelection(
                    id=f"selection_{uuid4().hex[:16]}",
                    project_id=project.id,
                    asset_id=asset.id,
                    source_run_id=asset.source_run_id,
                    source_flow_step_key=self._short_text(payload.sourceFlowStepKey, 64) or asset.source_flow_step_key,
                    target_flow_step_key=target_flow_step_key,
                    selected_by_user_id=self._safe_user_id(user),
                    selected_by_user_name=self._actor_username(user),
                    note=self._short_text(payload.note, 2000),
                    extra_metadata=self._clean_metadata(payload.metadata),
                    created_at=datetime.utcnow(),
                )
                session.add(asset)
                session.add(row)
                rows.append(row)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [self._selection_to_dict(row) for row in rows]

    def create_export_package(
        self,
        project_id: str,
        payload: BusinessExportPackageCreateRequest,
        *,
        user: User | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        asset_ids = self._normalize_id_list(payload.assetIds)
        if not asset_ids:
            raise HTTPException(status_code=400, detail="PROJECT_EXPORT_ASSETS_EMPTY")
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            assets: list[BusinessProjectAsset] = []
            for asset_id in asset_ids:
                asset = session.get(BusinessProjectAsset, asset_id)
                if not asset or asset.project_id != project.id:
                    raise HTTPException(status_code=400, detail="PROJECT_EXPORT_ASSET_INVALID")
                assets.append(asset)
            run_ids = self._normalize_id_list([asset.source_run_id for asset in assets]) if payload.includeRunEvidence else []
            manifest = self._json_safe(
                {
                "projectId": project.id,
                "projectName": project.name,
                "scenario": project.scenario,
                "generatedAt": datetime.utcnow().isoformat(),
                "assets": [self._asset_to_dict(asset) for asset in assets],
                "runIds": run_ids,
                "metadata": self._clean_metadata(payload.metadata),
                }
            )
            summary = {
                "assetCount": len(assets),
                "runCount": len(run_ids),
                "qualityByGrade": self._quality_summary(assets) if payload.includeQualitySummary else {},
            }
            package_id = f"pkg_{uuid4().hex[:16]}"
            download_url = self._export_package_download_url(
                project_id=project.id,
                package_id=package_id,
                base_url=base_url,
            )
            try:
                self._write_export_package_archive(
                    project=project,
                    package_id=package_id,
                    manifest=manifest,
                    summary=summary,
                    assets=assets,
                    run_ids=run_ids,
                )
            except Exception as exc:  # pragma: no cover - defensive path covered by caller-level error code.
                logger.exception("failed to build business export package: project_id=%s", project.id)
                raise HTTPException(status_code=500, detail="PROJECT_EXPORT_BUILD_FAILED") from exc
            row = BusinessExportPackage(
                id=package_id,
                project_id=project.id,
                status="ready",
                asset_ids=asset_ids,
                run_ids=run_ids,
                download_url=download_url,
                manifest=manifest,
                summary=summary,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._export_package_to_dict(row)

    def get_export_package(
        self,
        project_id: str,
        package_id: str,
        *,
        user: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            row = session.get(BusinessExportPackage, package_id)
            if not row or row.project_id != project.id:
                raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
            return self._export_package_to_dict(row)

    def get_export_package_file(
        self,
        project_id: str,
        package_id: str,
        *,
        user: User | None = None,
    ) -> tuple[Path, str]:
        with get_session() as session:
            project = self._load_project_for_user(session, project_id=project_id, user=user)
            row = session.get(BusinessExportPackage, package_id)
            if not row or row.project_id != project.id:
                raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
            file_path = self._export_package_file_path(project_id=project.id, package_id=row.id)
            if not file_path.exists() or not file_path.is_file():
                raise HTTPException(status_code=404, detail="PROJECT_EXPORT_FILE_NOT_FOUND")
            return file_path, f"{self._safe_filename(project.name, fallback='podi-project')}-{row.id}.zip"

    def link_run_to_project(
        self,
        *,
        session,
        run: BusinessRun,
        payload: BusinessRunCreateRequest,
        trace_context: dict[str, Any],
        user: User | None = None,
    ) -> dict[str, Any] | None:
        context = self._project_context_from_payload(payload)
        project_id = context.get("projectId")
        if not project_id:
            return None
        project = session.get(BusinessProject, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
        if not self._can_user_access_project(project, user):
            raise HTTPException(status_code=403, detail="PROJECT_FORBIDDEN")
        self._validate_project_scope(project=project, trace_context=trace_context)
        input_asset_ids = self._validate_input_assets(session=session, project=project, asset_ids=context["inputAssetIds"])
        now = datetime.utcnow()
        link = BusinessProjectRunLink(
            id=f"plink_{uuid4().hex[:16]}",
            project_id=project.id,
            run_id=run.id,
            business_key=run.business_key,
            flow_step_key=context.get("flowStepKey"),
            flow_step_name=context.get("flowStepName"),
            flow_template_id=context.get("flowTemplateId") or project.flow_template_id,
            input_asset_ids=input_asset_ids,
            output_asset_ids=[],
            client_request_id=context.get("clientRequestId"),
            asset_sync_status="pending",
            extra_metadata={
                "source": run.source,
                "channel": run.channel,
                "traceId": run.trace_id,
                "requestId": run.request_id,
            },
            created_at=now,
            updated_at=now,
        )
        if context.get("flowStepKey"):
            project.current_flow_step_key = context.get("flowStepKey")
        session.add(project)
        session.add(link)
        return {
            **context,
            "projectId": project.id,
            "inputAssetIds": input_asset_ids,
            "linkId": link.id,
        }

    def sync_run_outputs_to_project_assets(self, run_id: str) -> None:
        try:
            with get_session() as session:
                link = (
                    session.execute(select(BusinessProjectRunLink).where(BusinessProjectRunLink.run_id == run_id))
                    .scalars()
                    .first()
                )
                if not link:
                    return
                run = session.get(BusinessRun, run_id)
                if not run:
                    link.asset_sync_status = "failed"
                    link.asset_sync_error = "BUSINESS_RUN_NOT_FOUND"
                    session.add(link)
                    session.commit()
                    return
                if run.status != "succeeded":
                    if run.status in {"failed", "cancelled"}:
                        link.asset_sync_status = "skipped"
                        link.asset_sync_error = run.error_message
                        session.add(link)
                        session.commit()
                    return
                if link.asset_sync_status == "succeeded" and link.output_asset_ids:
                    return
                existing = (
                    session.execute(
                        select(BusinessProjectAsset).where(BusinessProjectAsset.source_run_id == run.id)
                    )
                    .scalars()
                    .all()
                )
                if existing:
                    link.output_asset_ids = [asset.id for asset in existing]
                    link.asset_sync_status = "succeeded"
                    link.asset_sync_error = None
                    link.updated_at = datetime.utcnow()
                    session.add(link)
                    session.commit()
                    return
                created_assets = self._create_assets_from_run(session=session, link=link, run=run)
                link.output_asset_ids = [asset.id for asset in created_assets]
                link.asset_sync_status = "succeeded" if created_assets else "skipped"
                link.asset_sync_error = None if created_assets else "NO_PROJECT_OUTPUT_ASSETS"
                link.updated_at = datetime.utcnow()
                session.add(link)
                session.commit()
        except Exception as exc:  # pragma: no cover - defensive observability path
            logger.warning("business project asset sync failed: run_id=%s error=%s", run_id, exc)
            self._mark_asset_sync_failed(run_id=run_id, detail=str(exc)[:1000])

    def _create_assets_from_run(
        self,
        *,
        session,
        link: BusinessProjectRunLink,
        run: BusinessRun,
    ) -> list[BusinessProjectAsset]:
        rows: list[BusinessProjectAsset] = []
        image_urls = self._normalize_url_list(run.image_urls)
        video_urls = self._normalize_url_list(run.video_urls)
        flow_step_key = link.flow_step_key
        now = datetime.utcnow()
        for index, url in enumerate(image_urls):
            row = BusinessProjectAsset(
                id=f"asset_{uuid4().hex[:16]}",
                project_id=link.project_id,
                asset_type=self._asset_type_for_run(run.business_key),
                url=url,
                content_type=self._content_type_for_url(url, fallback="image"),
                source_run_id=run.id,
                source_business_key=run.business_key,
                source_flow_step_key=flow_step_key,
                source_output_index=index,
                selected=False,
                extra_metadata=self._run_asset_metadata(run=run, output_kind="image", output_index=index),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            rows.append(row)
        for index, url in enumerate(video_urls):
            row = BusinessProjectAsset(
                id=f"asset_{uuid4().hex[:16]}",
                project_id=link.project_id,
                asset_type="video",
                url=url,
                content_type=self._content_type_for_url(url, fallback="video"),
                source_run_id=run.id,
                source_business_key=run.business_key,
                source_flow_step_key=flow_step_key,
                source_output_index=index,
                selected=False,
                extra_metadata=self._run_asset_metadata(run=run, output_kind="video", output_index=index),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            rows.append(row)
        return rows

    def _mark_asset_sync_failed(self, *, run_id: str, detail: str) -> None:
        try:
            with get_session() as session:
                link = (
                    session.execute(select(BusinessProjectRunLink).where(BusinessProjectRunLink.run_id == run_id))
                    .scalars()
                    .first()
                )
                if not link:
                    return
                link.asset_sync_status = "failed"
                link.asset_sync_error = detail or "PROJECT_ASSET_SYNC_FAILED"
                link.updated_at = datetime.utcnow()
                session.add(link)
                session.commit()
        except Exception:
            logger.exception("failed to mark business project asset sync failure: run_id=%s", run_id)

    def _project_context_from_payload(self, payload: BusinessRunCreateRequest) -> dict[str, Any]:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        nested = metadata.get("projectContext") if isinstance(metadata.get("projectContext"), dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        input_asset_ids = self._first_value(
            payload.inputAssetIds,
            metadata.get("inputAssetIds"),
            metadata.get("input_asset_ids"),
            nested.get("inputAssetIds"),
            nested.get("input_asset_ids"),
            inputs.get("inputAssetIds"),
            inputs.get("input_asset_ids"),
        )
        return {
            "projectId": self._short_text(
                self._first_string(
                    payload.projectId,
                    metadata.get("projectId"),
                    metadata.get("project_id"),
                    nested.get("projectId"),
                    nested.get("project_id"),
                    inputs.get("projectId"),
                    inputs.get("project_id"),
                ),
                64,
            ),
            "flowStepKey": self._short_text(
                self._first_string(
                    payload.flowStepKey,
                    metadata.get("flowStepKey"),
                    metadata.get("flow_step_key"),
                    nested.get("flowStepKey"),
                    nested.get("flow_step_key"),
                    inputs.get("flowStepKey"),
                    inputs.get("flow_step_key"),
                ),
                64,
            ),
            "flowStepName": self._short_text(
                self._first_string(
                    payload.flowStepName,
                    metadata.get("flowStepName"),
                    metadata.get("flow_step_name"),
                    nested.get("flowStepName"),
                    nested.get("flow_step_name"),
                    inputs.get("flowStepName"),
                    inputs.get("flow_step_name"),
                ),
                128,
            ),
            "flowTemplateId": self._short_text(
                self._first_string(
                    payload.flowTemplateId,
                    metadata.get("flowTemplateId"),
                    metadata.get("flow_template_id"),
                    nested.get("flowTemplateId"),
                    nested.get("flow_template_id"),
                    inputs.get("flowTemplateId"),
                    inputs.get("flow_template_id"),
                ),
                64,
            ),
            "clientRequestId": self._short_text(
                self._first_string(
                    payload.clientRequestId,
                    metadata.get("clientRequestId"),
                    metadata.get("client_request_id"),
                    nested.get("clientRequestId"),
                    nested.get("client_request_id"),
                    inputs.get("clientRequestId"),
                    inputs.get("client_request_id"),
                ),
                128,
            ),
            "inputAssetIds": self._normalize_id_list(input_asset_ids if isinstance(input_asset_ids, list) else [input_asset_ids]),
        }

    def _validate_input_assets(self, *, session, project: BusinessProject, asset_ids: list[str]) -> list[str]:
        normalized = self._normalize_id_list(asset_ids)
        for asset_id in normalized:
            asset = session.get(BusinessProjectAsset, asset_id)
            if not asset or asset.project_id != project.id:
                raise HTTPException(status_code=400, detail="PROJECT_RUN_LINK_INVALID")
        return normalized

    def _validate_project_scope(self, *, project: BusinessProject, trace_context: dict[str, Any]) -> None:
        tenant_id = self._short_text(trace_context.get("tenantId"), 64)
        client_id = self._short_text(trace_context.get("clientId"), 64)
        if project.tenant_id and tenant_id and project.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="PROJECT_FORBIDDEN")
        if project.client_id and client_id and project.client_id != client_id:
            raise HTTPException(status_code=403, detail="PROJECT_FORBIDDEN")

    def _load_project_for_user(self, session, *, project_id: str, user: User | None) -> BusinessProject:
        normalized = self._short_text(project_id, 64)
        if not normalized:
            raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
        row = session.get(BusinessProject, normalized)
        if not row:
            raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
        if not self._can_user_access_project(row, user):
            raise HTTPException(status_code=403, detail="PROJECT_FORBIDDEN")
        return row

    def _apply_access_filters(self, stmt, *, user: User | None):  # noqa: ANN001
        if self._is_privileged_business_user(user):
            return stmt
        user_id = self._safe_user_id(user)
        user_tenant_id = self._short_text(getattr(user, "tenant_id", None), 64)
        user_client_id = self._short_text(getattr(user, "client_id", None), 64)
        if user_tenant_id:
            stmt = stmt.where(BusinessProject.tenant_id == user_tenant_id)
            if user_client_id:
                stmt = stmt.where(
                    or_(
                        BusinessProject.client_id.is_(None),
                        BusinessProject.client_id == user_client_id,
                    )
                )
            return stmt
        if user_id:
            return stmt.where(BusinessProject.owner_user_id == user_id)
        return stmt.where(BusinessProject.owner_user_id.is_(None), BusinessProject.tenant_id.is_(None))

    def _can_user_access_project(self, project: BusinessProject, user: User | None) -> bool:
        if self._is_privileged_business_user(user):
            return True
        user_id = self._safe_user_id(user)
        if project.owner_user_id and user_id and project.owner_user_id == user_id:
            return True
        user_tenant_id = self._short_text(getattr(user, "tenant_id", None), 64)
        user_client_id = self._short_text(getattr(user, "client_id", None), 64)
        if user_tenant_id and project.tenant_id == user_tenant_id:
            if user_client_id and project.client_id and project.client_id != user_client_id:
                return False
            return True
        return not project.owner_user_id and not project.tenant_id

    def _resolve_scope(
        self,
        *,
        user: User | None,
        tenant_id: str | None,
        client_id: str | None,
    ) -> tuple[str | None, str | None]:
        explicit_tenant = self._short_text(tenant_id, 64)
        explicit_client = self._short_text(client_id, 64)
        user_tenant = self._short_text(getattr(user, "tenant_id", None), 64)
        user_client = self._short_text(getattr(user, "client_id", None), 64)
        if user is not None and not self._is_privileged_business_user(user):
            if str(getattr(user, "role", "") or "").strip() == "client" and not user_tenant:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_REQUIRED")
            if explicit_tenant and user_tenant and explicit_tenant != user_tenant:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_FORBIDDEN")
            if explicit_client and user_client and explicit_client != user_client:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_FORBIDDEN")
            return user_tenant or explicit_tenant, user_client or explicit_client
        return explicit_tenant or user_tenant, explicit_client or user_client

    @staticmethod
    def _project_to_dict(row: BusinessProject, *, session=None) -> dict[str, Any]:
        asset_count = run_count = selection_count = export_package_count = 0
        latest_run_status = None
        if session is not None:
            asset_count = session.execute(
                select(func.count(BusinessProjectAsset.id)).where(BusinessProjectAsset.project_id == row.id)
            ).scalar_one() or 0
            run_count = session.execute(
                select(func.count(BusinessProjectRunLink.id)).where(BusinessProjectRunLink.project_id == row.id)
            ).scalar_one() or 0
            selection_count = session.execute(
                select(func.count(BusinessProjectSelection.id)).where(BusinessProjectSelection.project_id == row.id)
            ).scalar_one() or 0
            export_package_count = session.execute(
                select(func.count(BusinessExportPackage.id)).where(BusinessExportPackage.project_id == row.id)
            ).scalar_one() or 0
            latest_link = (
                session.execute(
                    select(BusinessProjectRunLink)
                    .where(BusinessProjectRunLink.project_id == row.id)
                    .order_by(BusinessProjectRunLink.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if latest_link:
                latest_run = session.get(BusinessRun, latest_link.run_id)
                latest_run_status = latest_run.status if latest_run else None
        return {
            "id": row.id,
            "name": row.name,
            "scenario": row.scenario,
            "status": row.status,
            "tenant_id": row.tenant_id,
            "client_id": row.client_id,
            "owner_user_id": row.owner_user_id,
            "owner_user_name": row.owner_user_name,
            "current_flow_step_key": row.current_flow_step_key,
            "flow_template_id": row.flow_template_id,
            "extra_metadata": row.extra_metadata or {},
            "asset_count": int(asset_count or 0),
            "run_count": int(run_count or 0),
            "selection_count": int(selection_count or 0),
            "export_package_count": int(export_package_count or 0),
            "latest_run_status": latest_run_status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _asset_to_dict(row: BusinessProjectAsset) -> dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "asset_type": row.asset_type,
            "url": row.url,
            "content_type": row.content_type,
            "file_name": row.file_name,
            "source_run_id": row.source_run_id,
            "source_business_key": row.source_business_key,
            "source_flow_step_key": row.source_flow_step_key,
            "source_output_index": row.source_output_index,
            "quality_grade": row.quality_grade,
            "input_tags": row.input_tags or [],
            "issue_tags": row.issue_tags or [],
            "selected": bool(row.selected),
            "extra_metadata": row.extra_metadata or {},
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _run_link_to_dict(self, row: BusinessProjectRunLink, *, session=None) -> dict[str, Any]:
        status = error_message = None
        if session is not None:
            run = session.get(BusinessRun, row.run_id)
            if run:
                status = run.status
                error_message = run.error_message
        return {
            "id": row.id,
            "project_id": row.project_id,
            "run_id": row.run_id,
            "business_key": row.business_key,
            "status": status,
            "flow_step_key": row.flow_step_key,
            "flow_step_name": row.flow_step_name,
            "flow_template_id": row.flow_template_id,
            "input_asset_ids": row.input_asset_ids or [],
            "output_asset_ids": row.output_asset_ids or [],
            "client_request_id": row.client_request_id,
            "asset_sync_status": row.asset_sync_status,
            "asset_sync_error": row.asset_sync_error,
            "error_code": self._error_code(error_message),
            "error_message": error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _selection_to_dict(row: BusinessProjectSelection) -> dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "asset_id": row.asset_id,
            "source_run_id": row.source_run_id,
            "source_flow_step_key": row.source_flow_step_key,
            "target_flow_step_key": row.target_flow_step_key,
            "selected_by_user_id": row.selected_by_user_id,
            "selected_by_user_name": row.selected_by_user_name,
            "note": row.note,
            "extra_metadata": row.extra_metadata or {},
            "created_at": row.created_at,
        }

    @staticmethod
    def _export_package_to_dict(row: BusinessExportPackage) -> dict[str, Any]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "status": row.status,
            "asset_ids": row.asset_ids or [],
            "run_ids": row.run_ids or [],
            "download_url": row.download_url,
            "manifest": row.manifest or {},
            "summary": row.summary or {},
            "error_code": row.error_code,
            "error_message": row.error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _normalize_project_status(value: str | None) -> str:
        normalized = str(value or "draft").strip().lower()
        if normalized not in PROJECT_STATUSES:
            raise HTTPException(status_code=400, detail="PROJECT_STATUS_INVALID")
        return normalized

    @staticmethod
    def _normalize_asset_type(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in PROJECT_ASSET_TYPES:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_TYPE_INVALID")
        return normalized

    @staticmethod
    def _normalize_scenario(value: str | None) -> str:
        normalized = str(value or "general").strip()
        if not PROJECT_SCENARIO_PATTERN.match(normalized):
            raise HTTPException(status_code=400, detail="PROJECT_SCENARIO_INVALID")
        return normalized

    @staticmethod
    def _validate_asset_url(value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_URL_REQUIRED")
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_URL_INVALID")
        return text

    @staticmethod
    def _normalize_text_list(values: list[str] | None) -> list[str]:
        return [str(item).strip() for item in values or [] if str(item).strip()][:50]

    @staticmethod
    def _normalize_url_list(values: list[str] | None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for value in values or []:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            urls.append(text)
        return urls

    @staticmethod
    def _normalize_id_list(values: Any) -> list[str]:
        if values is None:
            return []
        raw = values if isinstance(values, list) else [values]
        out: list[str] = []
        seen: set[str] = set()
        for value in raw:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text[:64])
        return out

    @staticmethod
    def _required_text(value: str | None, error_code: str, *, max_length: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail=error_code)
        return text[:max_length]

    @staticmethod
    def _short_text(value: Any, max_length: int) -> str | None:
        text = str(value or "").strip()
        return text[:max_length] if text else None

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _first_value(*values: Any) -> Any | None:
        for value in values:
            if value not in (None, "", []):
                return value
        return None

    @staticmethod
    def _clean_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        blocked = {"apiKey", "api_key", "secret", "password", "token", "authorization"}
        return {
            str(key): BusinessProjectService._json_safe(item)
            for key, item in value.items()
            if str(key) not in blocked
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): BusinessProjectService._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [BusinessProjectService._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [BusinessProjectService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _export_storage_dir() -> Path:
        raw = (get_settings().business_export_storage_dir or "runtime/business_exports").strip()
        base = Path(raw)
        if not base.is_absolute():
            base = Path(__file__).resolve().parents[2] / raw
        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def _safe_path_segment(value: str, *, fallback: str) -> str:
        cleaned = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in ("-", "_"))
        return cleaned[:80] if cleaned else fallback

    @staticmethod
    def _safe_filename(value: str, *, fallback: str) -> str:
        cleaned = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in ("-", "_", "."))
        return cleaned[:80] if cleaned else fallback

    def _export_package_file_path(self, *, project_id: str, package_id: str) -> Path:
        project_segment = self._safe_path_segment(project_id, fallback="project")
        package_segment = self._safe_path_segment(package_id, fallback="package")
        return self._export_storage_dir() / project_segment / f"{package_segment}.zip"

    @staticmethod
    def _export_package_download_url(*, project_id: str, package_id: str, base_url: str | None = None) -> str:
        path = f"/api/business/projects/{project_id}/exports/{package_id}/download"
        normalized_base = str(base_url or "").strip().rstrip("/")
        return f"{normalized_base}{path}" if normalized_base else path

    def _write_export_package_archive(
        self,
        *,
        project: BusinessProject,
        package_id: str,
        manifest: dict[str, Any],
        summary: dict[str, Any],
        assets: list[BusinessProjectAsset],
        run_ids: list[str],
    ) -> Path:
        file_path = self._export_package_file_path(project_id=project.id, package_id=package_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        assets_payload = [self._asset_to_dict(asset) for asset in assets]
        readme = "\n".join(
            [
                "PODI business project export package",
                f"Project: {project.name}",
                f"Project ID: {project.id}",
                f"Package ID: {package_id}",
                "",
                "This package contains manifest and evidence files.",
                "Media binaries are referenced by URL in manifest.json and assets.json.",
                "Do not expose internal run/debug data outside authorized business users.",
                "",
            ]
        )
        with zipfile.ZipFile(file_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", readme)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("summary.json", json.dumps(self._json_safe(summary), ensure_ascii=False, indent=2))
            archive.writestr("assets.json", json.dumps(self._json_safe(assets_payload), ensure_ascii=False, indent=2))
            archive.writestr("run_ids.json", json.dumps(run_ids, ensure_ascii=False, indent=2))
        return file_path

    @staticmethod
    def _safe_user_id(user: User | None) -> str | None:
        if not user:
            return None
        user_id = str(getattr(user, "id", "") or "").strip()
        if not user_id or user_id == "service" or user_id.startswith("business-api-key:"):
            return None
        return user_id[:64]

    @staticmethod
    def _actor_username(user: User | None) -> str | None:
        if not user:
            return None
        value = getattr(user, "username", None) or getattr(user, "email", None) or getattr(user, "id", None)
        return str(value).strip()[:128] if value else None

    @staticmethod
    def _is_privileged_business_user(user: User | None) -> bool:
        if not user:
            return False
        if str(getattr(user, "id", "") or "").strip() == "service":
            return True
        return str(getattr(user, "role", "") or "").strip() == "admin"

    @staticmethod
    def _asset_type_for_run(business_key: str | None) -> str:
        mapping = {
            "pattern_extract": "pattern",
            "fission": "variant",
            "text_fission": "variant",
            "outpaint": "variant",
            "image_edit": "product_image",
        }
        return mapping.get(str(business_key or "").strip(), "other")

    @staticmethod
    def _run_asset_metadata(*, run: BusinessRun, output_kind: str, output_index: int) -> dict[str, Any]:
        return {
            "outputKind": output_kind,
            "outputIndex": output_index,
            "businessVersionId": run.business_version_id,
            "version": run.version,
            "traceId": run.trace_id,
            "requestId": run.request_id,
        }

    @staticmethod
    def _content_type_for_url(url: str, *, fallback: str) -> str | None:
        path = urlparse(url).path.lower()
        if path.endswith(".png"):
            return "image/png"
        if path.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if path.endswith(".webp"):
            return "image/webp"
        if path.endswith(".mp4"):
            return "video/mp4"
        if fallback == "image":
            return "image"
        if fallback == "video":
            return "video"
        return None

    @staticmethod
    def _quality_summary(assets: list[BusinessProjectAsset]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for asset in assets:
            key = str(asset.quality_grade or "unreviewed").strip() or "unreviewed"
            summary[key] = summary.get(key, 0) + 1
        return summary

    @staticmethod
    def _error_code(message: str | None) -> str | None:
        text = str(message or "").strip()
        if not text:
            return None
        match = re.search(r"\b([A-Z][A-Z0-9_]{2,})\b", text)
        return match.group(1) if match else None


_business_project_service: BusinessProjectService | None = None


def get_business_project_service() -> BusinessProjectService:
    global _business_project_service
    if _business_project_service is None:
        _business_project_service = BusinessProjectService()
    return _business_project_service
