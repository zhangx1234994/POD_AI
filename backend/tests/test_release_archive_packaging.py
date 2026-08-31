import importlib.util
import os
import tarfile
from pathlib import Path


def _load_packager_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "package_release_archive.py"
    spec = importlib.util.spec_from_file_location("package_release_archive", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_release_archive_normalizes_metadata(tmp_path: Path) -> None:
    module = _load_packager_module()
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "backend" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('ok')\n", encoding="utf-8")
    ignored = root / "backend" / ".DS_Store"
    ignored.write_text("ignore", encoding="utf-8")
    apple_double = root / "backend" / "._app.py"
    apple_double.write_text("ignore", encoding="utf-8")
    macosx_dir = root / "backend" / "__MACOSX"
    macosx_dir.mkdir()
    (macosx_dir / "payload").write_text("ignore", encoding="utf-8")
    env_file = root / "backend" / ".env"
    env_file.write_text("SECRET=ignore\n", encoding="utf-8")
    venv_file = root / "backend" / ".venv" / "pyvenv.cfg"
    venv_file.parent.mkdir()
    venv_file.write_text("ignore\n", encoding="utf-8")
    pycache_file = root / "backend" / "__pycache__" / "app.cpython-311.pyc"
    pycache_file.parent.mkdir()
    pycache_file.write_bytes(b"ignore")
    node_module_file = root / "backend" / "node_modules" / "package" / "index.js"
    node_module_file.parent.mkdir(parents=True)
    node_module_file.write_text("ignore\n", encoding="utf-8")
    os.utime(target, (4_000_000_000, 4_000_000_000))

    output = tmp_path / "release.tgz"
    added = module.build_archive(root=root, output=output, paths=[Path("backend")], mtime=1_700_000_000)

    assert "backend/app.py" in added
    assert "backend/.DS_Store" not in added
    assert "backend/._app.py" not in added
    assert "backend/__MACOSX" not in added
    assert "backend/__MACOSX/payload" not in added
    assert "backend/.env" not in added
    assert "backend/.venv" not in added
    assert "backend/.venv/pyvenv.cfg" not in added
    assert "backend/__pycache__" not in added
    assert "backend/__pycache__/app.cpython-311.pyc" not in added
    assert "backend/node_modules" not in added
    assert "backend/node_modules/package/index.js" not in added

    with tarfile.open(output, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}

    assert "backend/app.py" in members
    assert "backend/.DS_Store" not in members
    assert "backend/._app.py" not in members
    assert "backend/__MACOSX" not in members
    assert "backend/__MACOSX/payload" not in members
    assert "backend/.env" not in members
    assert "backend/.venv" not in members
    assert "backend/.venv/pyvenv.cfg" not in members
    assert "backend/__pycache__" not in members
    assert "backend/__pycache__/app.cpython-311.pyc" not in members
    assert "backend/node_modules" not in members
    assert "backend/node_modules/package/index.js" not in members
    app_member = members["backend/app.py"]
    assert app_member.uid == 0
    assert app_member.gid == 0
    assert app_member.uname == "root"
    assert app_member.gname == "root"
    assert app_member.mtime == 1_700_000_000
    assert not any(key.startswith("LIBARCHIVE.xattr.") for key in app_member.pax_headers)
    assert not any(key.startswith("SCHILY.xattr.") for key in app_member.pax_headers)


def test_package_release_archive_can_package_dist_contents_without_prefix(tmp_path: Path) -> None:
    module = _load_packager_module()
    root = tmp_path / "dist"
    root.mkdir()
    (root / "index.html").write_text("<div>PODI</div>\n", encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("console.log('ok')\n", encoding="utf-8")

    output = tmp_path / "dist.tgz"
    added = module.build_archive(root=root, output=output, paths=[Path(".")], mtime=1_700_000_000)

    assert "index.html" in added
    assert "assets" in added
    assert "assets/main.js" in added
    assert "." not in added


def test_control_plane_release_packages_executor_config() -> None:
    """控制面发布包必须携带 config，否则 233 inactive 配置无法同步到 /srv/pod。"""

    repo_root = Path(__file__).resolve().parents[2]
    release_script = (repo_root / "scripts" / "release_114_control_plane.sh").read_text(encoding="utf-8")

    assert "backend config/executors.yaml docs scripts deploy" in release_script
    assert "rm -f config/executors.yaml" in release_script
    assert "rm -rf backend config docs scripts deploy" not in release_script
    assert 'EXECUTOR_CONFIG_PATH="$TARGET_ROOT/config/executors.yaml" .venv/bin/python scripts/refresh_workflow_seeds.py' in release_script
    assert "EXECUTOR_CONFIG_PATH points outside production config" in release_script
