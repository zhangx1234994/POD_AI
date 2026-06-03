from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import zipfile

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.business_projects as business_projects_module
from app.core.db import Base
from app.models.integration import (
    BusinessProjectAsset,
    BusinessProjectRunLink,
    BusinessRun,
)
from app.models.user import User
from app.schemas.business import (
    BusinessExportPackageCreateRequest,
    BusinessProjectAssetCreateRequest,
    BusinessProjectCreateRequest,
    BusinessProjectSelectionCreateRequest,
    BusinessRunCreateRequest,
)
from app.services.business_projects import BusinessProjectService


def _install_project_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(business_projects_module, "get_session", fake_get_session)
    return testing_session


def _client_user(*, tenant_id: str = "tenant-a", client_id: str = "studio") -> User:
    return User(
        id=f"business-api-key:test-{tenant_id}-{client_id}",
        email="business@example.com",
        username="业务方",
        password_hash="",
        role="client",
        status="active",
        tenant_id=tenant_id,
        client_id=client_id,
    )


def test_business_project_asset_selection_and_export(monkeypatch, tmp_path) -> None:
    _install_project_db(monkeypatch)
    monkeypatch.setattr(BusinessProjectService, "_export_storage_dir", staticmethod(lambda: tmp_path))
    user = _client_user()
    service = BusinessProjectService()

    project = service.create_project(
        BusinessProjectCreateRequest(
            name="夏季花纹项目",
            scenario="pattern_to_product",
            flowTemplateId="pattern_to_product_v1",
        ),
        user=user,
    )
    assert project["tenant_id"] == "tenant-a"
    assert project["client_id"] == "studio"

    asset = service.create_asset(
        project["id"],
        BusinessProjectAssetCreateRequest(
            assetType="input_image",
            url="https://podi.oss-cn-hangzhou.aliyuncs.com/input.png",
            flowStepKey="upload_assets",
        ),
        user=user,
    )
    assert asset["asset_type"] == "input_image"
    assert asset["selected"] is False

    selections = service.create_selection(
        project["id"],
        BusinessProjectSelectionCreateRequest(
            assetIds=[asset["id"]],
            sourceFlowStepKey="upload_assets",
            targetFlowStepKey="variant_fission",
            note="进入裂变",
        ),
        user=user,
    )
    assert len(selections) == 1
    assert selections[0]["target_flow_step_key"] == "variant_fission"

    package = service.create_export_package(
        project["id"],
        BusinessExportPackageCreateRequest(assetIds=[asset["id"]]),
        user=user,
        base_url="http://testserver",
    )
    assert package["status"] == "ready"
    assert package["asset_ids"] == [asset["id"]]
    assert package["manifest"]["projectId"] == project["id"]
    assert package["download_url"].endswith(f"/api/business/projects/{project['id']}/exports/{package['id']}/download")

    file_path, file_name = service.get_export_package_file(project["id"], package["id"], user=user)
    assert file_name.endswith(f"{package['id']}.zip")
    with zipfile.ZipFile(file_path) as archive:
        assert sorted(archive.namelist()) == [
            "README.txt",
            "assets.json",
            "manifest.json",
            "run_ids.json",
            "summary.json",
        ]
        assert project["id"] in archive.read("manifest.json").decode("utf-8")

    file_path.unlink()
    with pytest.raises(HTTPException) as missing_file:
        service.get_export_package_file(project["id"], package["id"], user=user)
    assert missing_file.value.detail == "PROJECT_EXPORT_FILE_NOT_FOUND"

    detail = service.get_project_detail(project["id"], user=user)
    assert detail["project"]["asset_count"] == 1
    assert detail["project"]["selection_count"] == 1
    assert detail["project"]["export_package_count"] == 1
    assert detail["assets"][0]["selected"] is True


def test_business_project_rejects_invalid_inputs_and_cross_tenant(monkeypatch) -> None:
    _install_project_db(monkeypatch)
    service = BusinessProjectService()
    user = _client_user(tenant_id="tenant-a", client_id="studio")
    other_user = _client_user(tenant_id="tenant-b", client_id="studio")

    with pytest.raises(HTTPException) as missing_name:
        service.create_project(BusinessProjectCreateRequest(name="", scenario="general"), user=user)
    assert missing_name.value.detail == "PROJECT_NAME_REQUIRED"

    with pytest.raises(HTTPException) as bad_scenario:
        service.create_project(BusinessProjectCreateRequest(name="项目", scenario="../bad"), user=user)
    assert bad_scenario.value.detail == "PROJECT_SCENARIO_INVALID"

    project = service.create_project(BusinessProjectCreateRequest(name="项目", scenario="general"), user=user)

    with pytest.raises(HTTPException) as bad_url:
        service.create_asset(
            project["id"],
            BusinessProjectAssetCreateRequest(assetType="input_image", url="file:///tmp/a.png"),
            user=user,
        )
    assert bad_url.value.detail == "PROJECT_ASSET_URL_INVALID"

    with pytest.raises(HTTPException) as forbidden:
        service.get_project_detail(project["id"], user=other_user)
    assert forbidden.value.detail == "PROJECT_FORBIDDEN"


def test_business_run_context_links_project_and_syncs_output_assets(monkeypatch) -> None:
    testing_session = _install_project_db(monkeypatch)
    service = BusinessProjectService()
    user = _client_user()
    project = service.create_project(
        BusinessProjectCreateRequest(name="端到端项目", scenario="pattern_to_product"),
        user=user,
    )
    input_asset = service.create_asset(
        project["id"],
        BusinessProjectAssetCreateRequest(
            assetType="pattern",
            url="https://podi.oss-cn-hangzhou.aliyuncs.com/pattern.png",
        ),
        user=user,
    )
    run_id = "run_project_context_ok"

    with testing_session() as session:
        run = BusinessRun(
            id=run_id,
            business_key="fission",
            business_version_id=None,
            version="v-test",
            status="succeeded",
            source="business-api",
            tenant_id="tenant-a",
            client_id="studio",
            trace_id="trace-project",
            request_id="req-project",
            image_urls=["https://podi.oss-cn-hangzhou.aliyuncs.com/result.png"],
            result_payload={"imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result.png"]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
        )
        session.add(run)
        context = service.link_run_to_project(
            session=session,
            run=run,
            payload=BusinessRunCreateRequest(
                imageUrl=input_asset["url"],
                projectId=project["id"],
                flowStepKey="variant_fission",
                flowStepName="裂变候选",
                inputAssetIds=[input_asset["id"]],
                clientRequestId="client-req-1",
            ),
            trace_context={"tenantId": "tenant-a", "clientId": "studio"},
            user=user,
        )
        session.commit()
    assert context and context["projectId"] == project["id"]

    service.sync_run_outputs_to_project_assets(run_id)

    with testing_session() as session:
        link = session.execute(select(BusinessProjectRunLink).where(BusinessProjectRunLink.run_id == run_id)).scalar_one()
        assert link.flow_step_key == "variant_fission"
        assert link.input_asset_ids == [input_asset["id"]]
        assert link.asset_sync_status == "succeeded"
        assert len(link.output_asset_ids) == 1
        output_asset = session.get(BusinessProjectAsset, link.output_asset_ids[0])
        assert output_asset is not None
        assert output_asset.asset_type == "variant"
        assert output_asset.source_run_id == run_id
        assert output_asset.url == "https://podi.oss-cn-hangzhou.aliyuncs.com/result.png"


def test_business_run_context_rejects_foreign_input_asset(monkeypatch) -> None:
    testing_session = _install_project_db(monkeypatch)
    service = BusinessProjectService()
    user = _client_user()
    project_a = service.create_project(BusinessProjectCreateRequest(name="项目 A"), user=user)
    project_b = service.create_project(BusinessProjectCreateRequest(name="项目 B"), user=user)
    foreign_asset = service.create_asset(
        project_b["id"],
        BusinessProjectAssetCreateRequest(
            assetType="input_image",
            url="https://podi.oss-cn-hangzhou.aliyuncs.com/foreign.png",
        ),
        user=user,
    )

    with testing_session() as session:
        run = BusinessRun(
            id="run_foreign_asset",
            business_key="fission",
            status="queued",
            source="business-api",
            tenant_id="tenant-a",
            client_id="studio",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(run)
        with pytest.raises(HTTPException) as exc:
            service.link_run_to_project(
                session=session,
                run=run,
                payload=BusinessRunCreateRequest(
                    imageUrl=foreign_asset["url"],
                    projectId=project_a["id"],
                    inputAssetIds=[foreign_asset["id"]],
                ),
                trace_context={"tenantId": "tenant-a", "clientId": "studio"},
                user=user,
            )
    assert exc.value.detail == "PROJECT_RUN_LINK_INVALID"
