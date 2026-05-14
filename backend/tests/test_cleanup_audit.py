from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_cleanup_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_cleanup_candidates.py"
    spec = importlib.util.spec_from_file_location("audit_cleanup_candidates", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_audit_repo_files_marks_only_regenerable_artifacts(tmp_path: Path) -> None:
    module = _load_cleanup_module()
    root = tmp_path / "repo"
    root.mkdir()
    dist_file = root / "podi-eval-web" / "dist" / "index.html"
    dist_file.parent.mkdir(parents=True)
    dist_file.write_text("<div>build</div>", encoding="utf-8")
    pycache_file = root / "backend" / "app" / "__pycache__" / "mod.pyc"
    pycache_file.parent.mkdir(parents=True)
    pycache_file.write_bytes(b"cache")
    log_file = root / "console-admin.log"
    log_file.write_text("log", encoding="utf-8")
    node_file = root / "podi-eval-web" / "node_modules" / "pkg" / "index.js"
    node_file.parent.mkdir(parents=True)
    node_file.write_text("dependency", encoding="utf-8")

    items = module.audit_repo_files(root)
    by_path = {item.path_or_id: item for item in items}

    assert "podi-eval-web/dist" in by_path
    assert "backend/app/__pycache__" in by_path
    assert "console-admin.log" in by_path
    assert not any("node_modules" in item.path_or_id for item in items)
    assert {by_path["podi-eval-web/dist"].action, by_path["backend/app/__pycache__"].action} == {
        "safe-delete-local"
    }


def test_object_key_from_url_respects_known_domain_and_root_prefix() -> None:
    module = _load_cleanup_module()
    key = module._object_key_from_url(
        "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/a.png",
        known_domains=["podiaidesign.oss-cn-hangzhou.aliyuncs.com"],
        root_prefix="test",
    )

    assert key == "test/abilities/a.png"
    assert (
        module._object_key_from_url(
            "https://evil.example.com/test/abilities/a.png",
            known_domains=["podiaidesign.oss-cn-hangzhou.aliyuncs.com"],
            root_prefix="test",
        )
        is None
    )


def test_summarize_oss_candidates_groups_by_prefix_and_month() -> None:
    module = _load_cleanup_module()
    groups = module.summarize_oss_candidates(
        [
            {
                "object_key": "test/eval/a.png",
                "size_bytes": 100,
                "last_modified": "2026-04-01T00:00:00+00:00",
            },
            {
                "object_key": "test/eval/b.png",
                "size_bytes": 200,
                "last_modified": "2026-04-02T00:00:00+00:00",
            },
            {
                "object_key": "test/tmp/c.png",
                "size_bytes": 300,
                "last_modified": "2026-03-02T00:00:00+00:00",
            },
        ]
    )

    by_key = {(row["prefix_group"], row["month"]): row for row in groups}
    assert by_key[("test/eval", "2026-04")]["count"] == 2
    assert by_key[("test/eval", "2026-04")]["size_bytes"] == 300
    assert by_key[("test/tmp", "2026-03")]["sample_keys"] == ["test/tmp/c.png"]


def test_build_oss_deletion_review_plan_is_review_only_and_batched() -> None:
    module = _load_cleanup_module()
    plan = module.build_oss_deletion_review_plan(
        [
            {
                "object_key": "test/eval/b.png",
                "size_bytes": 20,
                "last_modified": "2026-04-02T00:00:00+00:00",
            },
            {
                "object_key": "test/eval/a.png",
                "size_bytes": 10,
                "last_modified": "2026-04-01T00:00:00+00:00",
            },
            {
                "object_key": "test/tmp/c.png",
                "size_bytes": 30,
                "last_modified": "2026-04-03T00:00:00+00:00",
            },
        ],
        batch_size=2,
    )

    assert [row["object_key"] for row in plan] == ["test/eval/a.png", "test/eval/b.png", "test/tmp/c.png"]
    assert [row["proposed_batch"] for row in plan] == [1, 1, 2]
    assert {row["decision"] for row in plan} == {"review_required"}
    assert {row["delete_allowed"] for row in plan} == {"no"}
    assert (
        module._object_key_from_url(
            "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/uploads/a.png",
            known_domains=["podiaidesign.oss-cn-hangzhou.aliyuncs.com"],
            root_prefix="test",
        )
        is None
    )
