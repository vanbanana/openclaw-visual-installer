#!/usr/bin/env python3
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from openclaw_installer_core import (
    DEFAULT_SAFE_BASE,
    apply_config_values,
    get_bin_hint,
    install_openclaw,
    resolve_safe_dir,
)


class InstallerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OpenClaw Desktop Installer")
        self.root.geometry("900x620")
        self.root.minsize(820, 540)

        self._init_style()
        self.safe_dir_var = tk.StringVar(value=str(DEFAULT_SAFE_BASE))
        self.status_var = tk.StringVar(value="就绪：请确认安装目录后点击安装")

        # 可视化配置（不让用户去命令行填）
        self.heartbeat_indicator_var = tk.StringVar(value="true")
        self.timezone_var = tk.StringVar(value="Asia/Shanghai")
        self.group_policy_var = tk.StringVar(value="allowlist")
        self.heartbeat_ok_var = tk.StringVar(value="false")

        self._build_ui()

    def _init_style(self) -> None:
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        s.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#555")
        s.configure("Card.TFrame", background="#f8fafc")
        s.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="OpenClaw 可视化一键安装", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Windows / Linux · 安装与配置全在界面内完成 · 默认安全隔离目录",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 10))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)

        page_install = ttk.Frame(notebook, padding=14)
        page_config = ttk.Frame(notebook, padding=14)
        page_logs = ttk.Frame(notebook, padding=14)
        notebook.add(page_install, text="1) 安装")
        notebook.add(page_config, text="2) 配置")
        notebook.add(page_logs, text="3) 日志")

        self._build_install_page(page_install)
        self._build_config_page(page_config)
        self._build_logs_page(page_logs)

        ttk.Label(outer, textvariable=self.status_var, foreground="#0f4c81").pack(anchor="w", pady=(8, 0))

    def _build_install_page(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(6, 8))
        ttk.Label(row, text="安全目录").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.safe_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row, text="浏览", command=self.pick_dir).pack(side=tk.LEFT)

        tips = (
            "安全策略：安装到指定目录，不写全局系统路径。\n"
            "防误操作：禁止根目录/家目录作为安装目录。"
        )
        ttk.Label(parent, text=tips, style="Sub.TLabel").pack(anchor="w", pady=(0, 12))

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X)
        self.install_btn = ttk.Button(btns, text="开始一键安装", style="Primary.TButton", command=self.start_install)
        self.install_btn.pack(side=tk.LEFT)
        ttk.Button(btns, text="复制 PATH 提示", command=self.copy_path_hint).pack(side=tk.LEFT, padx=8)

    def _build_config_page(self, parent: ttk.Frame) -> None:
        grid = ttk.Frame(parent)
        grid.pack(fill=tk.X)

        rows = [
            ("心跳指示器(true/false)", self.heartbeat_indicator_var, "channels.defaults.heartbeat.useIndicator"),
            ("消息时区", self.timezone_var, "agents.defaults.envelopeTimezone"),
            ("群聊默认策略(open/disabled/allowlist)", self.group_policy_var, "channels.defaults.groupPolicy"),
            ("显示心跳OK(true/false)", self.heartbeat_ok_var, "channels.defaults.heartbeat.showOk"),
        ]

        self.config_key_map = {}
        for i, (label, var, key) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=5)
            ttk.Entry(grid, textvariable=var).grid(row=i, column=1, sticky="ew", pady=5, padx=8)
            self.config_key_map[key] = var

        grid.columnconfigure(1, weight=1)

        ttk.Label(
            parent,
            text="点击“写入配置”后会自动执行 openclaw config set（用户无须命令行输入）",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(10, 10))

        self.apply_btn = ttk.Button(parent, text="写入配置", command=self.apply_config)
        self.apply_btn.pack(anchor="w")

    def _build_logs_page(self, parent: ttk.Frame) -> None:
        self.log_text = tk.Text(parent, height=20, bg="#0b1020", fg="#d1e7ff", insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, text: str) -> None:
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def pick_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.safe_dir_var.get() or str(Path.home()))
        if chosen:
            self.safe_dir_var.set(chosen)

    def copy_path_hint(self) -> None:
        try:
            safe_dir = resolve_safe_dir(self.safe_dir_var.get())
            hint = get_bin_hint(safe_dir)
            self.root.clipboard_clear()
            self.root.clipboard_append(hint)
            self.status_var.set("已复制 PATH 目录")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("路径错误", str(e))

    def start_install(self) -> None:
        self.install_btn.config(state=tk.DISABLED)
        self.progress["value"] = 10
        self.status_var.set("安装中...")
        self.log("== [Step 1/2] 开始安装 OpenClaw ==")

        def run() -> None:
            try:
                safe_dir = resolve_safe_dir(self.safe_dir_var.get())
                self.log(f"安全目录: {safe_dir}")
                self.progress["value"] = 35
                result = install_openclaw(safe_dir)
                self.log(f"命令: {' '.join(result.command)}")
                self.log(result.message)
                self.log(f"PATH 提示: {get_bin_hint(safe_dir)}")
                if result.ok:
                    self.progress["value"] = 70
                    self.status_var.set("安装完成，可继续在“配置”页一键写入参数")
                    messagebox.showinfo("安装完成", "OpenClaw 安装成功，请继续写入配置。")
                else:
                    self.progress["value"] = 0
                    self.status_var.set("安装失败")
                    messagebox.showerror("安装失败", result.message)
            except Exception as e:  # noqa: BLE001
                self.log(f"异常: {e}")
                self.progress["value"] = 0
                self.status_var.set("安装异常")
                messagebox.showerror("异常", str(e))
            finally:
                self.install_btn.config(state=tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()

    def apply_config(self) -> None:
        self.apply_btn.config(state=tk.DISABLED)
        self.log("== [Step 2/2] 写入配置 ==")
        self.status_var.set("配置写入中...")

        def run() -> None:
            try:
                safe_dir = resolve_safe_dir(self.safe_dir_var.get())
                payload = {k: v.get() for k, v in self.config_key_map.items()}
                result = apply_config_values(safe_dir, payload)
                self.log(result.message)
                if result.ok:
                    self.progress["value"] = 100
                    self.status_var.set("安装+配置全部完成 ✅")
                    messagebox.showinfo("完成", "全部步骤完成，且无需命令行输入。")
                else:
                    self.status_var.set("配置失败")
                    messagebox.showerror("配置失败", result.message)
            except Exception as e:  # noqa: BLE001
                self.log(f"异常: {e}")
                self.status_var.set("配置异常")
                messagebox.showerror("异常", str(e))
            finally:
                self.apply_btn.config(state=tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
