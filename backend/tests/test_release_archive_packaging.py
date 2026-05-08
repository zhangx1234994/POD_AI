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
    os.utime(target, (4_000_000_000, 4_000_000_000))

    output = tmp_path / "release.tgz"
    added = module.build_archive(root=root, output=output, paths=[Path("backend")], mtime=1_700_000_000)

    assert "backend/app.py" in added
    assert "backend/.DS_Store" not in added
    assert "backend/._app.py" not in added
    assert "backend/__MACOSX" not in added
    assert "backend/__MACOSX/payload" not in added

    with tarfile.open(output, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}

    assert "backend/app.py" in members
    assert "backend/.DS_Store" not in members
    assert "backend/._app.py" not in members
    assert "backend/__MACOSX" not in members
    assert "backend/__MACOSX/payload" not in members
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
