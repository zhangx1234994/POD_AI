import json
from pathlib import Path
import subprocess

from app.services.product_3d_render_video import Product3DRenderVideoService
from scripts.stage_product_3d_scene_assets import (
    build_staging_manifest,
    collect_scene_asset_candidates,
    select_scene_asset_candidates,
)


def test_product_3d_scene_asset_staging_selects_retail_candidates() -> None:
    catalog = Product3DRenderVideoService().catalog()

    candidates = collect_scene_asset_candidates(catalog)
    selected = select_scene_asset_candidates(candidates, scene_presets=["retail_shelf"])
    by_id = {item["assetId"]: item for item in selected}

    assert "wooden_display_shelves_01" in by_id
    assert "steel_frame_shelves_01" in by_id
    assert "Metal037" in by_id
    assert by_id["wooden_display_shelves_01"]["provider"] == "Poly Haven"
    assert by_id["wooden_display_shelves_01"]["license"] == "CC0"
    assert "retail_shelf" in by_id["wooden_display_shelves_01"]["targetScenePresets"]
    assert any(
        context["type"] == "scenePreset" and context["scenePreset"] == "retail_shelf"
        for context in by_id["wooden_display_shelves_01"]["catalogContexts"]
    )
    assert by_id["steel_frame_shelves_01"]["provider"] == "Poly Haven"
    assert by_id["steel_frame_shelves_01"]["licenseReview"]["commercialUse"] is True
    assert "retail_shelf" in by_id["steel_frame_shelves_01"]["targetScenePresets"]
    assert any(
        context["type"] == "scenePreset" and context["scenePreset"] == "retail_shelf"
        for context in by_id["steel_frame_shelves_01"]["catalogContexts"]
    )


def test_product_3d_scene_asset_staging_selects_tabletop_candidates() -> None:
    catalog = Product3DRenderVideoService().catalog()

    candidates = collect_scene_asset_candidates(catalog)
    selected = select_scene_asset_candidates(candidates, scene_presets=["desktop_lifestyle", "gift_table"])
    by_id = {item["assetId"]: item for item in selected}

    assert "industrial_coffee_table" in by_id
    table = by_id["industrial_coffee_table"]
    assert table["provider"] == "Poly Haven"
    assert table["license"] == "CC0"
    assert {"desktop_lifestyle", "gift_table"}.issubset(set(table["targetScenePresets"]))
    assert table["workerReadiness"]["highFidelityWorker"] == "requires_asset_import_test"
    assert any(
        context["type"] == "scenePreset" and context["scenePreset"] == "desktop_lifestyle"
        for context in table["catalogContexts"]
    )
    assert any(
        context["type"] == "scenePreset" and context["scenePreset"] == "gift_table"
        for context in table["catalogContexts"]
    )


def test_product_3d_scene_asset_staging_manifest_is_safe_by_default(tmp_path: Path) -> None:
    catalog = Product3DRenderVideoService().catalog()
    candidates = collect_scene_asset_candidates(catalog)
    selected = select_scene_asset_candidates(candidates, asset_ids=["wooden_display_shelves_01"])

    manifest = build_staging_manifest(
        selected,
        enrich_online=False,
        download=False,
        download_includes=False,
        preferred_resolution="1k",
        max_download_bytes=1024,
        output_dir=tmp_path,
    )

    assert manifest["policy"]["executionInput"] is False
    assert manifest["policy"]["largeVendorAssetsBundledInRepo"] is False
    assert manifest["count"] == 1
    item = manifest["items"][0]
    assert item["assetId"] == "wooden_display_shelves_01"
    assert item["providerApi"] == {"status": "skipped", "reason": "enrich_online_disabled"}
    assert item["staging"]["status"] == "manifest_only"
    assert item["staging"]["downloadedFiles"] == []
    assert item["staging"]["reason"] == "download_not_requested"
    assert "download_hash_recorded" in manifest["policy"]["readyGate"]


def test_product_3d_scene_asset_staging_can_download_package_includes(tmp_path: Path) -> None:
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    class FakeStream:
        def __init__(self, payload: bytes):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):
            yield self.payload

    class FakeClient:
        def get(self, url: str):
            if url.endswith("/info/demo_scene"):
                return FakeResponse(
                    {
                        "name": "Demo Scene",
                        "type": 2,
                        "categories": ["furniture"],
                        "tags": ["shelf"],
                        "authors": {"PODI Test": "All"},
                        "polycount": 128,
                    }
                )
            if url.endswith("/files/demo_scene"):
                return FakeResponse(
                    {
                        "gltf": {
                            "1k": {
                                "gltf": {
                                    "url": "https://assets.example/demo_scene.gltf",
                                    "md5": "provider-main-md5",
                                    "size": 12,
                                    "include": {
                                        "demo_scene.bin": {
                                            "url": "https://assets.example/demo_scene.bin",
                                            "md5": "provider-bin-md5",
                                            "size": 10,
                                        },
                                        "textures/demo_scene_diff_1k.jpg": {
                                            "url": "https://assets.example/demo_scene_diff_1k.jpg",
                                            "md5": "provider-texture-md5",
                                            "size": 9,
                                        },
                                    },
                                }
                            }
                        }
                    }
                )
            raise AssertionError(url)

        def stream(self, method: str, url: str):
            assert method == "GET"
            payloads = {
                "https://assets.example/demo_scene.gltf": (
                    b'{"asset":{"version":"2.0"},"buffers":[{"uri":"demo_scene.bin"}],'
                    b'"images":[{"uri":"textures/demo_scene_diff_1k.jpg"}]}'
                ),
                "https://assets.example/demo_scene.bin": b"bincontent",
                "https://assets.example/demo_scene_diff_1k.jpg": b"jpgbytes",
            }
            return FakeStream(payloads[url])

    manifest = build_staging_manifest(
        [
            {
                "assetId": "demo_scene",
                "provider": "Poly Haven",
                "sourceUrl": "https://polyhaven.com/a/demo_scene",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "targetScenePresets": ["retail_shelf"],
            }
        ],
        enrich_online=True,
        download=True,
        download_includes=True,
        preferred_resolution="1k",
        max_download_bytes=1024,
        output_dir=tmp_path,
        client=FakeClient(),
    )

    item = manifest["items"][0]
    assert item["providerApi"]["status"] == "ok"
    assert item["staging"]["status"] == "downloaded_package"
    assert item["staging"]["reason"] == "main_file_and_includes_downloaded"
    assert len(item["staging"]["downloadedFiles"]) == 1
    assert len(item["staging"]["downloadedIncludes"]) == 2
    assert (tmp_path / "assets" / "poly_haven" / "demo_scene" / "demo_scene.gltf").exists()
    assert (tmp_path / "assets" / "poly_haven" / "demo_scene" / "demo_scene.bin").exists()
    assert (tmp_path / "assets" / "poly_haven" / "demo_scene" / "textures" / "demo_scene_diff_1k.jpg").exists()
    assert item["staging"]["packageValidation"]["status"] == "passed"
    assert item["staging"]["packageValidation"]["checks"]["hashesRecorded"] is True
    assert item["staging"]["packageValidation"]["checks"]["gltfReferencesPresent"] is True
    assert item["staging"]["packageValidation"]["expectedReferenceCount"] == 2


def test_product_3d_scene_asset_staging_records_three_import_smoke(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    class FakeStream:
        def __init__(self, payload: bytes):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):
            yield self.payload

    class FakeClient:
        def get(self, url: str):
            if url.endswith("/info/demo_import_scene"):
                return FakeResponse({"name": "Demo Import Scene", "type": 2, "polycount": 256})
            if url.endswith("/files/demo_import_scene"):
                return FakeResponse(
                    {
                        "gltf": {
                            "1k": {
                                "gltf": {
                                    "url": "https://assets.example/demo_import_scene.gltf",
                                    "md5": "provider-main-md5",
                                    "size": 12,
                                    "include": {
                                        "demo_import_scene.bin": {
                                            "url": "https://assets.example/demo_import_scene.bin",
                                            "md5": "provider-bin-md5",
                                            "size": 10,
                                        }
                                    },
                                }
                            }
                        }
                    }
                )
            raise AssertionError(url)

        def stream(self, method: str, url: str):
            assert method == "GET"
            payloads = {
                "https://assets.example/demo_import_scene.gltf": (
                    b'{"asset":{"version":"2.0"},"buffers":[{"uri":"demo_import_scene.bin"}],'
                    b'"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],'
                    b'"nodes":[{"mesh":0}],"scenes":[{"nodes":[0]}],"scene":0}'
                ),
                "https://assets.example/demo_import_scene.bin": b"bincontent",
            }
            return FakeStream(payloads[url])

    three_root = tmp_path / "three-root"
    (three_root / "node_modules" / "three").mkdir(parents=True)
    (three_root / "node_modules" / "three" / "package.json").write_text("{}", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        calls.append(
            {
                "cmd": cmd,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
                "check": check,
            }
        )
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "status": "passed",
                    "loader": "three.GLTFLoader",
                    "meshCount": 3,
                    "materialCount": 2,
                    "checks": {"parsedByThree": True, "meshDetected": True},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("scripts.stage_product_3d_scene_assets.subprocess.run", fake_run)

    manifest = build_staging_manifest(
        [
            {
                "assetId": "demo_import_scene",
                "provider": "Poly Haven",
                "sourceUrl": "https://polyhaven.com/a/demo_import_scene",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "targetScenePresets": ["studio_turntable"],
            }
        ],
        enrich_online=True,
        download=True,
        download_includes=True,
        import_smoke=True,
        preferred_resolution="1k",
        max_download_bytes=1024,
        output_dir=tmp_path,
        three_root=three_root,
        client=FakeClient(),
    )

    item = manifest["items"][0]
    assert item["staging"]["packageValidation"]["status"] == "passed"
    assert item["staging"]["importSmoke"]["status"] == "passed"
    assert item["staging"]["importSmoke"]["loader"] == "three.GLTFLoader"
    assert item["staging"]["importSmoke"]["meshCount"] == 3
    assert item["staging"]["importSmoke"]["checks"]["parsedByThree"] is True
    assert calls
    assert calls[0]["cwd"] == three_root.resolve()
    assert calls[0]["cmd"][0] == "node"
