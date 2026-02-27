"""Local sqlite state store for desktop agent."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                create table if not exists task_history (
                    task_id text primary key,
                    status text not null,
                    message text,
                    request_payload text,
                    result_payload text,
                    created_at text not null,
                    updated_at text not null
                );
                create table if not exists sync_snapshot (
                    id integer primary key check (id = 1),
                    manifest_version text,
                    snapshot_payload text,
                    updated_at text not null
                );
                create table if not exists alerts_cache (
                    id integer primary key autoincrement,
                    alert_type text not null,
                    message text not null,
                    payload text,
                    created_at text not null
                );
                create table if not exists update_state (
                    id integer primary key check (id = 1),
                    current_version text,
                    target_version text,
                    status text,
                    payload text,
                    updated_at text not null
                );
                """
            )
            conn.commit()

    def upsert_task(
        self,
        *,
        task_id: str,
        status: str,
        message: str | None = None,
        request_payload: dict[str, Any] | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                insert into task_history (task_id, status, message, request_payload, result_payload, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(task_id) do update set
                    status=excluded.status,
                    message=excluded.message,
                    request_payload=excluded.request_payload,
                    result_payload=excluded.result_payload,
                    updated_at=excluded.updated_at
                """,
                (
                    task_id,
                    status,
                    message,
                    json.dumps(request_payload, ensure_ascii=True) if request_payload is not None else None,
                    json.dumps(result_payload, ensure_ascii=True) if result_payload is not None else None,
                    now,
                    now,
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("select * from task_history where task_id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def list_tasks(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "select * from task_history order by updated_at desc limit ?",
                (max(1, min(2000, limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_snapshot(self, manifest_version: str, snapshot_payload: dict[str, Any]) -> None:
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                insert into sync_snapshot (id, manifest_version, snapshot_payload, updated_at)
                values (1, ?, ?, ?)
                on conflict(id) do update set
                    manifest_version=excluded.manifest_version,
                    snapshot_payload=excluded.snapshot_payload,
                    updated_at=excluded.updated_at
                """,
                (manifest_version, json.dumps(snapshot_payload, ensure_ascii=True), now),
            )
            conn.commit()

    def get_snapshot(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("select * from sync_snapshot where id = 1").fetchone()
        if not row:
            return None
        data = dict(row)
        raw_payload = data.get("snapshot_payload")
        if isinstance(raw_payload, str) and raw_payload.strip():
            try:
                data["snapshot_payload"] = json.loads(raw_payload)
            except json.JSONDecodeError:
                pass
        return data

    def set_update_state(
        self,
        *,
        current_version: str,
        target_version: str | None,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                insert into update_state (id, current_version, target_version, status, payload, updated_at)
                values (1, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    current_version=excluded.current_version,
                    target_version=excluded.target_version,
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    current_version,
                    target_version,
                    status,
                    json.dumps(payload, ensure_ascii=True) if payload is not None else None,
                    now,
                ),
            )
            conn.commit()

    def get_update_state(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("select * from update_state where id = 1").fetchone()
        if not row:
            return None
        data = dict(row)
        raw_payload = data.get("payload")
        if isinstance(raw_payload, str) and raw_payload.strip():
            try:
                data["payload"] = json.loads(raw_payload)
            except json.JSONDecodeError:
                pass
        return data
