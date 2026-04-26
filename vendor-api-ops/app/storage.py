"""SQLite storage for vendor-api-ops.

This keeps the service self-contained while giving us durable keys,
invocations, and usage logs. It can be replaced by MySQL/Postgres later without
changing the HTTP contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings


class VendorStorage:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or get_settings().resolved_database_path()
        self._lock = threading.Lock()
        self._ensure_schema()

    def create_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                insert into vendor_api_keys (
                    id, provider, alias, key_value, secret_value, model, status,
                    daily_quota, monthly_quota, usage_count, max_concurrency,
                    cooldown_until, last_error, last_used_at, metadata_json,
                    created_at, updated_at
                ) values (
                    :id, :provider, :alias, :key_value, :secret_value, :model, :status,
                    :daily_quota, :monthly_quota, 0, :max_concurrency,
                    null, null, null, :metadata_json, :created_at, :updated_at
                )
                """,
                {
                    **payload,
                    "metadata_json": _dump_json(payload.get("metadata") or {}),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.commit()
        return self.get_key(str(payload["id"])) or {}

    def list_keys(self, provider: str | None = None) -> list[dict[str, Any]]:
        sql = "select * from vendor_api_keys"
        params: dict[str, Any] = {}
        if provider:
            sql += " where provider = :provider"
            params["provider"] = provider
        sql += " order by provider asc, alias asc, id asc"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_key(row) for row in rows]

    def get_key(self, key_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from vendor_api_keys where id = ?", (key_id,)).fetchone()
        return _row_to_key(row) if row else None

    def update_key(self, key_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields: dict[str, Any] = {"updated_at": _now_iso()}
        if "status" in payload and payload["status"] is not None:
            fields["status"] = payload["status"]
        if "cooldown_until" in payload:
            fields["cooldown_until"] = _to_iso(payload["cooldown_until"]) if payload["cooldown_until"] is not None else None
        if "last_error" in payload:
            fields["last_error"] = payload["last_error"]
        if "metadata" in payload and payload["metadata"] is not None:
            fields["metadata_json"] = _dump_json(payload["metadata"])
        if len(fields) == 1:
            return self.get_key(key_id)
        set_clause = ", ".join(f"{key} = :{key}" for key in fields)
        with self._connect() as conn:
            conn.execute(f"update vendor_api_keys set {set_clause} where id = :id", {**fields, "id": key_id})
            conn.commit()
        return self.get_key(key_id)

    def pick_key(self, *, provider: str, model: str | None = None) -> dict[str, Any] | None:
        now = _now_iso()
        params: dict[str, Any] = {"provider": provider, "now": now}
        model_clause = ""
        if model:
            model_clause = "and (model is null or model = :model)"
            params["model"] = model
        with self._connect() as conn:
            row = conn.execute(
                f"""
                select * from vendor_api_keys
                where provider = :provider
                  and status = 'active'
                  {model_clause}
                  and (cooldown_until is null or cooldown_until <= :now)
                order by usage_count asc, last_used_at asc nulls first, id asc
                limit 1
                """,
                params,
            ).fetchone()
        return _row_to_key(row) if row else None

    def bump_key_usage(self, key_id: str) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                update vendor_api_keys
                set usage_count = usage_count + 1,
                    last_used_at = ?,
                    updated_at = ?
                where id = ?
                """,
                (now, now, key_id),
            )
            conn.commit()

    def mark_key_error(self, key_id: str, *, status: str | None = None, last_error: str | None = None, cooldown_until: Any = None) -> None:
        payload: dict[str, Any] = {}
        if status:
            payload["status"] = status
        if last_error:
            payload["last_error"] = last_error
        if cooldown_until:
            payload["cooldown_until"] = cooldown_until
        self.update_key(key_id, payload)

    def create_invocation(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        record = {
            **payload,
            "request_json": _dump_json(payload.get("request") or {}),
            "response_json": _dump_json(payload.get("response") or {}),
            "error_json": _dump_json(payload.get("error")),
            "raw_json": _dump_json(payload.get("raw") or {}),
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into vendor_invocations (
                    id, provider, model, capability_key, api_type, execution_mode,
                    status, success, vendor_task_id, request_json, response_json,
                    error_json, raw_json, created_at, updated_at
                ) values (
                    :id, :provider, :model, :capability_key, :api_type, :execution_mode,
                    :status, :success, :vendor_task_id, :request_json, :response_json,
                    :error_json, :raw_json, :created_at, :updated_at
                )
                """,
                record,
            )
            conn.commit()
        return self.get_invocation(str(payload["id"])) or {}

    def get_invocation(self, invocation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from vendor_invocations where id = ?", (invocation_id,)).fetchone()
        return _row_to_invocation(row) if row else None

    def update_invocation(self, invocation_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields: dict[str, Any] = {"updated_at": _now_iso()}
        mapping = {
            "status": "status",
            "success": "success",
            "vendor_task_id": "vendor_task_id",
            "response": "response_json",
            "error": "error_json",
            "raw": "raw_json",
        }
        for source, target in mapping.items():
            if source not in payload:
                continue
            value = payload[source]
            fields[target] = _dump_json(value) if target.endswith("_json") else value
        set_clause = ", ".join(f"{key} = :{key}" for key in fields)
        with self._connect() as conn:
            conn.execute(f"update vendor_invocations set {set_clause} where id = :id", {**fields, "id": invocation_id})
            conn.commit()
        return self.get_invocation(invocation_id)

    def create_usage_log(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into vendor_usage_logs (
                    id, invocation_id, provider, model, key_id, status,
                    error_code, latency_ms, created_at
                ) values (
                    :id, :invocation_id, :provider, :model, :key_id, :status,
                    :error_code, :latency_ms, :created_at
                )
                """,
                {**payload, "created_at": _now_iso()},
            )
            conn.commit()

    def usage_summary(self, *, window_hours: int = 24) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc).timestamp() - max(1, int(window_hours or 24)) * 3600
        cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    provider,
                    model,
                    status,
                    error_code,
                    count(*) as count,
                    avg(latency_ms) as avg_latency_ms,
                    max(created_at) as last_seen_at
                from vendor_usage_logs
                where created_at >= :cutoff
                group by provider, model, status, error_code
                order by last_seen_at desc, count desc
                """,
                {"cutoff": cutoff_iso},
            ).fetchall()
        return [
            {
                "provider": row["provider"],
                "model": row["model"],
                "status": row["status"],
                "error_code": row["error_code"],
                "count": int(row["count"] or 0),
                "avg_latency_ms": int(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None,
                "last_seen_at": row["last_seen_at"],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path.as_posix(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    create table if not exists vendor_api_keys (
                        id text primary key,
                        provider text not null,
                        alias text not null,
                        key_value text not null,
                        secret_value text,
                        model text,
                        status text not null default 'active',
                        daily_quota integer,
                        monthly_quota integer,
                        usage_count integer not null default 0,
                        max_concurrency integer not null default 1,
                        cooldown_until text,
                        last_error text,
                        last_used_at text,
                        metadata_json text,
                        created_at text not null,
                        updated_at text not null
                    );
                    create index if not exists idx_vendor_api_keys_provider_status
                        on vendor_api_keys(provider, status);

                    create table if not exists vendor_invocations (
                        id text primary key,
                        provider text not null,
                        model text,
                        capability_key text not null,
                        api_type text,
                        execution_mode text,
                        status text not null,
                        success integer not null default 0,
                        vendor_task_id text,
                        request_json text,
                        response_json text,
                        error_json text,
                        raw_json text,
                        created_at text not null,
                        updated_at text not null
                    );
                    create index if not exists idx_vendor_invocations_provider_status
                        on vendor_invocations(provider, status);

                    create table if not exists vendor_usage_logs (
                        id text primary key,
                        invocation_id text,
                        provider text not null,
                        model text,
                        key_id text,
                        status text not null,
                        error_code text,
                        latency_ms integer,
                        created_at text not null
                    );
                    """
                )
                conn.commit()


def _row_to_key(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "alias": row["alias"],
        "key": row["key_value"],
        "secret": row["secret_value"],
        "model": row["model"],
        "status": row["status"],
        "daily_quota": row["daily_quota"],
        "monthly_quota": row["monthly_quota"],
        "usage_count": int(row["usage_count"] or 0),
        "max_concurrency": int(row["max_concurrency"] or 1),
        "cooldown_until": row["cooldown_until"],
        "last_error": row["last_error"],
        "last_used_at": row["last_used_at"],
        "metadata": _load_json(row["metadata_json"]) or {},
    }


def _row_to_invocation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "model": row["model"],
        "capability_key": row["capability_key"],
        "api_type": row["api_type"],
        "execution_mode": row["execution_mode"],
        "status": row["status"],
        "success": bool(row["success"]),
        "vendor_task_id": row["vendor_task_id"],
        "request": _load_json(row["request_json"]) or {},
        "response": _load_json(row["response_json"]) or {},
        "error": _load_json(row["error_json"]),
        "raw": _load_json(row["raw_json"]) or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _dump_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


vendor_storage = VendorStorage()
