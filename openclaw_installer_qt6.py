#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from openclaw_installer_core import (
    DEFAULT_SAFE_BASE,
    apply_config_values,
    get_bin_hint,
    get_openclaw_executable,
    install_openclaw,
    resolve_safe_dir,
)


class Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            ok, msg = self.fn()
            self.done.emit(ok, msg)
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class InstallerWindow(QMainWindow):
    STEPS = [
        "欢迎",
        "环境检测",
        "安装目录",
        "安装 OpenClaw",
        "基础配置",
        "启动与更新检测",
        "首次对话前检查",
        "完成",
    ]

    def __init__(self):
        super().__init__()
        self._drag_pos = QPoint()
        self.safe_path = DEFAULT_SAFE_BASE
        self.installed_ok = False
        self.config_ok = False
        self.gateway_ok = False

        self.setWindowTitle("OpenClaw Installer Pro")
        self.setMinimumSize(1160, 790)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_style()
        self.refresh_step_ui()

    def _build_ui(self):
        wrap = QWidget()
        root = QVBoxLayout(wrap)
        root.setContentsMargins(16, 16, 16, 16)

        glass = QFrame()
        glass.setObjectName("glass")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.black)
        glass.setGraphicsEffect(shadow)

        g = QVBoxLayout(glass)
        g.setContentsMargins(14, 14, 14, 14)
        g.setSpacing(10)

        title = QFrame()
        title.setObjectName("titlebar")
        tl = QHBoxLayout(title)
        tl.setContentsMargins(12, 8, 12, 8)
        self.lbl_title = QLabel("OpenClaw 零基础图形化安装向导（Qt6）")
        self.lbl_title.setObjectName("title")
        tl.addWidget(self.lbl_title)
        tl.addStretch(1)
        bmin = QPushButton("—")
        bmin.clicked.connect(self.showMinimized)
        bcls = QPushButton("✕")
        bcls.clicked.connect(self.close)
        for b in (bmin, bcls):
            b.setObjectName("titlebtn")
            b.setFixedSize(34, 28)
            tl.addWidget(b)
        g.addWidget(title)

        self.step_header = QLabel()
        self.step_header.setObjectName("stepHeader")
        g.addWidget(self.step_header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        g.addWidget(self.progress)

        body = QHBoxLayout()

        self.sidebar = QFrame()
        self.sidebar.setObjectName("panel")
        sl = QVBoxLayout(self.sidebar)
        sl.addWidget(QLabel("流程总览"))
        self.step_labels: list[QLabel] = []
        for s in self.STEPS:
            lb = QLabel(f"○ {s}")
            lb.setObjectName("stepItem")
            self.step_labels.append(lb)
            sl.addWidget(lb)

        sl.addStretch(1)
        self.btn_help_docs = QPushButton("打开帮助文档")
        self.btn_help_docs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://docs.openclaw.ai")))
        sl.addWidget(self.btn_help_docs)

        body.addWidget(self.sidebar, 2)

        right = QFrame()
        right.setObjectName("panel")
        rl = QVBoxLayout(right)

        self.help_box = QLabel()
        self.help_box.setObjectName("helpBox")
        self.help_box.setWordWrap(True)
        rl.addWidget(self.help_box)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_welcome())
        self.stack.addWidget(self.page_env())
        self.stack.addWidget(self.page_dir())
        self.stack.addWidget(self.page_install())
        self.stack.addWidget(self.page_config())
        self.stack.addWidget(self.page_startup())
        self.stack.addWidget(self.page_checklist())
        self.stack.addWidget(self.page_finish())
        rl.addWidget(self.stack)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setPlaceholderText("这里显示每一步执行日志和失败修复建议…")
        rl.addWidget(self.logs, 1)

        nav = QHBoxLayout()
        self.btn_prev = QPushButton("上一步")
        self.btn_prev.clicked.connect(self.prev_step)
        self.btn_next = QPushButton("下一步")
        self.btn_next.clicked.connect(self.next_step)
        nav.addStretch(1)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        rl.addLayout(nav)

        body.addWidget(right, 5)
        g.addLayout(body)

        root.addWidget(glass)
        self.setCentralWidget(wrap)

    # Pages
    def page_welcome(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("欢迎使用：OpenClaw 小白安装向导"))
        l.addWidget(QLabel("目标：让你不写命令也能完成安装、配置、启动、首次对话前检查。"))
        return w

    def page_env(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.env_result = QLabel("待检测")
        self.env_result.setWordWrap(True)
        l.addWidget(self.env_result)
        row = QHBoxLayout()
        b1 = QPushButton("重新检测")
        b1.clicked.connect(self.run_env_check)
        b2 = QPushButton("安装 Node.js（浏览器）")
        b2.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://nodejs.org/en/download")))
        row.addWidget(b1); row.addWidget(b2)
        l.addLayout(row)
        return w

    def page_dir(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("安装目录（安全隔离）"))
        self.input_dir = QLineEdit(str(DEFAULT_SAFE_BASE))
        l.addWidget(self.input_dir)
        l.addWidget(QLabel("提示：不要选系统根目录/用户家目录，向导会自动拦截。"))
        return w

    def page_install(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.install_status = QLabel("待安装")
        l.addWidget(self.install_status)
        l.addWidget(QLabel("点击下一步会自动安装 openclaw@latest 到安全目录。"))
        return w

    def page_config(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("基础配置（全部图形化填写）"))
        self.f_tz = QLineEdit("Asia/Shanghai")
        self.f_group = QLineEdit("allowlist")
        self.f_show_ok = QLineEdit("false")
        self.f_indicator = QLineEdit("true")
        for name, field in [
            ("消息时区", self.f_tz),
            ("群聊策略(open/disabled/allowlist)", self.f_group),
            ("显示心跳OK(true/false)", self.f_show_ok),
            ("心跳指示器(true/false)", self.f_indicator),
        ]:
            l.addWidget(QLabel(name)); l.addWidget(field)
        self.config_status = QLabel("待写入")
        l.addWidget(self.config_status)
        return w

    def page_startup(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.startup_info = QLabel("待检查")
        self.startup_info.setWordWrap(True)
        l.addWidget(self.startup_info)
        row = QHBoxLayout()
        b_start = QPushButton("启动 Gateway")
        b_start.clicked.connect(self.start_gateway)
        b_dash = QPushButton("打开 Dashboard")
        b_dash.clicked.connect(lambda: self.run_and_log([str(get_openclaw_executable(self.safe_path)), "dashboard"]))
        row.addWidget(b_start); row.addWidget(b_dash)
        l.addLayout(row)
        return w

    def page_checklist(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("首次对话前，请逐项确认："))
        self.ck1 = QCheckBox("我已完成 Node/npm 检测并通过")
        self.ck2 = QCheckBox("我已成功安装 OpenClaw")
        self.ck3 = QCheckBox("我已写入基础配置")
        self.ck4 = QCheckBox("我已启动 Gateway 或打开 Dashboard")
        self.ck5 = QCheckBox("我已知晓如何开始第一次对话")
        for c in (self.ck1, self.ck2, self.ck3, self.ck4, self.ck5):
            l.addWidget(c)
        l.addWidget(QLabel("全部勾选后才可进入完成页。"))
        return w

    def page_finish(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.finish_text = QLabel("完成")
        self.finish_text.setWordWrap(True)
        l.addWidget(self.finish_text)
        return w

    # Flow
    def current_step(self):
        return self.stack.currentIndex()

    def refresh_step_ui(self):
        i = self.current_step()
        self.step_header.setText(f"Step {i+1}/{len(self.STEPS)} · {self.STEPS[i]}")
        self.progress.setValue(int((i + 1) / len(self.STEPS) * 100))
        for idx, lb in enumerate(self.step_labels):
            mark = "●" if idx == i else ("✓" if idx < i else "○")
            lb.setText(f"{mark} {self.STEPS[idx]}")
        self.btn_prev.setEnabled(i > 0)
        self.btn_next.setText("完成" if i == len(self.STEPS) - 1 else "下一步")

        helps = [
            "欢迎页：说明全流程。点击下一步开始自动化检测。",
            "环境检测：自动检查 Node/npm 和 openclaw 最新版本。若缺失，点“安装 Node.js”会打开官网。",
            "目录页：选择安全目录。向导会防止你选错危险目录。",
            "安装页：自动安装到隔离目录，不污染系统全局。",
            "配置页：所有关键参数都在图形界面填写，避免命令行。",
            "启动页：检测本地版本是否最新，可一键启动 Gateway / 打开 Dashboard。",
            "检查清单：确保零基础用户不会漏步骤。",
            "完成页：给出 PATH、版本、首次对话建议。",
        ]
        self.help_box.setText(helps[i])

    def prev_step(self):
        if self.current_step() > 0:
            self.stack.setCurrentIndex(self.current_step() - 1)
            self.refresh_step_ui()

    def next_step(self):
        i = self.current_step()
        if i == 0:
            self.stack.setCurrentIndex(1)
            self.run_env_check()
        elif i == 1:
            if not self.run_env_check(show_popup=True):
                return
            self.stack.setCurrentIndex(2)
        elif i == 2:
            if not self.validate_dir():
                return
            self.stack.setCurrentIndex(3)
        elif i == 3:
            self.run_install()
            return
        elif i == 4:
            self.run_config()
            return
        elif i == 5:
            self.refresh_startup_info()
            self.stack.setCurrentIndex(6)
        elif i == 6:
            if not all([self.ck1.isChecked(), self.ck2.isChecked(), self.ck3.isChecked(), self.ck4.isChecked(), self.ck5.isChecked()]):
                QMessageBox.warning(self, "检查未完成", "请先勾选全部检查项。")
                return
            self.stack.setCurrentIndex(7)
            self.finish_text.setText(
                f"安装已完成。\n本地可执行：{get_openclaw_executable(self.safe_path)}\n"
                f"PATH 目录：{get_bin_hint(self.safe_path)}\n"
                "你现在可以在 Dashboard 或聊天渠道里开始第一次对话。"
            )
        elif i == 7:
            QMessageBox.information(self, "完成", "向导流程全部完成。")
            return
        self.refresh_step_ui()

    def run_env_check(self, show_popup=False):
        node = shutil.which("node")
        npm = shutil.which("npm")
        node_v = self.try_cmd([node, "-v"]) if node else "未找到"
        npm_v = self.try_cmd([npm, "-v"]) if npm else "未找到"
        latest = self.try_cmd([npm, "view", "openclaw", "version"]) if npm else "未知"
        ok = bool(node and npm)
        msg = f"node: {node_v}\nnpm: {npm_v}\nopenclaw 最新: {latest}"
        self.env_result.setText(msg)
        self.log(msg)
        self.ck1.setChecked(ok)
        if show_popup and not ok:
            QMessageBox.warning(self, "环境不满足", "未检测到 Node/npm，请先安装 Node.js。")
        return ok

    def validate_dir(self):
        try:
            self.safe_path = resolve_safe_dir(self.input_dir.text())
            self.log(f"目录已确认: {self.safe_path}")
            return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "目录错误", str(e))
            return False

    def run_install(self):
        self.btn_next.setEnabled(False)

        def fn():
            res = install_openclaw(self.safe_path)
            self.log(' '.join(res.command))
            self.log(res.message)
            return res.ok, res.message

        self.worker = Worker(fn)
        self.worker.done.connect(self._done_install)
        self.worker.start()

    def _done_install(self, ok, msg):
        self.btn_next.setEnabled(True)
        self.install_status.setText(msg)
        self.installed_ok = ok
        self.ck2.setChecked(ok)
        if ok:
            self.stack.setCurrentIndex(4)
            self.refresh_step_ui()
        else:
            QMessageBox.critical(self, "安装失败", msg)

    def run_config(self):
        self.btn_next.setEnabled(False)

        def fn():
            values = {
                "agents.defaults.envelopeTimezone": self.f_tz.text(),
                "channels.defaults.groupPolicy": self.f_group.text(),
                "channels.defaults.heartbeat.showOk": self.f_show_ok.text(),
                "channels.defaults.heartbeat.useIndicator": self.f_indicator.text(),
            }
            res = apply_config_values(self.safe_path, values)
            self.log(res.message)
            return res.ok, res.message

        self.worker = Worker(fn)
        self.worker.done.connect(self._done_config)
        self.worker.start()

    def _done_config(self, ok, msg):
        self.btn_next.setEnabled(True)
        self.config_status.setText(msg)
        self.config_ok = ok
        self.ck3.setChecked(ok)
        if ok:
            self.stack.setCurrentIndex(5)
            self.refresh_startup_info()
            self.refresh_step_ui()
        else:
            QMessageBox.critical(self, "配置失败", msg)

    def refresh_startup_info(self):
        exe = get_openclaw_executable(self.safe_path)
        local_v = self.try_cmd([str(exe), "--version"]) if exe.exists() else "未找到"
        npm = shutil.which("npm")
        latest = self.try_cmd([npm, "view", "openclaw", "version"]) if npm else "未知"
        self.startup_info.setText(f"本地版本: {local_v}\n仓库最新版本: {latest}\nPATH: {get_bin_hint(self.safe_path)}")

    def start_gateway(self):
        exe = get_openclaw_executable(self.safe_path)
        if not exe.exists():
            QMessageBox.warning(self, "未安装", "先完成安装步骤")
            return
        out = self.try_cmd([str(exe), "gateway", "start"])
        self.log(out)
        self.gateway_ok = "error" not in out.lower()
        self.ck4.setChecked(self.gateway_ok)

    def run_and_log(self, cmd):
        self.log(self.try_cmd(cmd))

    def try_cmd(self, cmd):
        if not cmd or not cmd[0]:
            return "命令不可用"
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=30).strip()
        except Exception as e:  # noqa: BLE001
            return f"命令失败: {e}"

    def log(self, text):
        self.logs.appendPlainText(text)

    # frameless drag
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _apply_style(self):
        QApplication.instance().setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QFrame#glass { background: rgba(15,23,42,0.80); border: 1px solid rgba(148,163,184,0.35); border-radius: 18px; }
            QFrame#titlebar { background: rgba(30,41,59,0.75); border-radius: 12px; }
            QLabel#title { font-size: 20px; font-weight: 700; color: #f8fafc; }
            QLabel#stepHeader { color: #93c5fd; font-size: 13px; font-weight: 600; }
            QFrame#panel { background: rgba(17,24,39,0.80); border: 1px solid #1f2937; border-radius: 14px; }
            QLabel#helpBox { background: rgba(2,6,23,0.65); border: 1px dashed #334155; border-radius: 10px; padding: 10px; color: #cbd5e1; }
            QLabel, QCheckBox { color: #e2e8f0; }
            QLineEdit, QPlainTextEdit { background: rgba(2,6,23,0.9); color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 8px; }
            QPushButton { background: #2563eb; color: white; border-radius: 10px; padding: 9px 14px; font-weight: 600; border: none; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton#titlebtn { background: rgba(30,41,59,0.9); }
            QProgressBar { border: 1px solid #334155; border-radius: 8px; background: #020617; text-align: center; }
            QProgressBar::chunk { background: #22c55e; border-radius: 7px; }
            """
        )


def main():
    app = QApplication(sys.argv)
    w = InstallerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
