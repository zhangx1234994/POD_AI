#!/usr/bin/env python3
"""Build a clean tar.gz archive for manual production patch uploads.

This intentionally avoids the macOS metadata that BSD tar may include
(`LIBARCHIVE.xattr.*`, AppleDouble files, .DS_Store) and normalizes mtimes so
remote hosts with slightly slower clocks do not emit "time stamp is in the
future" warnings during extraction.
"""

import argparse
import os
import tarfile
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

IGNORED_NAMES = {".DS_Store", "__MACOSX"}
IGNORED_PREFIXES = ("._",)


def _is_ignored(path: Path) -> bool:
    return path.name in IGNORED_NAMES or any(path.name.startswith(prefix) for prefix in IGNORED_PREFIXES)


def _safe_relative_path(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path is outside archive root: {path}") from exc


def _iter_archive_entries(root: Path, requested_paths: List[Path]) -> List[Tuple[Path, str]]:
    entries = []  # type: List[Tuple[Path, str]]
    for requested in requested_paths:
        source = (root / requested).resolve()
        _safe_relative_path(root, source)
        if not source.exists() and not source.is_symlink():
            raise FileNotFoundError(source)
        if source.is_dir():
            for current_root, dir_names, file_names in os.walk(source):
                current_dir = Path(current_root)
                dir_names[:] = sorted(name for name in dir_names if not _is_ignored(Path(name)))
                for dir_name in dir_names:
                    full_path = current_dir / dir_name
                    rel_path = _safe_relative_path(root, full_path)
                    entries.append((full_path, rel_path.as_posix()))
                for file_name in sorted(file_names):
                    full_path = current_dir / file_name
                    if _is_ignored(full_path):
                        continue
                    rel_path = _safe_relative_path(root, full_path)
                    entries.append((full_path, rel_path.as_posix()))
        else:
            rel_path = _safe_relative_path(root, source)
            if not _is_ignored(source):
                entries.append((source, rel_path.as_posix()))
    return entries


def _normalize_tar_info(info: tarfile.TarInfo, *, mtime: int) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = mtime
    info.pax_headers = {
        key: value
        for key, value in info.pax_headers.items()
        if not key.startswith("LIBARCHIVE.xattr.") and not key.startswith("SCHILY.xattr.")
    }
    return info


def build_archive(
    *,
    root: Path,
    output: Path,
    paths: List[Path],
    mtime: Optional[int] = None,
) -> List[str]:
    root = root.resolve()
    output = output.resolve()
    archive_mtime = int(mtime if mtime is not None else time.time() - 300)
    entries = _iter_archive_entries(root, paths)
    output.parent.mkdir(parents=True, exist_ok=True)

    added = []  # type: List[str]
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        seen = set()  # type: Set[str]
        for source, arcname in entries:
            if arcname in seen:
                continue
            seen.add(arcname)
            info = archive.gettarinfo(str(source), arcname=arcname)
            info = _normalize_tar_info(info, mtime=archive_mtime)
            if info.isfile():
                with source.open("rb") as file_obj:
                    archive.addfile(info, fileobj=file_obj)
            else:
                archive.addfile(info)
            added.append(arcname)
    return added


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a normalized release tar.gz archive.")
    parser.add_argument("--root", default=".", help="Archive root. Paths are resolved relative to this directory.")
    parser.add_argument("--output", required=True, help="Output .tar.gz path.")
    parser.add_argument(
        "--mtime",
        type=int,
        default=None,
        help="Optional fixed archive mtime epoch. Default is current time minus 300 seconds.",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to include, relative to --root.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    added = build_archive(
        root=Path(args.root),
        output=Path(args.output),
        paths=[Path(item) for item in args.paths],
        mtime=args.mtime,
    )
    print(f"archive={Path(args.output).resolve()}")
    print(f"entries={len(added)}")
    for item in added[:20]:
        print(f"- {item}")
    if len(added) > 20:
        print(f"... {len(added) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
