from __future__ import annotations

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.deps.auth as auth_deps
import app.services.auth_service as auth_service_module
from app.core.db import Base
from app.models.user import User, UserSession
from app.routers import auth as auth_router
from app.services.auth_service import auth_service


def install_auth_db(monkeypatch):
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
    with testing_session() as session:
        session.add(
            User(
                id="admin-user",
                email="admin@podi.local",
                username="admin",
                display_name="管理员",
                password_hash=auth_service.hash_password("admin123"),
                role="admin",
                status="active",
            )
        )
        session.commit()
    return fake_get_session


def make_auth_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    return TestClient(app)


def test_login_creates_session_and_refresh_rotates(monkeypatch) -> None:
    get_session = install_auth_db(monkeypatch)
    client = make_auth_client()

    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["role"] == "admin"
    assert login_data["user"]["username"] == "admin"
    assert login_data["refreshToken"]

    sessions_resp = client.get("/api/auth/sessions", headers={"Authorization": f"Bearer {login_data['accessToken']}"})
    assert sessions_resp.status_code == 200
    assert len(sessions_resp.json()["items"]) == 1

    refresh_resp = client.post("/api/auth/refresh", json={"refreshToken": login_data["refreshToken"]})
    assert refresh_resp.status_code == 200
    next_refresh = refresh_resp.json()["refreshToken"]
    assert next_refresh and next_refresh != login_data["refreshToken"]

    with get_session() as session:
        statuses = [row.status for row in session.execute(select(UserSession)).scalars().all()]
    assert sorted(statuses) == ["active", "rotated"]

    logout_resp = client.post(
        "/api/auth/logout",
        json={"refreshToken": next_refresh},
        headers={"Authorization": f"Bearer {refresh_resp.json()['accessToken']}"},
    )
    assert logout_resp.status_code == 200

    rejected = client.post("/api/auth/refresh", json={"refreshToken": next_refresh})
    assert rejected.status_code == 401
    assert rejected.json()["detail"] == "SESSION_REVOKED"


def test_invite_register_inherits_tenant_and_admin_can_list_users(monkeypatch) -> None:
    install_auth_db(monkeypatch)
    client = make_auth_client()
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['accessToken']}"}

    invite_resp = client.post(
        "/api/auth/invite-codes",
        json={"tenantId": "tenant-a", "clientId": "client-web", "maxUses": 1, "note": "业务方 A"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 200
    invite = invite_resp.json()
    assert invite["tenantId"] == "tenant-a"
    assert invite["usedCount"] == 0

    register_resp = client.post(
        "/api/auth/register",
        json={
            "email": "designer@example.com",
            "username": "designer",
            "password": "Designer123",
            "inviteCode": invite["code"],
            "displayName": "设计师",
        },
    )
    assert register_resp.status_code == 200
    user = register_resp.json()["user"]
    assert user["tenantId"] == "tenant-a"
    assert user["clientId"] == "client-web"
    assert user["displayName"] == "设计师"

    reused = client.post(
        "/api/auth/register",
        json={
            "email": "other@example.com",
            "username": "other",
            "password": "Designer123",
            "inviteCode": invite["code"],
        },
    )
    assert reused.status_code == 409
    assert reused.json()["detail"] == "INVITE_CODE_USED"

    users_resp = client.get("/api/auth/users", headers=admin_headers)
    assert users_resp.status_code == 200
    assert {item["username"] for item in users_resp.json()["items"]} == {"admin", "designer"}


def test_auth_failure_paths_are_explicit(monkeypatch) -> None:
    get_session = install_auth_db(monkeypatch)
    with get_session() as session:
        session.add(
            User(
                id="normal-user",
                email="normal@example.com",
                username="normal",
                password_hash=auth_service.hash_password("Normal12345"),
                role="user",
                status="active",
            )
        )
        session.commit()

    client = make_auth_client()

    missing_identifier = client.post("/api/auth/login", json={"password": "admin123"})
    assert missing_identifier.status_code == 400
    assert missing_identifier.json()["detail"] == "LOGIN_IDENTIFIER_REQUIRED"

    invalid_refresh = client.post("/api/auth/refresh", json={"refreshToken": "not-a-jwt"})
    assert invalid_refresh.status_code == 401
    assert invalid_refresh.json()["detail"] == "INVALID_REFRESH_TOKEN"

    invalid_invite = client.post(
        "/api/auth/register",
        json={
            "email": "ghost@example.com",
            "username": "ghost",
            "password": "Ghost12345",
            "inviteCode": "missing",
        },
    )
    assert invalid_invite.status_code == 400
    assert invalid_invite.json()["detail"] == "INVITE_CODE_INVALID"

    weak_password = client.post(
        "/api/auth/register",
        json={
            "email": "weak@example.com",
            "username": "weak",
            "password": "short",
            "inviteCode": "missing",
        },
    )
    assert weak_password.status_code == 400
    assert weak_password.json()["detail"] == "PASSWORD_TOO_SHORT"

    normal_login = client.post("/api/auth/login", json={"username": "normal", "password": "Normal12345"}).json()
    forbidden = client.post(
        "/api/auth/invite-codes",
        json={"tenantId": "tenant-a"},
        headers={"Authorization": f"Bearer {normal_login['accessToken']}"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "ADMIN_ONLY"


def test_login_failure_rate_limit_is_explicit(monkeypatch) -> None:
    install_auth_db(monkeypatch)
    client = make_auth_client()
    headers = {"x-forwarded-for": "10.1.1.10"}

    for _ in range(5):
        rejected = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
            headers=headers,
        )
        assert rejected.status_code == 401
        assert rejected.json()["detail"] == "INVALID_CREDENTIALS"

    blocked = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "LOGIN_RATE_LIMITED"


def test_admin_can_revoke_session_and_disable_invite(monkeypatch) -> None:
    get_session = install_auth_db(monkeypatch)
    with get_session() as session:
        session.add(
            User(
                id="normal-user",
                email="normal@example.com",
                username="normal",
                password_hash=auth_service.hash_password("Normal12345"),
                role="user",
                status="active",
            )
        )
        session.commit()

    client = make_auth_client()
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['accessToken']}"}
    normal_login = client.post("/api/auth/login", json={"username": "normal", "password": "Normal12345"}).json()

    sessions_resp = client.get("/api/auth/sessions/all", headers=admin_headers)
    assert sessions_resp.status_code == 200
    normal_session = next(item for item in sessions_resp.json()["items"] if item["username"] == "normal")
    assert normal_session["status"] == "active"
    assert normal_session["email"] == "normal@example.com"

    revoke_resp = client.post(f"/api/auth/sessions/{normal_session['id']}/revoke", headers=admin_headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    rejected_refresh = client.post("/api/auth/refresh", json={"refreshToken": normal_login["refreshToken"]})
    assert rejected_refresh.status_code == 401
    assert rejected_refresh.json()["detail"] == "SESSION_REVOKED"

    invite_resp = client.post(
        "/api/auth/invite-codes",
        json={"tenantId": "tenant-b", "maxUses": 2},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 200
    invite = invite_resp.json()

    disabled_resp = client.post(f"/api/auth/invite-codes/{invite['id']}/disable", headers=admin_headers)
    assert disabled_resp.status_code == 200
    assert disabled_resp.json()["status"] == "disabled"

    register_resp = client.post(
        "/api/auth/register",
        json={
            "email": "blocked@example.com",
            "username": "blocked",
            "password": "Blocked12345",
            "inviteCode": invite["code"],
        },
    )
    assert register_resp.status_code == 409
    assert register_resp.json()["detail"] == "INVITE_CODE_INACTIVE"


def test_admin_can_update_user_scope_and_scope_summary_reports_risks(monkeypatch) -> None:
    get_session = install_auth_db(monkeypatch)
    with get_session() as session:
        session.add(
            User(
                id="client-user",
                email="client@example.com",
                username="client",
                password_hash=auth_service.hash_password("Client12345"),
                role="client",
                status="active",
            )
        )
        session.commit()

    client = make_auth_client()
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['accessToken']}"}

    summary_before = client.get("/api/auth/scope-summary", headers=admin_headers)
    assert summary_before.status_code == 200
    assert summary_before.json()["totals"]["unscopedClientUsers"] == 1
    assert summary_before.json()["releaseReady"] is False
    assert summary_before.json()["warningRiskCount"] >= 1
    assert any(item["key"] == "unscoped_client_users" and item["count"] == 1 for item in summary_before.json()["risks"])
    assert any(item["key"] == "client_users_scoped" and item["passed"] is False for item in summary_before.json()["checklist"])
    assert any(
        item["key"] == "unscoped_client_user_blocked" and item["enforced"] is True
        for item in summary_before.json()["businessApiPolicy"]
    )
    assert {item["key"] for item in summary_before.json()["roleBoundary"]} >= {
        "admin_user",
        "client_user",
        "service_token",
        "coze_toolbox",
    }
    assert all(item["enforced"] for item in summary_before.json()["roleBoundary"])

    update_resp = client.patch(
        "/api/auth/users/client-user",
        json={
            "displayName": "业务方账号",
            "tenantId": "tenant-a",
            "clientId": "client-web",
            "note": "绑定业务方范围",
        },
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["displayName"] == "业务方账号"
    assert updated["tenantId"] == "tenant-a"
    assert updated["clientId"] == "client-web"
    assert updated["adminAudit"][0]["changedFields"] == ["displayName", "tenantId", "clientId"]
    assert updated["adminAudit"][0]["note"] == "绑定业务方范围"

    users_resp = client.get("/api/auth/users", headers=admin_headers)
    assert users_resp.status_code == 200
    client_user = next(item for item in users_resp.json()["items"] if item["id"] == "client-user")
    assert client_user["adminAudit"][0]["actorUsername"] == "admin"

    summary_after = client.get("/api/auth/scope-summary", headers=admin_headers)
    assert summary_after.status_code == 200
    assert summary_after.json()["totals"]["unscopedClientUsers"] == 0
    assert summary_after.json()["releaseReady"] is True
    assert summary_after.json()["blockingRiskCount"] == 0
    assert summary_after.json()["warningRiskCount"] == 0
    assert any(item["tenantId"] == "tenant-a" and item["clientId"] == "client-web" for item in summary_after.json()["tenants"])
    assert all(item["passed"] for item in summary_after.json()["checklist"])
    assert all(item["enforced"] for item in summary_after.json()["businessApiPolicy"])
    assert all(item["enforced"] for item in summary_after.json()["roleBoundary"])


def test_admin_user_update_protects_self_lockout_and_revokes_disabled_user_sessions(monkeypatch) -> None:
    get_session = install_auth_db(monkeypatch)
    with get_session() as session:
        session.add(
            User(
                id="normal-user",
                email="normal@example.com",
                username="normal",
                password_hash=auth_service.hash_password("Normal12345"),
                role="user",
                status="active",
            )
        )
        session.commit()

    client = make_auth_client()
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['accessToken']}"}
    normal_login = client.post("/api/auth/login", json={"username": "normal", "password": "Normal12345"}).json()

    self_demote = client.patch(
        "/api/auth/users/admin-user",
        json={"role": "user", "note": "误操作"},
        headers=admin_headers,
    )
    assert self_demote.status_code == 409
    assert self_demote.json()["detail"] == "AUTH_SELF_LOCKOUT_FORBIDDEN"

    disabled = client.patch(
        "/api/auth/users/normal-user",
        json={"status": "inactive", "note": "离职停用"},
        headers=admin_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "inactive"
    assert "sessions" in disabled.json()["adminAudit"][0]["changedFields"]

    rejected_refresh = client.post("/api/auth/refresh", json={"refreshToken": normal_login["refreshToken"]})
    assert rejected_refresh.status_code == 401
    assert rejected_refresh.json()["detail"] == "SESSION_REVOKED"

    invalid_status = client.patch(
        "/api/auth/users/normal-user",
        json={"status": "sleeping"},
        headers=admin_headers,
    )
    assert invalid_status.status_code == 400
    assert invalid_status.json()["detail"] == "USER_STATUS_INVALID"
