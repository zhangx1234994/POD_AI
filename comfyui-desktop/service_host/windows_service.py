"""Windows service helper for desktop agent.

This module keeps service management scriptable even before pywin32 service
wrapping is introduced. It uses `sc.exe` for install/remove/start/stop.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SERVICE_NAME = "PodiComfyuiAgent"
DISPLAY_NAME = "PODI ComfyUI 代理服务"


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())


def install(python_exe: str, workdir: str, home_dir: str | None = None) -> None:
    script = Path(workdir) / "agent_server" / "main.py"
    runtime_home = Path(home_dir) if home_dir else Path(workdir) / "runtime"
    runtime_home.mkdir(parents=True, exist_ok=True)
    wrapper = Path(workdir) / "run_agent_service.cmd"
    wrapper.write_text(
        "\n".join(
            [
                "@echo off",
                f"set COMFYUI_DESKTOP_HOME={runtime_home}",
                f'"{python_exe}" "{script}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    binary = f'"{wrapper}"'
    _run(["sc", "create", SERVICE_NAME, f"binPath={binary}", "start=auto", f"DisplayName={DISPLAY_NAME}"])
    _run(["sc", "description", SERVICE_NAME, "PODI ComfyUI desktop agent service"])


def remove() -> None:
    _run(["sc", "delete", SERVICE_NAME])


def start() -> None:
    _run(["sc", "start", SERVICE_NAME])


def stop() -> None:
    _run(["sc", "stop", SERVICE_NAME])


def status() -> None:
    _run(["sc", "query", SERVICE_NAME])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage PODI desktop agent windows service")
    parser.add_argument("action", choices=["install", "remove", "start", "stop", "status"])
    parser.add_argument("--python", default=sys.executable, help="python executable")
    parser.add_argument("--workdir", default=str(Path(__file__).resolve().parents[1]), help="project root")
    parser.add_argument("--home", default=None, help="runtime home dir")
    args = parser.parse_args(argv)

    try:
        if args.action == "install":
            install(args.python, args.workdir, args.home)
        elif args.action == "remove":
            remove()
        elif args.action == "start":
            start()
        elif args.action == "stop":
            stop()
        else:
            status()
    except Exception as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
