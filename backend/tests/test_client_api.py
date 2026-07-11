from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.deps.auth as auth_deps
import app.services.auth_service as auth_service_module
import app.services.client_workspace as client_workspace_module
import app.services.wallet as wallet_module
from app.core.db import Base
from app.models.integration import BusinessProject, BusinessProjectAsset
from app.models.user import User
from app.models.wallet import PackageBalance
from app.routers import auth as auth_router
from app.routers import client as client_router
from app.services.auth_service import auth_service


def _install_client_db(monkeypatch):
    with auth_service._login_failure_lock:
        auth_service._login_failures.clear()
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

    monkeypatch.setattr(auth_service_module, "get_session", fake_get_session)
    monkeypatch.setattr(auth_deps, "get_session", fake_get_session)
    monkeypatch.setattr(client_workspace_module, "get_session", fake_get_session)
    monkeypatch.setattr(wallet_module, "get_session", fake_get_session)

    with testing_session() as session:
        session.add(
            User(
                id="client-user-1",
                email="client@podi.local",
                username="clientuser",
                display_name="客户端用户",
                password_hash=auth_service.hash_password("Client12345"),
                role="user",
                status="active",
                tenant_id="tenant-podi",
                client_id="podi-main",
            )
        )
        session.add(
            PackageBalance(
                user_id="client-user-1",
                package_key="sample_coupon_new_user",
                package_name="新人产品券",
                business_key="sample_request",
                total_units=3,
                used_units=1,
                frozen_units=1,
                unit_name="张",
                status="active",
                source="manual",
                expires_at=datetime.utcnow() + timedelta(days=7),
                extra_metadata={"couponType": "product"},
            )
        )
        session.add(
            PackageBalance(
                user_id="client-user-1",
                package_key="image_credit_pack",
                package_name="AI 作图次数包",
                business_key="image_process",
                total_units=99,
                used_units=0,
                frozen_units=0,
                unit_name="次",
                status="active",
                source="manual",
            )
        )
        session.commit()
    return testing_session


def _client_app() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(client_router.router)
    return TestClient(app)


def _login_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "clientuser", "password": "Client12345"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_client_me_assets_and_wallet_are_server_backed(monkeypatch) -> None:
    testing_session = _install_client_db(monkeypatch)
    client = _client_app()
    headers = _login_headers(client)

    me_response = client.get("/api/client/me", headers=headers)
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["user"]["username"] == "clientuser"
    assert me["workspace"]["scenario"] == "client_default_workspace"
    workspace_id = me["workspace"]["id"]

    repeated = client.get("/api/client/workspace", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == workspace_id

    asset_response = client.post(
        "/api/client/assets",
        headers=headers,
        json={
            "assetType": "input_image",
            "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
            "fileName": "input.png",
            "metadata": {"title": "测试上传图"},
        },
    )
    assert asset_response.status_code == 200
    asset = asset_response.json()
    assert asset["assetType"] == "input_image"
    assert asset["title"] == "测试上传图"

    asset_list = client.get("/api/client/assets", headers=headers)
    assert asset_list.status_code == 200
    assert asset_list.json()["total"] == 1
    assert asset_list.json()["items"][0]["id"] == asset["id"]

    wallet = client.get("/api/client/wallet", headers=headers)
    assert wallet.status_code == 200
    wallet_data = wallet.json()
    assert wallet_data["pointBalance"] == 500
    assert wallet_data["productCouponCount"] == 1
    assert wallet_data["productCoupons"][0]["packageKey"] == "sample_coupon_new_user"
    assert wallet_data["productCoupons"][0]["remainingUnits"] == 1

    with testing_session() as session:
        projects = session.execute(select(BusinessProject)).scalars().all()
        assets = session.execute(select(BusinessProjectAsset)).scalars().all()
    assert len(projects) == 1
    assert projects[0].scenario == "client_default_workspace"
    assert len(assets) == 1
    assert assets[0].project_id == workspace_id


def test_client_api_requires_auth_and_valid_assets(monkeypatch) -> None:
    _install_client_db(monkeypatch)
    client = _client_app()

    missing_auth = client.get("/api/client/me")
    assert missing_auth.status_code == 401
    assert missing_auth.json()["detail"] == "AUTHORIZATION_REQUIRED"

    headers = _login_headers(client)
    bad_type = client.post(
        "/api/client/assets",
        headers=headers,
        json={"assetType": "unknown", "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/a.png"},
    )
    assert bad_type.status_code == 400
    assert bad_type.json()["detail"] == "PROJECT_ASSET_TYPE_INVALID"

    bad_url = client.post(
        "/api/client/assets",
        headers=headers,
        json={"assetType": "input_image", "url": "file:///tmp/a.png"},
    )
    assert bad_url.status_code == 400
    assert bad_url.json()["detail"] == "PROJECT_ASSET_URL_INVALID"
