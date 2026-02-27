"""PySide6 GUI for desktop agent configuration and operations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from agent_core.config import load_config, save_config
from agent_core.health_check import run_health_check
from agent_core.models import JwtKey


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PODI ComfyUI 代理服务")
        self.resize(980, 700)
        self.cfg = load_config()
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_config_tab()
        self._build_enroll_tab()
        self._build_runtime_tab()

    def _build_config_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.center_url = QLineEdit(self.cfg.center_url)
        self.install_key = QLineEdit(self.cfg.install_key)
        self.install_key.setPlaceholderText("零配置安装密钥（可选）")
        self.comfyui_path = QLineEdit(self.cfg.comfyui_path)
        self.comfyui_port = QSpinBox()
        self.comfyui_port.setRange(1, 65535)
        self.comfyui_port.setValue(self.cfg.comfyui_port)
        self.agent_port = QSpinBox()
        self.agent_port.setRange(1, 65535)
        self.agent_port.setValue(self.cfg.agent_port)
        self.heartbeat_sec = QSpinBox()
        self.heartbeat_sec.setRange(10, 3600)
        self.heartbeat_sec.setValue(self.cfg.heartbeat_interval_sec)

        form.addRow("中台地址", self.center_url)
        form.addRow("安装密钥", self.install_key)
        form.addRow("ComfyUI 路径", self.comfyui_path)
        form.addRow("ComfyUI 端口", self.comfyui_port)
        form.addRow("代理服务端口", self.agent_port)
        form.addRow("心跳间隔(秒)", self.heartbeat_sec)
        layout.addLayout(form)

        btn_line = QHBoxLayout()
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._save_config)
        check_btn = QPushButton("执行体检")
        check_btn.clicked.connect(self._run_health_check)
        btn_line.addWidget(save_btn)
        btn_line.addWidget(check_btn)
        btn_line.addStretch(1)
        layout.addLayout(btn_line)

        self.health_output = QPlainTextEdit()
        self.health_output.setReadOnly(True)
        layout.addWidget(QLabel("体检结果"))
        layout.addWidget(self.health_output, 1)

        self.tabs.addTab(tab, "接入配置")

    def _build_enroll_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.enroll_code = QLineEdit()
        self.machine_name = QLineEdit()
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("例如 http://1.2.3.4:18079")
        form.addRow("注册码", self.enroll_code)
        form.addRow("机器名称", self.machine_name)
        form.addRow("代理地址(可选)", self.base_url)
        layout.addLayout(form)

        run_btn = QPushButton("完成接入")
        run_btn.clicked.connect(self._do_enroll)
        layout.addWidget(run_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.enroll_output = QPlainTextEdit()
        self.enroll_output.setReadOnly(True)
        layout.addWidget(self.enroll_output, 1)
        self.tabs.addTab(tab, "首次接入")

    def _build_runtime_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        button_line = QHBoxLayout()
        refresh_btn = QPushButton("刷新状态")
        refresh_btn.clicked.connect(self._refresh_runtime)
        history_btn = QPushButton("查看任务历史")
        history_btn.clicked.connect(self._load_task_history)
        update_btn = QPushButton("检查更新")
        update_btn.clicked.connect(self._check_updates)
        apply_btn = QPushButton("执行更新")
        apply_btn.clicked.connect(self._apply_updates)
        button_line.addWidget(refresh_btn)
        button_line.addWidget(history_btn)
        button_line.addWidget(update_btn)
        button_line.addWidget(apply_btn)
        button_line.addStretch(1)
        layout.addLayout(button_line)
        self.runtime_output = QPlainTextEdit()
        self.runtime_output.setReadOnly(True)
        layout.addWidget(self.runtime_output, 1)
        self.tabs.addTab(tab, "运行总览")

    def _save_config(self) -> None:
        self.cfg.center_url = self.center_url.text().strip()
        self.cfg.install_key = self.install_key.text().strip()
        self.cfg.auto_bootstrap = True
        self.cfg.comfyui_path = self.comfyui_path.text().strip()
        self.cfg.comfyui_port = int(self.comfyui_port.value())
        self.cfg.agent_port = int(self.agent_port.value())
        self.cfg.heartbeat_interval_sec = int(self.heartbeat_sec.value())
        save_config(self.cfg)
        QMessageBox.information(self, "已保存", "配置已保存。")

    def _run_health_check(self) -> None:
        report = run_health_check(
            comfyui_path=self.comfyui_path.text().strip(),
            comfyui_port=int(self.comfyui_port.value()),
        )
        self.health_output.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))

    def _do_enroll(self) -> None:
        self._save_config()
        payload = {
            "enrollCode": self.enroll_code.text().strip(),
            "machineName": self.machine_name.text().strip() or Path.home().name,
            "baseUrl": self.base_url.text().strip() or None,
        }
        if not payload["enrollCode"]:
            QMessageBox.warning(self, "缺少参数", "请填写注册码。")
            return
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.cfg.center_url.rstrip('/')}/api/agent/bootstrap/exchange",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            self.cfg.center_url = str(data.get("centerUrl") or self.cfg.center_url).strip()
            self.cfg.agent_id = str(data.get("agentId") or "").strip()
            self.cfg.agent_token = str(data.get("agentToken") or "").strip()
            keyset = []
            for item in data.get("jwtKeys") or []:
                if isinstance(item, dict) and item.get("kid") and item.get("secret"):
                    keyset.append(item)
            if keyset:
                self.cfg.jwt_keys = [JwtKey(kid=k["kid"], secret=k["secret"], status=k.get("status", "active")) for k in keyset]
            save_config(self.cfg)
            self.enroll_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            QMessageBox.information(self, "接入成功", "已完成注册并保存凭证。")
        except Exception as exc:
            self.enroll_output.setPlainText(str(exc))
            QMessageBox.critical(self, "接入失败", str(exc))

    def _refresh_runtime(self) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"http://127.0.0.1:{int(self.cfg.agent_port)}/status")
                resp.raise_for_status()
                data = resp.json()
            self.runtime_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.runtime_output.setPlainText(f"本地代理服务不可达：{exc}")

    def _load_task_history(self) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"http://127.0.0.1:{int(self.cfg.agent_port)}/tasks/history?limit=200")
                resp.raise_for_status()
                data = resp.json()
            self.runtime_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.runtime_output.setPlainText(str(exc))

    def _check_updates(self) -> None:
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(f"http://127.0.0.1:{int(self.cfg.agent_port)}/updates/check")
                resp.raise_for_status()
                data = resp.json()
            self.runtime_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.runtime_output.setPlainText(str(exc))

    def _apply_updates(self) -> None:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"http://127.0.0.1:{int(self.cfg.agent_port)}/updates/apply")
                resp.raise_for_status()
                data = resp.json()
            self.runtime_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.runtime_output.setPlainText(str(exc))


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
