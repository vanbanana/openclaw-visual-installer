#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from openclaw_installer_core import (
    DEFAULT_SAFE_BASE,
    apply_config_values,
    get_bin_hint,
    install_openclaw,
    resolve_safe_dir,
)


class InstallWorker(QThread):
    log = Signal(str)
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, safe_dir: str):
        super().__init__()
        self.safe_dir = safe_dir

    def run(self) -> None:
        try:
            safe = resolve_safe_dir(self.safe_dir)
            self.log.emit(f"安全目录: {safe}")
            self.progress.emit(25)
            result = install_openclaw(safe)
            self.log.emit(f"命令: {' '.join(result.command)}")
            self.log.emit(result.message)
            self.log.emit(f"PATH 提示: {get_bin_hint(safe)}")
            self.progress.emit(70 if result.ok else 0)
            self.done.emit(result.ok, result.message)
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class ConfigWorker(QThread):
    log = Signal(str)
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, safe_dir: str, values: dict[str, str]):
        super().__init__()
        self.safe_dir = safe_dir
        self.values = values

    def run(self) -> None:
        try:
            safe = resolve_safe_dir(self.safe_dir)
            result = apply_config_values(safe, self.values)
            self.log.emit(result.message)
            self.progress.emit(100 if result.ok else 70)
            self.done.emit(result.ok, result.message)
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenClaw Installer Pro (Qt6)")
        self.resize(980, 700)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(14)

        title = QLabel("OpenClaw 现代化一键安装器")
        title.setObjectName("title")
        subtitle = QLabel("Qt6 UI · 安装与配置全图形化 · 安全目录隔离")
        subtitle.setObjectName("subtitle")

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        main.addWidget(title)
        main.addWidget(subtitle)
        main.addWidget(self.progress)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        form = QFormLayout()
        self.safe_dir = QLineEdit(str(DEFAULT_SAFE_BASE))
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.safe_dir)
        browse = QPushButton("浏览")
        browse.clicked.connect(self.pick_dir)
        dir_row.addWidget(browse)
        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        form.addRow("安全目录", dir_wrap)

        self.timezone = QLineEdit("Asia/Shanghai")
        self.group_policy = QLineEdit("allowlist")
        self.show_ok = QLineEdit("false")
        self.indicator = QLineEdit("true")

        form.addRow("消息时区", self.timezone)
        form.addRow("群聊策略", self.group_policy)
        form.addRow("显示心跳OK", self.show_ok)
        form.addRow("心跳指示器", self.indicator)

        card_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_install = QPushButton("① 安装 OpenClaw")
        self.btn_install.clicked.connect(self.start_install)
        self.btn_config = QPushButton("② 写入配置")
        self.btn_config.clicked.connect(self.start_config)
        self.btn_copy = QPushButton("复制 PATH")
        self.btn_copy.clicked.connect(self.copy_path)
        btn_row.addWidget(self.btn_install)
        btn_row.addWidget(self.btn_config)
        btn_row.addWidget(self.btn_copy)
        card_layout.addLayout(btn_row)

        main.addWidget(card)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setPlaceholderText("安装/配置日志会显示在这里…")
        main.addWidget(self.logs, stretch=1)

        self.status = QLabel("待命：先点安装，再点写入配置")
        self.status.setObjectName("status")
        main.addWidget(self.status)

    def _apply_style(self) -> None:
        QApplication.instance().setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QMainWindow { background: #0f172a; color: #e2e8f0; }
            QLabel#title { font-size: 28px; font-weight: 700; color: #f8fafc; }
            QLabel#subtitle { color: #94a3b8; }
            QLabel#status { color: #93c5fd; font-weight: 600; }
            QFrame#card { background: #111827; border: 1px solid #1f2937; border-radius: 14px; }
            QLineEdit, QPlainTextEdit {
                background: #020617;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px;
            }
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 10px;
                color: white;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #334155; color: #94a3b8; }
            QProgressBar {
                border: 1px solid #1e293b;
                border-radius: 8px;
                background: #020617;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk { background-color: #22c55e; border-radius: 6px; }
            """
        )

    def log(self, text: str) -> None:
        self.logs.appendPlainText(text)

    def pick_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择安全目录", self.safe_dir.text())
        if path:
            self.safe_dir.setText(path)

    def copy_path(self) -> None:
        try:
            hint = get_bin_hint(resolve_safe_dir(self.safe_dir.text()))
            QApplication.clipboard().setText(hint)
            self.status.setText("已复制 PATH 目录")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "路径错误", str(e))

    def start_install(self) -> None:
        self.btn_install.setEnabled(False)
        self.status.setText("安装中…")
        self.worker = InstallWorker(self.safe_dir.text())
        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.done.connect(self.finish_install)
        self.worker.start()

    def finish_install(self, ok: bool, msg: str) -> None:
        self.btn_install.setEnabled(True)
        if ok:
            self.status.setText("安装完成，可继续写入配置")
            QMessageBox.information(self, "完成", "安装成功")
        else:
            self.status.setText("安装失败")
            QMessageBox.critical(self, "失败", msg)

    def start_config(self) -> None:
        self.btn_config.setEnabled(False)
        self.status.setText("配置写入中…")
        values = {
            "agents.defaults.envelopeTimezone": self.timezone.text(),
            "channels.defaults.groupPolicy": self.group_policy.text(),
            "channels.defaults.heartbeat.showOk": self.show_ok.text(),
            "channels.defaults.heartbeat.useIndicator": self.indicator.text(),
        }
        self.cfg_worker = ConfigWorker(self.safe_dir.text(), values)
        self.cfg_worker.log.connect(self.log)
        self.cfg_worker.progress.connect(self.progress.setValue)
        self.cfg_worker.done.connect(self.finish_config)
        self.cfg_worker.start()

    def finish_config(self, ok: bool, msg: str) -> None:
        self.btn_config.setEnabled(True)
        if ok:
            self.status.setText("全部完成 ✅")
            QMessageBox.information(self, "完成", "配置写入成功")
        else:
            self.status.setText("配置失败")
            QMessageBox.critical(self, "失败", msg)


def main() -> None:
    app = QApplication(sys.argv)
    w = InstallerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
