from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_eval_health_module():
    script_path = REPO_ROOT / "backend" / "scripts" / "check_eval_operations_health.py"
    spec = importlib.util.spec_from_file_location("check_eval_operations_health", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_eval_health_write_report_creates_parent_directory(tmp_path) -> None:
    module = _load_eval_health_module()
    report_path = tmp_path / "nested" / "eval_health.json"

    written = module._write_report({"status": "healthy", "issues": []}, str(report_path))

    assert written == str(report_path)
    assert report_path.exists()
    assert '"status": "healthy"' in report_path.read_text(encoding="utf-8")


def test_health_watch_shell_script_has_fixed_reports_and_live_recording() -> None:
    script_path = REPO_ROOT / "scripts" / "run_podi_health_watch.sh"
    script = script_path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(script_path)], check=True)
    subprocess.run(["bash", "-n", str(REPO_ROOT / "scripts" / "install_business_health_watch.sh")], check=True)

    assert 'REPORT_DIR="${REPORT_DIR:-$TARGET_ROOT/reports/health-watch}"' in script
    assert "--record-release-patrol" in script
    assert "--report \"$report\"" in script
    assert "--report \"$(make_report_path business_route)\"" in script
    assert "--report \"$(make_report_path eval_health)\"" in script
    assert "--report \"$(make_report_path eval_production)\"" in script
