#!/usr/bin/env python3
"""Build a controlled staging manifest for 3D render-video scene assets."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.product_3d_render_video import Product3DRenderVideoService


PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_THREE_ROOT = PROJECT_ROOT / "podi-eval-web"
DEFAULT_OUTPUT_ROOT = Path("deliverables") / "product_3d_scene_assets"
POLYHAVEN_API_BASE = "https://api.polyhaven.com"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_slug() -> str:
    return _now().strftime("%Y%m%d_%H%M%S")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_filter(values: list[str] | None) -> set[str]:
    return {_clean_text(item).lower() for item in values or [] if _clean_text(item)}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _asset_key(provider: str, asset_id: str) -> str:
    return f"{provider.strip().lower()}::{asset_id.strip().lower()}"


def _source_candidate_record(candidate: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(candidate)
    provider = _clean_text(item.get("provider")) or _clean_text(source.get("provider")) or "unknown"
    item["provider"] = provider
    item["assetId"] = _clean_text(item.get("assetId"))
    item["sourceUrl"] = _clean_text(item.get("sourceUrl") or item.get("url"))
    item["license"] = _clean_text(item.get("license")) or _clean_text(source.get("license")) or "to_be_verified"
    item["licenseUrl"] = _clean_text(item.get("licenseUrl")) or _clean_text(source.get("licenseUrl"))
    item["catalogContexts"] = [
        {
            "type": "sourceCatalog",
            "provider": _clean_text(source.get("provider")),
            "sourceType": _clean_text(source.get("sourceType")),
            "commercialUse": bool(source.get("commercialUse")),
            "ingestStatus": _clean_text(source.get("ingestStatus")),
        }
    ]
    return item


def _scene_candidate_record(candidate: dict[str, Any], *, scene: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(candidate)
    provider = _clean_text(item.get("provider")) or "unknown"
    scene_key = _clean_text(scene.get("key"))
    item["provider"] = provider
    item["assetId"] = _clean_text(item.get("assetId"))
    item["sourceUrl"] = _clean_text(item.get("sourceUrl") or item.get("url"))
    item["catalogContexts"] = [
        {
            "type": "scenePreset",
            "scenePreset": scene_key,
            "sceneAssetId": _clean_text((scene.get("asset") or {}).get("assetId") if isinstance(scene.get("asset"), dict) else None),
            "renderFidelity": _clean_text((scene.get("asset") or {}).get("renderFidelity") if isinstance(scene.get("asset"), dict) else None),
        }
    ]
    presets = item.get("targetScenePresets")
    if not isinstance(presets, list):
        presets = []
    if scene_key and scene_key not in presets:
        presets.append(scene_key)
    item["targetScenePresets"] = presets
    return item


def collect_scene_asset_candidates(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge asset-level candidates from source catalog and scene presets."""
    merged: dict[str, dict[str, Any]] = {}

    for source in catalog.get("sceneAssetSources") or []:
        if not isinstance(source, dict):
            continue
        for candidate in source.get("candidateAssets") or []:
            if not isinstance(candidate, dict):
                continue
            item = _source_candidate_record(candidate, source=source)
            asset_id = _clean_text(item.get("assetId"))
            if not asset_id:
                continue
            key = _asset_key(_clean_text(item.get("provider")), asset_id)
            merged[key] = item

    for scene in catalog.get("scenePresets") or []:
        if not isinstance(scene, dict):
            continue
        asset = scene.get("asset") if isinstance(scene.get("asset"), dict) else {}
        for candidate in asset.get("externalCandidates") or []:
            if not isinstance(candidate, dict):
                continue
            item = _scene_candidate_record(candidate, scene=scene)
            asset_id = _clean_text(item.get("assetId"))
            if not asset_id:
                continue
            key = _asset_key(_clean_text(item.get("provider")), asset_id)
            if key not in merged:
                merged[key] = item
                continue
            existing = merged[key]
            existing_contexts = existing.setdefault("catalogContexts", [])
            existing_contexts.extend(item.get("catalogContexts") or [])
            existing_presets = set(existing.get("targetScenePresets") or [])
            existing_presets.update(item.get("targetScenePresets") or [])
            existing["targetScenePresets"] = sorted(existing_presets)
            if not _clean_text(existing.get("kind")) and _clean_text(item.get("kind")):
                existing["kind"] = item.get("kind")
            if not _clean_text(existing.get("use")) and _clean_text(item.get("use")):
                existing["use"] = item.get("use")

    return sorted(merged.values(), key=lambda item: (_clean_text(item.get("provider")).lower(), _clean_text(item.get("assetId")).lower()))


def select_scene_asset_candidates(
    candidates: list[dict[str, Any]],
    *,
    asset_ids: list[str] | None = None,
    providers: list[str] | None = None,
    scene_presets: list[str] | None = None,
) -> list[dict[str, Any]]:
    asset_filter = _normalize_filter(asset_ids)
    provider_filter = _normalize_filter(providers)
    scene_filter = _normalize_filter(scene_presets)
    selected: list[dict[str, Any]] = []
    for item in candidates:
        if asset_filter and _clean_text(item.get("assetId")).lower() not in asset_filter:
            continue
        if provider_filter and _clean_text(item.get("provider")).lower() not in provider_filter:
            continue
        if scene_filter:
            presets = {_clean_text(value).lower() for value in item.get("targetScenePresets") or []}
            contexts = {
                _clean_text(context.get("scenePreset")).lower()
                for context in item.get("catalogContexts") or []
                if isinstance(context, dict)
            }
            if not scene_filter.intersection(presets | contexts):
                continue
        selected.append(item)
    return selected


def _resolution_rank(value: str) -> int:
    text = _clean_text(value).lower()
    if text.endswith("k") and text[:-1].isdigit():
        return int(text[:-1])
    if text.isdigit():
        return int(text)
    return 999


def _flatten_polyhaven_downloads(files_payload: dict[str, Any], *, preferred_resolution: str) -> list[dict[str, Any]]:
    downloads: list[dict[str, Any]] = []
    for asset_format in ("gltf", "blend", "fbx", "usd"):
        variants = files_payload.get(asset_format)
        if not isinstance(variants, dict):
            continue
        resolutions = sorted([_clean_text(item) for item in variants.keys()], key=_resolution_rank)
        if not resolutions:
            continue
        resolution = preferred_resolution if preferred_resolution in variants else resolutions[0]
        format_map = variants.get(resolution)
        if not isinstance(format_map, dict):
            continue
        for extension, file_info in format_map.items():
            if not isinstance(file_info, dict) or not _clean_text(file_info.get("url")):
                continue
            includes = file_info.get("include") if isinstance(file_info.get("include"), dict) else {}
            include_bytes = sum(int(item.get("size") or 0) for item in includes.values() if isinstance(item, dict))
            downloads.append(
                {
                    "format": asset_format,
                    "extension": _clean_text(extension),
                    "resolution": resolution,
                    "url": _clean_text(file_info.get("url")),
                    "md5": _clean_text(file_info.get("md5")),
                    "sizeBytes": int(file_info.get("size") or 0),
                    "includeCount": len(includes),
                    "includeBytes": include_bytes,
                    "totalBytes": int(file_info.get("size") or 0) + include_bytes,
                    "includes": [
                        {
                            "path": path,
                            "url": _clean_text(info.get("url")),
                            "md5": _clean_text(info.get("md5")),
                            "sizeBytes": int(info.get("size") or 0),
                        }
                        for path, info in includes.items()
                        if isinstance(info, dict)
                    ],
                }
            )
    return downloads


def enrich_candidate(candidate: dict[str, Any], *, client: httpx.Client, preferred_resolution: str) -> dict[str, Any]:
    provider = _clean_text(candidate.get("provider")).lower()
    asset_id = _clean_text(candidate.get("assetId"))
    if provider != "poly haven":
        return {
            "status": "skipped",
            "reason": "provider_api_not_configured",
            "provider": candidate.get("provider"),
        }
    try:
        info = client.get(f"{POLYHAVEN_API_BASE}/info/{asset_id}")
        info.raise_for_status()
        files = client.get(f"{POLYHAVEN_API_BASE}/files/{asset_id}")
        files.raise_for_status()
        info_payload = info.json()
        files_payload = files.json()
    except Exception as exc:
        return {
            "status": "failed",
            "provider": "Poly Haven",
            "error": str(exc),
        }
    return {
        "status": "ok",
        "provider": "Poly Haven",
        "infoUrl": f"{POLYHAVEN_API_BASE}/info/{asset_id}",
        "filesUrl": f"{POLYHAVEN_API_BASE}/files/{asset_id}",
        "name": info_payload.get("name"),
        "type": info_payload.get("type"),
        "categories": info_payload.get("categories") or [],
        "tags": info_payload.get("tags") or [],
        "authors": info_payload.get("authors") or {},
        "datePublished": info_payload.get("date_published"),
        "polycount": info_payload.get("polycount"),
        "maxResolution": info_payload.get("max_resolution"),
        "downloadOptions": _flatten_polyhaven_downloads(files_payload, preferred_resolution=preferred_resolution),
    }


def _filename_from_url(url: str, fallback: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name or fallback


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_file(client: httpx.Client, url: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return {
        "path": str(target),
        "sha256": _sha256_file(target),
        "sizeBytes": target.stat().st_size,
    }


def _safe_include_path(path: str) -> Path:
    include_path = Path(path)
    if include_path.is_absolute() or ".." in include_path.parts:
        return Path(include_path.name)
    return include_path


def _local_reference_path(base_dir: Path, uri: Any) -> Path | None:
    text = _clean_text(uri)
    if not text or text.startswith("data:"):
        return None
    parsed = urlparse(text)
    if parsed.scheme and parsed.scheme not in {"file"}:
        return None
    return base_dir / _safe_include_path(unquote(parsed.path or text))


def validate_staged_package(entry: dict[str, Any]) -> dict[str, Any]:
    staging = entry.get("staging") if isinstance(entry.get("staging"), dict) else {}
    downloaded_files = staging.get("downloadedFiles") if isinstance(staging.get("downloadedFiles"), list) else []
    downloaded_includes = staging.get("downloadedIncludes") if isinstance(staging.get("downloadedIncludes"), list) else []
    all_downloads = [item for item in [*downloaded_files, *downloaded_includes] if isinstance(item, dict)]
    if not downloaded_files:
        return {
            "status": "not_downloaded",
            "checks": {
                "hashesRecorded": False,
                "gltfReferencesPresent": False,
            },
            "missingReferences": [],
        }
    hashes_recorded = all(_clean_text(item.get("sha256")) and int(item.get("sizeBytes") or 0) > 0 for item in all_downloads)
    main_path = Path(_clean_text(downloaded_files[0].get("path")))
    if main_path.suffix.lower() != ".gltf":
        return {
            "status": "not_applicable",
            "reason": "main_file_is_not_gltf",
            "mainFile": str(main_path),
            "checks": {
                "hashesRecorded": hashes_recorded,
                "gltfReferencesPresent": None,
            },
            "missingReferences": [],
        }
    try:
        gltf = json.loads(main_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "failed",
            "reason": "gltf_json_parse_failed",
            "error": str(exc),
            "mainFile": str(main_path),
            "checks": {
                "hashesRecorded": hashes_recorded,
                "gltfReferencesPresent": False,
            },
            "missingReferences": [],
        }
    expected_references: list[dict[str, str]] = []
    for section, kind in (("buffers", "buffer"), ("images", "image")):
        items = gltf.get(section) if isinstance(gltf.get(section), list) else []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            reference_path = _local_reference_path(main_path.parent, item.get("uri"))
            if reference_path is None:
                continue
            expected_references.append(
                {
                    "kind": kind,
                    "index": str(index),
                    "uri": _clean_text(item.get("uri")),
                    "path": str(reference_path),
                }
            )
    missing_references = [item for item in expected_references if not Path(item["path"]).exists()]
    status = "passed" if hashes_recorded and not missing_references else "failed"
    return {
        "status": status,
        "mainFile": str(main_path),
        "checks": {
            "hashesRecorded": hashes_recorded,
            "gltfReferencesPresent": not missing_references,
        },
        "expectedReferenceCount": len(expected_references),
        "missingReferences": missing_references,
    }


def _parse_smoke_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed([item.strip() for item in stdout.splitlines() if item.strip()]):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def run_three_gltf_import_smoke(
    main_path: Path,
    *,
    three_root: Path | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Use the eval-web Three.js dependency to prove a staged GLTF can be imported."""
    resolved_path = main_path.expanduser().resolve()
    if not resolved_path.exists():
        return {
            "status": "failed",
            "reason": "main_file_missing",
            "mainFile": str(resolved_path),
        }
    if resolved_path.suffix.lower() != ".gltf":
        return {
            "status": "not_applicable",
            "reason": "main_file_is_not_gltf",
            "mainFile": str(resolved_path),
        }

    resolved_three_root = (three_root or DEFAULT_THREE_ROOT).expanduser().resolve()
    if not (resolved_three_root / "node_modules" / "three" / "package.json").exists():
        return {
            "status": "skipped",
            "reason": "three_dependency_not_installed",
            "mainFile": str(resolved_path),
            "threeRoot": str(resolved_three_root),
        }

    script = r"""
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

if (typeof globalThis.self === 'undefined') {
  globalThis.self = globalThis;
}

if (!globalThis.URL.createObjectURL) {
  globalThis.URL.createObjectURL = () => 'blob:podi-gltf-import-smoke';
}

if (!globalThis.URL.revokeObjectURL) {
  globalThis.URL.revokeObjectURL = () => {};
}

if (typeof globalThis.ProgressEvent === 'undefined') {
  globalThis.ProgressEvent = class ProgressEvent extends Event {
    constructor(type, options = {}) {
      super(type);
      this.lengthComputable = Boolean(options.lengthComputable);
      this.loaded = Number(options.loaded || 0);
      this.total = Number(options.total || 0);
    }
  };
}

if (typeof globalThis.createImageBitmap === 'undefined') {
  globalThis.createImageBitmap = async () => ({ width: 1, height: 1, close() {} });
}

const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = typeof input === 'string' ? input : input?.url;
  if (url && url.startsWith('file:')) {
    const data = await readFile(fileURLToPath(url));
    return new Response(data);
  }
  return nativeFetch(input, init);
};

const mainFile = process.argv[1];
const baseDir = dirname(mainFile);
const baseUrl = pathToFileURL(`${baseDir}/`).href;
const manager = new THREE.LoadingManager();
manager.setURLModifier((url) => {
  if (/^(https?:|data:|blob:|file:)/i.test(url)) return url;
  return pathToFileURL(resolve(baseDir, decodeURIComponent(url))).href;
});

const loader = new GLTFLoader(manager);
const buffer = await readFile(mainFile);
const arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
const gltf = await new Promise((accept, reject) => {
  loader.parse(arrayBuffer, baseUrl, accept, reject);
});

let nodeCount = 0;
let meshCount = 0;
let cameraCount = 0;
let lightCount = 0;
const materialIds = new Set();
const textureIds = new Set();
gltf.scene.traverse((object) => {
  nodeCount += 1;
  if (object.isMesh) {
    meshCount += 1;
    const materials = Array.isArray(object.material) ? object.material : [object.material].filter(Boolean);
    for (const material of materials) {
      materialIds.add(material.uuid);
      for (const value of Object.values(material)) {
        if (value && value.isTexture) textureIds.add(value.uuid);
      }
    }
  }
  if (object.isCamera) cameraCount += 1;
  if (object.isLight) lightCount += 1;
});

const payload = {
  status: meshCount > 0 ? 'passed' : 'failed',
  reason: meshCount > 0 ? undefined : 'no_mesh_detected',
  loader: 'three.GLTFLoader',
  textureDecode: 'mocked_createImageBitmap_for_node_smoke',
  mainFile,
  sceneChildren: gltf.scene.children.length,
  nodeCount,
  meshCount,
  materialCount: materialIds.size,
  textureCount: textureIds.size,
  animationCount: gltf.animations?.length || 0,
  cameraCount,
  lightCount,
  checks: {
    parsedByThree: true,
    meshDetected: meshCount > 0,
    localReferencesResolvable: true
  }
};
console.log(JSON.stringify(payload));
"""
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(resolved_path)],
            cwd=resolved_three_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "status": "skipped",
            "reason": "node_not_available",
            "mainFile": str(resolved_path),
            "threeRoot": str(resolved_three_root),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "reason": "three_import_timeout",
            "mainFile": str(resolved_path),
            "threeRoot": str(resolved_three_root),
            "timeoutSeconds": timeout_seconds,
            "stdout": (exc.stdout or "")[-2000:],
            "stderr": (exc.stderr or "")[-2000:],
        }

    parsed = _parse_smoke_stdout(result.stdout)
    if result.returncode != 0 or not parsed:
        return {
            "status": "failed",
            "reason": "three_import_failed",
            "mainFile": str(resolved_path),
            "threeRoot": str(resolved_three_root),
            "exitCode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }
    parsed["mainFile"] = str(resolved_path)
    parsed["threeRoot"] = str(resolved_three_root)
    if result.stderr.strip():
        parsed["stderr"] = result.stderr[-2000:]
    return parsed


def run_staged_import_smoke(entry: dict[str, Any], *, three_root: Path | None = None) -> dict[str, Any]:
    staging = entry.get("staging") if isinstance(entry.get("staging"), dict) else {}
    downloaded_files = staging.get("downloadedFiles") if isinstance(staging.get("downloadedFiles"), list) else []
    if not downloaded_files:
        return {
            "status": "not_downloaded",
            "reason": "main_file_not_downloaded",
        }
    package_validation = staging.get("packageValidation") if isinstance(staging.get("packageValidation"), dict) else {}
    if package_validation.get("status") not in {"passed", "not_applicable"}:
        return {
            "status": "skipped",
            "reason": "package_validation_not_passed",
            "packageValidationStatus": package_validation.get("status"),
        }
    main_path = Path(_clean_text(downloaded_files[0].get("path")))
    return run_three_gltf_import_smoke(main_path, three_root=three_root)


def _download_plan(entry: dict[str, Any]) -> dict[str, Any] | None:
    options = (
        ((entry.get("providerApi") or {}).get("downloadOptions") or [])
        if isinstance(entry.get("providerApi"), dict)
        else []
    )
    if not isinstance(options, list) or not options:
        return None
    for preferred_format in ("gltf", "blend", "fbx", "usd"):
        for option in options:
            if isinstance(option, dict) and option.get("format") == preferred_format and _clean_text(option.get("url")):
                return option
    return next((option for option in options if isinstance(option, dict) and _clean_text(option.get("url"))), None)


def build_staging_manifest(
    candidates: list[dict[str, Any]],
    *,
    enrich_online: bool,
    download: bool,
    download_includes: bool,
    preferred_resolution: str,
    max_download_bytes: int,
    output_dir: Path,
    import_smoke: bool = False,
    three_root: Path | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    http_client = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True)
    try:
        entries: list[dict[str, Any]] = []
        for candidate in candidates:
            entry = {
                "assetId": candidate.get("assetId"),
                "provider": candidate.get("provider"),
                "sourceUrl": candidate.get("sourceUrl") or candidate.get("url"),
                "license": candidate.get("license"),
                "licenseUrl": candidate.get("licenseUrl"),
                "kind": candidate.get("kind"),
                "use": candidate.get("use"),
                "targetScenePresets": candidate.get("targetScenePresets") or [],
                "catalogContexts": candidate.get("catalogContexts") or [],
                "ingestStage": candidate.get("ingestStage"),
                "requiredValidation": candidate.get("requiredValidation") or [],
                "workerReadiness": candidate.get("workerReadiness") or {},
                "providerApi": {"status": "skipped", "reason": "enrich_online_disabled"},
                "staging": {
                    "downloadEnabled": download,
                    "downloadIncludes": download_includes,
                    "status": "manifest_only",
                    "downloadedFiles": [],
                    "downloadedIncludes": [],
                    "selectedDownload": None,
                    "packageValidation": {"status": "not_downloaded"},
                    "importSmoke": {"status": "not_requested"},
                    "reason": "download_not_requested" if not download else None,
                },
            }
            if enrich_online:
                entry["providerApi"] = enrich_candidate(candidate, client=http_client, preferred_resolution=preferred_resolution)
            selected_download = _download_plan(entry)
            entry["staging"]["selectedDownload"] = selected_download
            if download:
                if not selected_download:
                    entry["staging"]["status"] = "skipped"
                    entry["staging"]["reason"] = "no_direct_download_option"
                elif int(selected_download.get("totalBytes") or selected_download.get("sizeBytes") or 0) > max_download_bytes:
                    entry["staging"]["status"] = "skipped"
                    entry["staging"]["reason"] = "selected_download_exceeds_max_bytes"
                else:
                    asset_dir = output_dir / "assets" / _clean_text(entry["provider"]).replace(" ", "_").lower() / _clean_text(entry["assetId"])
                    target = asset_dir / _filename_from_url(_clean_text(selected_download.get("url")), f"{entry['assetId']}.asset")
                    entry["staging"]["downloadedFiles"] = [_download_file(http_client, _clean_text(selected_download.get("url")), target)]
                    include_records = [
                        include
                        for include in selected_download.get("includes") or []
                        if isinstance(include, dict) and _clean_text(include.get("url"))
                    ]
                    if download_includes:
                        downloaded_includes = []
                        for include in include_records:
                            include_target = asset_dir / _safe_include_path(_clean_text(include.get("path")))
                            downloaded = _download_file(http_client, _clean_text(include.get("url")), include_target)
                            downloaded["sourcePath"] = _clean_text(include.get("path"))
                            downloaded["providerMd5"] = _clean_text(include.get("md5"))
                            downloaded_includes.append(downloaded)
                        entry["staging"]["downloadedIncludes"] = downloaded_includes
                        entry["staging"]["status"] = "downloaded_package"
                        entry["staging"]["reason"] = "main_file_and_includes_downloaded"
                    else:
                        entry["staging"]["status"] = "downloaded_main_file"
                        entry["staging"]["reason"] = "includes_not_downloaded_by_default"
                    entry["staging"]["packageValidation"] = validate_staged_package(entry)
                    if import_smoke:
                        entry["staging"]["importSmoke"] = run_staged_import_smoke(entry, three_root=three_root)
            entries.append(entry)
        return {
            "generatedAt": _now().isoformat(),
            "purpose": "product_3d_render_video_scene_asset_staging",
            "policy": {
                "executionInput": False,
                "largeVendorAssetsBundledInRepo": False,
                "promotionPath": ["candidate_source", "staging_asset", "visual_performance_review", "ready_scene_asset"],
                "readyGate": [
                    "license_and_commercial_use",
                    "download_hash_recorded",
                    "three_gltf_import_smoke",
                    "no_text_logo_watermark_or_brand_props",
                    "scene_fusion_no_occlusion",
                    "safe_framing_with_close_camera",
                    "browser_preview_performance",
                    "server_worker_render_smoke",
                ],
            },
            "enrichOnline": enrich_online,
            "download": download,
            "downloadIncludes": download_includes,
            "importSmoke": import_smoke,
            "threeRoot": str((three_root or DEFAULT_THREE_ROOT).expanduser()),
            "preferredResolution": preferred_resolution,
            "maxDownloadBytes": max_download_bytes,
            "count": len(entries),
            "items": entries,
        }
    finally:
        if owns_client:
            http_client.close()


def run(args: argparse.Namespace) -> Path:
    output_dir = Path(args.output_dir or DEFAULT_OUTPUT_ROOT / _now_slug()).expanduser()
    catalog = Product3DRenderVideoService().catalog()
    candidates = collect_scene_asset_candidates(catalog)
    selected = select_scene_asset_candidates(
        candidates,
        asset_ids=args.asset_id,
        providers=args.provider,
        scene_presets=args.scene_preset,
    )
    manifest = build_staging_manifest(
        selected,
        enrich_online=not args.no_online_enrich,
        download=args.download,
        download_includes=args.download_includes,
        preferred_resolution=args.preferred_resolution,
        max_download_bytes=args.max_download_bytes,
        output_dir=output_dir,
        import_smoke=args.import_smoke,
        three_root=Path(args.three_root).expanduser() if args.three_root else None,
    )
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-id", action="append", help="Limit to one asset id. Can be repeated.")
    parser.add_argument("--provider", action="append", help="Limit to one provider. Can be repeated.")
    parser.add_argument("--scene-preset", action="append", help="Limit to candidates related to one scene preset. Can be repeated.")
    parser.add_argument("--output-dir", help="Output directory. Default: deliverables/product_3d_scene_assets/<timestamp>.")
    parser.add_argument("--no-online-enrich", action="store_true", help="Do not call provider APIs; write catalog-only manifest.")
    parser.add_argument("--download", action="store_true", help="Download the selected main file when a direct provider URL is available.")
    parser.add_argument("--download-includes", action="store_true", help="Also download dependency files listed by the provider, such as .bin and textures.")
    parser.add_argument("--import-smoke", action="store_true", help="After download validation, import .gltf with eval-web Three.js GLTFLoader.")
    parser.add_argument("--three-root", help="Directory containing node_modules/three. Default: podi-eval-web.")
    parser.add_argument("--preferred-resolution", default="1k", help="Preferred provider asset resolution for download planning.")
    parser.add_argument("--max-download-bytes", type=int, default=30 * 1024 * 1024, help="Skip downloads larger than this size.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = run(args)
    payload = {"manifestPath": str(manifest_path)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"3D scene asset staging manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
