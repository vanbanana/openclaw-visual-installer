#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
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
    log = Signal(str)
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            ok, msg = self.fn(*self.args, **self.kwargs)
            self.done.emit(ok, msg)
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._drag_pos = QPoint()
        self.current_safe_dir = DEFAULT_SAFE_BASE

        self.setWindowTitle("OpenClaw Installer Pro")
        self.setMinimumSize(1080, 760)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_style()

    # -------------------- UI --------------------
    def _build_ui(self):
        wrap = QWidget()
        root = QVBoxLayout(wrap)
        root.setContentsMargins(16, 16, 16, 16)

        glass = QFrame()
        glass.setObjectName("glass")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(45)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.black)
        glass.setGraphicsEffect(shadow)

        g_layout = QVBoxLayout(glass)
        g_layout.setContentsMargins(14, 14, 14, 14)
        g_layout.setSpacing(10)

        # custom title bar
        title = QFrame()
        title.setObjectName("titlebar")
        t = QHBoxLayout(title)
        t.setContentsMargins(12, 8, 12, 8)
        self.title_label = QLabel("OpenClaw 安装向导 · Qt6")
        self.title_label.setObjectName("title")
        t.addWidget(self.title_label)
        t.addStretch(1)
        btn_min = QPushButton("—")
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QPushButton("✕")
        btn_close.clicked.connect(self.close)
        for b in (btn_min, btn_close):
            b.setFixedSize(34, 28)
            b.setObjectName("titlebtn")
            t.addWidget(b)
        g_layout.addWidget(title)

        # step indicator
        self.step_label = QLabel("Step 1/5 · 环境检测")
        self.step_label.setObjectName("step")
        g_layout.addWidget(self.step_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(10)
        g_layout.addWidget(self.progress)

        body = QHBoxLayout()

        # left guide panel
        guide = QFrame()
        guide.setObjectName("guide")
        gl = QVBoxLayout(guide)
        gl.addWidget(QLabel("安装总流程"))
        self.guide_text = QLabel(
            "1) 检测 Node/npm/网络\n"
            "2) 选择安装目录与安全策略\n"
            "3) 执行安装\n"
            "4) 可视化填写配置\n"
            "5) 启动前检查与版本校验"
        )
        self.guide_text.setWordWrap(True)
        gl.addWidget(self.guide_text)
        gl.addStretch(1)

        body.addWidget(guide, 2)

        # right wizard
        right = QFrame()
        right.setObjectName("card")
        rl = QVBoxLayout(right)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_check())
        self.stack.addWidget(self._page_dir())
        self.stack.addWidget(self._page_install())
        self.stack.addWidget(self._page_config())
        self.stack.addWidget(self._page_finish())
        rl.addWidget(self.stack)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setPlaceholderText("实时日志…")
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
        g_layout.addLayout(body)

        root.addWidget(glass)
        self.setCentralWidget(wrap)
        self._sync_nav()

    def _page_check(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("环境检测（全自动）"))
        self.check_result = QLabel("点击“下一步”开始检测")
        self.check_result.setWordWrap(True)
        l.addWidget(self.check_result)
        return w

    def _page_dir(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("安装目录与安全策略"))
        self.safe_dir = QLineEdit(str(DEFAULT_SAFE_BASE))
        l.addWidget(self.safe_dir)
        self.dir_hint = QLabel("将安装到隔离目录，不污染系统全局。")
        l.addWidget(self.dir_hint)
        return w

    def _page_install(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("执行安装"))
        self.install_state = QLabel("点击“下一步”开始安装")
        l.addWidget(self.install_state)
        return w

    def _page_config(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("可视化配置（无需命令行）"))
        self.f_timezone = QLineEdit("Asia/Shanghai")
        self.f_group = QLineEdit("allowlist")
        self.f_ok = QLineEdit("false")
        self.f_indicator = QLineEdit("true")
        for label, field in [
            ("消息时区", self.f_timezone),
            ("群聊策略", self.f_group),
            ("显示心跳OK", self.f_ok),
            ("心跳指示器", self.f_indicator),
        ]:
            l.addWidget(QLabel(label))
            l.addWidget(field)
        self.config_state = QLabel("点击“下一步”写入配置")
        l.addWidget(self.config_state)
        return w

    def _page_finish(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("完成与首次启动指导"))
        self.finish_text = QLabel("安装完成后，这里会显示版本、PATH、启动建议。")
        self.finish_text.setWordWrap(True)
        l.addWidget(self.finish_text)
        return w

    def _apply_style(self):
        QApplication.instance().setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QFrame#glass { background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(148,163,184,0.35); border-radius: 18px; }
            QFrame#titlebar { background: rgba(30, 41, 59, 0.75); border-radius: 12px; }
            QLabel#title { font-size: 20px; font-weight: 700; color: #f8fafc; }
            QLabel#step { color: #93c5fd; font-size: 13px; font-weight: 600; }
            QFrame#guide, QFrame#card { background: rgba(17, 24, 39, 0.80); border: 1px solid #1f2937; border-radius: 14px; }
            QLabel { color: #e2e8f0; }
            QLineEdit, QPlainTextEdit {
              background: rgba(2, 6, 23, 0.9); color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 8px;
            }
            QPushButton { background: #2563eb; color: white; border-radius: 10px; padding: 9px 14px; font-weight: 600; border: none; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton#titlebtn { background: rgba(30,41,59,0.9); }
            QProgressBar { border: 1px solid #334155; border-radius: 8px; background: #020617; text-align: center; }
            QProgressBar::chunk { background: #22c55e; border-radius: 7px; }
            """
        )

    # -------------------- flow --------------------
    def log(self, text: str):
        self.logs.appendPlainText(text)

    def prev_step(self):
        i = self.stack.currentIndex()
        if i > 0:
            self.stack.setCurrentIndex(i - 1)
            self._sync_nav()

    def next_step(self):
        i = self.stack.currentIndex()
        if i == 0:
            self.run_check()
        elif i == 1:
            self.run_dir_validate()
        elif i == 2:
            self.run_install()
        elif i == 3:
            self.run_config()
        elif i == 4:
            QMessageBox.information(self, "完成", "已完成全部步骤。")

    def _sync_nav(self):
        i = self.stack.currentIndex()
        self.btn_prev.setEnabled(i > 0)
        self.btn_next.setText("完成" if i == 4 else "下一步")
        self.step_label.setText(["Step 1/5 · 环境检测", "Step 2/5 · 安全目录", "Step 3/5 · 安装", "Step 4/5 · 配置", "Step 5/5 · 启动指导"][i])
        self.progress.setValue([10, 25, 45, 70, 100][i])

    def run_check(self):
        node = shutil.which("node")
        npm = shutil.which("npm")
        ok = bool(node and npm)
        node_v = self._run_cmd([node, "-v"]) if node else "未找到"
        npm_v = self._run_cmd([npm, "-v"]) if npm else "未找到"
        latest = self._run_cmd([npm, "view", "openclaw", "version"]) if npm else "未知"
        self.check_result.setText(f"node: {node_v}\nnpm: {npm_v}\nopenclaw latest: {latest}")
        self.log(self.check_result.text())
        if not ok:
            QMessageBox.warning(self, "环境不足", "请先安装 Node.js 与 npm")
            return
        self.stack.setCurrentIndex(1)
        self._sync_nav()

    def run_dir_validate(self):
        try:
            p = resolve_safe_dir(self.safe_dir.text())
            self.current_safe_dir = p
            self.dir_hint.setText(f"目录有效：{p}")
            self.log(f"safe dir ok: {p}")
            self.stack.setCurrentIndex(2)
            self._sync_nav()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "目录错误", str(e))

    def run_install(self):
        self.btn_next.setEnabled(False)

        def fn():
            res = install_openclaw(self.current_safe_dir)
            self.log(f"install cmd: {' '.join(res.command)}")
            self.log(res.message)
            return res.ok, res.message

        self.worker = Worker(fn)
        self.worker.done.connect(self._done_install)
        self.worker.start()

    def _done_install(self, ok: bool, msg: str):
        self.btn_next.setEnabled(True)
        self.install_state.setText(msg)
        if ok:
            self.stack.setCurrentIndex(3)
            self._sync_nav()
        else:
            QMessageBox.critical(self, "安装失败", msg)

    def run_config(self):
        self.btn_next.setEnabled(False)

        def fn():
            values = {
                "agents.defaults.envelopeTimezone": self.f_timezone.text(),
                "channels.defaults.groupPolicy": self.f_group.text(),
                "channels.defaults.heartbeat.showOk": self.f_ok.text(),
                "channels.defaults.heartbeat.useIndicator": self.f_indicator.text(),
            }
            res = apply_config_values(self.current_safe_dir, values)
            self.log(res.message)
            return res.ok, res.message

        self.worker = Worker(fn)
        self.worker.done.connect(self._done_config)
        self.worker.start()

    def _done_config(self, ok: bool, msg: str):
        self.btn_next.setEnabled(True)
        self.config_state.setText(msg)
        if ok:
            exe = get_openclaw_executable(self.current_safe_dir)
            local_ver = self._run_cmd([str(exe), "--version"]) if exe.exists() else "未检测到"
            npm = shutil.which("npm")
            latest = self._run_cmd([npm, "view", "openclaw", "version"]) if npm else "未知"
            self.finish_text.setText(
                f"本地安装版本: {local_ver}\n仓库最新版本: {latest}\n"
                f"PATH: {get_bin_hint(self.current_safe_dir)}\n"
                f"下一步：将 PATH 加入系统后，打开 OpenClaw 并完成首次对话向导。"
            )
            self.stack.setCurrentIndex(4)
            self._sync_nav()
        else:
            QMessageBox.critical(self, "配置失败", msg)

    @staticmethod
    def _run_cmd(cmd):
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=20).strip()
        except Exception as e:  # noqa: BLE001
            return f"命令失败: {e}"

    # -------------------- frameless drag --------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


def main():
    app = QApplication(sys.argv)
    w = InstallerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
