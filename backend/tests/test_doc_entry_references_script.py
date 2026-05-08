from __future__ import annotations

import subprocess
from pathlib import Path


def test_doc_entry_reference_check_passes_current_repository() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        ["python3", "scripts/check_doc_entry_references.py"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "local path references are valid" in result.stdout
