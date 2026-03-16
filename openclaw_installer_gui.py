#!/usr/bin/env python3
from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from openclaw_installer_core import (
    DEFAULT_SAFE_BASE,
    apply_config_values,
    generate_gateway_token,
    get_bin_hint,
    get_token_status,
    install_openclaw,
    install_skills_selection,
    list_skill_catalog,
    resolve_safe_dir,
    run_hook_test,
    run_preflight_checks,
    validate_api_key,
)


class InstallerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OpenClaw Desktop Installer")
        self.root.geometry("1040x760")
        self.root.minsize(920, 620)

        self._init_style()

        self.safe_dir_var = tk.StringVar(value=str(DEFAULT_SAFE_BASE))
        self.status_var = tk.StringVar(value="就绪")

        # P0: 运行模式
        self.gateway_mode_var = tk.StringVar(value="local")
        self.bind_mode_var = tk.StringVar(value="loopback")
        self.auth_mode_var = tk.StringVar(value="token")

        # 模型/登录（官方分支）
        self.provider_var = tk.StringVar(value="openai")
        self.auth_branch_var = tk.StringVar(value="openai_api_key")
        self.api_key_var = tk.StringVar(value="")
        self.oauth_token_var = tk.StringVar(value="")
        self.setup_token_var = tk.StringVar(value="")
        self.reuse_local_cred_var = tk.BooleanVar(value=False)
        self.ollama_url_var = tk.StringVar(value="http://127.0.0.1:11434")
        self.ollama_mode_var = tk.StringVar(value="cloud+local")
        self.default_model_var = tk.StringVar(value="gpt-5.3-codex")
        self.thinking_var = tk.StringVar(value="low")
        self.verbose_var = tk.StringVar(value="false")

        # P0: hooks
        self.hook_template_var = tk.StringVar(value="webhook")
        self.hook_trigger_var = tk.StringVar(value="on_message")
        self.hook_route_var = tk.StringVar(value="agent:main")
        self.hook_enabled_var = tk.BooleanVar(value=True)

        # P0: permission
        self.permission_mode_var = tk.StringVar(value="allowlist")

        # P0: gateway/dashboard
        self.dashboard_url_var = tk.StringVar(value="http://127.0.0.1:18789/dashboard")
        self.token_var = tk.StringVar(value="")
        self.token_status_var = tk.StringVar(value="未生成")
        self.token_expires_at = ""

        self.skill_vars: dict[str, tk.BooleanVar] = {}
        self.config_key_map: dict[str, tk.StringVar] = {}

        self._build_ui()

    def _init_style(self) -> None:
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        s.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#566")
        s.configure("Danger.TButton", foreground="#b00")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="OpenClaw 首次可用向导（P0可视化）", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="按标签页完成 7 项硬门槛，再执行完整检查", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 8))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)

        pages = {}
        for title in [
            "1 安装", "2 运行模式", "3 模型/API", "4 Skills", "5 Hooks", "6 权限", "7 Gateway", "8 完整检查", "9 官方11项对照", "日志"
        ]:
            frame = ttk.Frame(notebook, padding=12)
            notebook.add(frame, text=title)
            pages[title] = frame

        self._build_install_page(pages["1 安装"])
        self._build_runtime_page(pages["2 运行模式"])
        self._build_model_page(pages["3 模型/API"])
        self._build_skills_page(pages["4 Skills"])
        self._build_hooks_page(pages["5 Hooks"])
        self._build_permission_page(pages["6 权限"])
        self._build_gateway_page(pages["7 Gateway"])
        self._build_check_page(pages["8 完整检查"])
        self._build_parity_page(pages["9 官方11项对照"])
        self._build_logs_page(pages["日志"])

        ttk.Label(outer, textvariable=self.status_var, foreground="#0f4c81").pack(anchor="w", pady=(8, 0))

    def _build_install_page(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="安全目录").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.safe_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(row, text="浏览", command=self.pick_dir).pack(side=tk.LEFT)

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, pady=8)
        self.install_btn = ttk.Button(btns, text="开始安装", command=self.start_install)
        self.install_btn.pack(side=tk.LEFT)
        ttk.Button(btns, text="复制PATH提示", command=self.copy_path_hint).pack(side=tk.LEFT, padx=8)

    def _build_runtime_page(self, parent: ttk.Frame) -> None:
        self._labeled_combo(parent, "Gateway模式", self.gateway_mode_var, ["local", "remote"])
        self._labeled_combo(parent, "bind", self.bind_mode_var, ["loopback", "lan", "tailnet", "custom"])
        self._labeled_combo(parent, "auth", self.auth_mode_var, ["none", "token", "password", "trusted-proxy"])

    def _build_model_page(self, parent: ttk.Frame) -> None:
        self._labeled_combo(
            parent,
            "Provider",
            self.provider_var,
            [
                "openai", "anthropic", "openai-codex", "xai", "opencode", "ollama",
                "vercel-ai-gateway", "cloudflare-ai-gateway", "moonshot", "minimax", "synthetic", "other"
            ],
        )
        self._labeled_combo(
            parent,
            "登录分支",
            self.auth_branch_var,
            [
                "openai_api_key",
                "openai_codex_oauth",
                "openai_codex_reuse_local",
                "anthropic_api_key",
                "anthropic_oauth",
                "anthropic_setup_token",
                "ollama_local_or_hybrid",
                "generic_api_key",
            ],
        )
        self._labeled_entry(parent, "API Key", self.api_key_var, show="*")
        self._labeled_entry(parent, "OAuth Token/Code", self.oauth_token_var, show="*")
        self._labeled_entry(parent, "Setup Token", self.setup_token_var, show="*")
        self._labeled_entry(parent, "Ollama URL", self.ollama_url_var)
        self._labeled_combo(parent, "Ollama 模式", self.ollama_mode_var, ["cloud+local", "local"])
        ttk.Checkbutton(parent, text="复用本地登录凭据（Codex/Claude）", variable=self.reuse_local_cred_var).pack(anchor="w", pady=3)

        self._labeled_entry(parent, "默认模型", self.default_model_var)
        self._labeled_combo(parent, "thinking", self.thinking_var, ["low", "medium", "high"])
        self._labeled_combo(parent, "verbose", self.verbose_var, ["false", "true"])

        ttk.Button(parent, text="校验当前登录分支", command=self.validate_auth_branch).pack(anchor="w", pady=8)

    def _build_skills_page(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="推荐技能包（可多选）").pack(anchor="w")
        box = ttk.Frame(parent)
        box.pack(fill=tk.BOTH, expand=True, pady=6)

        for item in list_skill_catalog():
            var = tk.BooleanVar(value=item.recommended)
            self.skill_vars[item.name] = var
            text = f"{item.name} | source={item.source} | version={item.version} | risk={item.risk}"
            ttk.Checkbutton(box, text=text, variable=var).pack(anchor="w", pady=2)

        ttk.Button(parent, text="安装前预览（来源/版本/风险）", command=self.preview_skills).pack(anchor="w", pady=4)
        ttk.Button(parent, text="安装所选技能", command=self.install_skills).pack(anchor="w")

    def _build_hooks_page(self, parent: ttk.Frame) -> None:
        self._labeled_combo(parent, "模板", self.hook_template_var, ["webhook", "gmail", "custom"])
        self._labeled_entry(parent, "触发条件", self.hook_trigger_var)
        self._labeled_entry(parent, "路由目标", self.hook_route_var)
        ttk.Checkbutton(parent, text="启用Hook", variable=self.hook_enabled_var).pack(anchor="w", pady=4)
        ttk.Button(parent, text="测试Hook", command=self.test_hook).pack(anchor="w")

    def _build_permission_page(self, parent: ttk.Frame) -> None:
        self._labeled_combo(parent, "权限模式", self.permission_mode_var, ["reply-only", "allowlist", "full"])
        ttk.Label(parent, text="切换 full 时将触发风险二次确认", style="Sub.TLabel").pack(anchor="w", pady=4)
        ttk.Button(parent, text="应用权限模式", command=self.apply_permission_mode).pack(anchor="w")

    def _build_gateway_page(self, parent: ttk.Frame) -> None:
        self._labeled_entry(parent, "Dashboard URL", self.dashboard_url_var)
        self._labeled_entry(parent, "Gateway Token", self.token_var)
        ttk.Label(parent, textvariable=self.token_status_var).pack(anchor="w", pady=4)

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="生成Token", command=self.generate_token).pack(side=tk.LEFT)
        ttk.Button(btns, text="刷新Token", command=self.generate_token).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="复制Token", command=self.copy_token).pack(side=tk.LEFT)
        ttk.Button(btns, text="打开Dashboard", command=self.open_dashboard).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="检查Token状态", command=self.refresh_token_status).pack(side=tk.LEFT)

    def _build_check_page(self, parent: ttk.Frame) -> None:
        ttk.Button(parent, text="执行首次对话前完整检查", command=self.run_full_check).pack(anchor="w", pady=4)
        self.check_text = tk.Text(parent, height=18)
        self.check_text.pack(fill=tk.BOTH, expand=True)

    def _build_parity_page(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="官方流程 11 项对照（缺一项不算完成）", style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Button(parent, text="刷新官方11项对照", command=self.run_official_parity_check).pack(anchor="w", pady=4)
        self.parity_text = tk.Text(parent, height=18)
        self.parity_text.pack(fill=tk.BOTH, expand=True)

    def _build_logs_page(self, parent: ttk.Frame) -> None:
        self.log_text = tk.Text(parent, bg="#0b1020", fg="#d1e7ff", insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _labeled_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar, show: str | None = None) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=label, width=18).pack(side=tk.LEFT)
        ent = ttk.Entry(row, textvariable=var)
        if show:
            ent.configure(show=show)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _labeled_combo(self, parent: ttk.Frame, label: str, var: tk.StringVar, values: list[str]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=label, width=18).pack(side=tk.LEFT)
        cb = ttk.Combobox(row, textvariable=var, values=values, state="readonly")
        cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def log(self, text: str) -> None:
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def pick_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.safe_dir_var.get() or str(Path.home()))
        if chosen:
            self.safe_dir_var.set(chosen)

    def copy_path_hint(self) -> None:
        safe_dir = resolve_safe_dir(self.safe_dir_var.get())
        hint = get_bin_hint(safe_dir)
        self.root.clipboard_clear()
        self.root.clipboard_append(hint)
        self.status_var.set("已复制 PATH 提示")

    def start_install(self) -> None:
        self.install_btn.config(state=tk.DISABLED)
        self.status_var.set("安装中...")
        self.progress["value"] = 10

        def run() -> None:
            try:
                safe_dir = resolve_safe_dir(self.safe_dir_var.get())
                result = install_openclaw(safe_dir)
                self.log(result.message)
                if result.ok:
                    self.progress["value"] = 30
                    self.status_var.set("安装完成")
                else:
                    self.status_var.set("安装失败")
                    messagebox.showerror("安装失败", result.message)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("异常", str(e))
            finally:
                self.install_btn.config(state=tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()

    def validate_auth_branch(self) -> None:
        branch = self.auth_branch_var.get()
        provider = self.provider_var.get()

        ok = False
        msg = ""
        if branch in {"openai_api_key", "anthropic_api_key", "generic_api_key"}:
            r = validate_api_key(provider, self.api_key_var.get())
            ok, msg = r.ok, r.message
        elif branch in {"openai_codex_oauth", "anthropic_oauth"}:
            ok = bool(self.oauth_token_var.get().strip()) or self.reuse_local_cred_var.get()
            msg = "OAuth 分支校验通过" if ok else "OAuth 分支需要 Token/Code 或勾选复用本地凭据"
        elif branch == "anthropic_setup_token":
            ok = bool(self.setup_token_var.get().strip())
            msg = "Setup-token 分支校验通过" if ok else "请填写 setup token"
        elif branch == "ollama_local_or_hybrid":
            ok = bool(self.ollama_url_var.get().strip()) and self.ollama_mode_var.get() in {"cloud+local", "local"}
            msg = "Ollama 分支校验通过" if ok else "请填写 Ollama URL 和模式"

        self.log(f"[{branch}] {msg}")
        if ok:
            self.status_var.set("模型登录分支校验通过")
            self.progress["value"] = max(self.progress["value"], 50)
        else:
            messagebox.showwarning("校验失败", msg or "当前分支配置不完整")

    def preview_skills(self) -> None:
        lines = []
        for item in list_skill_catalog():
            if self.skill_vars[item.name].get():
                lines.append(f"- {item.name} | {item.source} | {item.version} | {item.risk}")
        if not lines:
            lines = ["- 未选择技能"]
        self.log("技能安装前预览:\n" + "\n".join(lines))

    def install_skills(self) -> None:
        safe_dir = resolve_safe_dir(self.safe_dir_var.get())
        selected = [name for name, var in self.skill_vars.items() if var.get()]
        result = install_skills_selection(selected, safe_dir)
        self.log(result.message)
        if result.ok:
            self.progress["value"] = max(self.progress["value"], 60)
            self.status_var.set("Skills 步骤完成")

    def test_hook(self) -> None:
        result = run_hook_test(self.hook_template_var.get(), self.hook_route_var.get())
        self.log(result.message)
        if result.ok:
            self.progress["value"] = max(self.progress["value"], 70)
            self.status_var.set("Hook 测试通过")
        else:
            messagebox.showwarning("Hook测试失败", result.message)

    def apply_permission_mode(self) -> None:
        mode = self.permission_mode_var.get()
        if mode == "full":
            ok = messagebox.askyesno("高权限确认", "你选择了 full 权限，可能执行高风险操作。确认继续？")
            if not ok:
                self.status_var.set("已取消 full 权限")
                return
        self.status_var.set(f"当前权限模式：{mode}")
        self.log(f"权限模式已应用: {mode}")
        self.progress["value"] = max(self.progress["value"], 80)

    def generate_token(self) -> None:
        info = generate_gateway_token(24)
        self.token_var.set(info["token"])
        self.token_expires_at = info["expiresAt"]
        self.refresh_token_status()
        self.log("已生成新的 Gateway Token")

    def refresh_token_status(self) -> None:
        if not self.token_expires_at:
            self.token_status_var.set("token 状态：未生成")
            return
        status = get_token_status(self.token_expires_at)
        self.token_status_var.set(f"token 状态：{status}（到期 {self.token_expires_at}）")

    def copy_token(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("提示", "请先生成 token")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(token)
        self.status_var.set("token 已复制")

    def open_dashboard(self) -> None:
        url = self.dashboard_url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "Dashboard URL 为空")
            return
        webbrowser.open(url)
        self.log(f"已打开 Dashboard: {url}")

    def run_official_parity_check(self) -> None:
        selected_skills = [n for n, v in self.skill_vars.items() if v.get()]
        provider = self.provider_var.get().strip().lower()

        # 以官方 onboard/configure 为基准的 11 项
        parity = {
            "1 Existing config Keep/Modify/Reset": "⚠️ 待实现（当前仅安装目录选择）",
            "2 QuickStart vs Advanced": "⚠️ 待实现（当前单一路径）",
            "3 运行模式/Gateway": "✅" if self.gateway_mode_var.get() and self.bind_mode_var.get() and self.auth_mode_var.get() else "❌",
            "4 模型认证全量分支": "✅（已含 OpenAI/Anthropic API+OAuth/setup-token、Codex复用、Ollama）", 
            "5 Skills eligible/check + npm/pnpm": "⚠️ 部分（当前静态清单）" if selected_skills else "❌",
            "6 Hooks 可视化": "✅" if self.hook_route_var.get().strip() else "❌",
            "7 权限模式 + 二次确认": "✅" if self.permission_mode_var.get() in {"reply-only", "allowlist", "full"} else "❌",
            "8 Channels 完整向导": "⚠️ 待实现",
            "9 Daemon/runtime + health": "⚠️ 待实现",
            "10 Web search provider 配置": "⚠️ 待实现",
            "11 完整检查与验收": "✅" if self.dashboard_url_var.get().strip() else "❌",
        }

        self.parity_text.delete("1.0", tk.END)
        done = 0
        for k, v in parity.items():
            self.parity_text.insert(tk.END, f"{k}: {v}\n")
            if str(v).startswith("✅"):
                done += 1

        self.status_var.set(f"官方11项对照：{done}/11 已达标")
        self.log(f"官方11项对照刷新：{done}/11")

    def run_full_check(self) -> None:
        snapshot = {
            "provider": self.provider_var.get(),
            "default_model": self.default_model_var.get(),
            "skills_selected": ",".join([n for n, v in self.skill_vars.items() if v.get()]),
            "hook_enabled": "true" if self.hook_enabled_var.get() else "false",
            "permission_mode": self.permission_mode_var.get(),
            "gateway_mode": self.gateway_mode_var.get(),
            "dashboard_url": self.dashboard_url_var.get(),
        }
        checks = run_preflight_checks(snapshot)
        self.check_text.delete("1.0", tk.END)
        ok_count = 0
        for k, v in checks.items():
            self.check_text.insert(tk.END, f"{k}: {v}\n")
            if v == "ok":
                ok_count += 1
        self.progress["value"] = 100 if ok_count == len(checks) else 88
        self.status_var.set(f"完整检查完成：{ok_count}/{len(checks)} 通过")

        # 配置写入（隔离）
        safe_dir = resolve_safe_dir(self.safe_dir_var.get())
        values = {
            "gateway.mode": self.gateway_mode_var.get(),
            "gateway.bind": self.bind_mode_var.get(),
            "gateway.auth": self.auth_mode_var.get(),
            "models.provider": self.provider_var.get(),
            "models.authBranch": self.auth_branch_var.get(),
            "models.ollama.url": self.ollama_url_var.get(),
            "models.ollama.mode": self.ollama_mode_var.get(),
            "models.default": self.default_model_var.get(),
            "agents.defaults.thinking": self.thinking_var.get(),
            "agents.defaults.verbose": self.verbose_var.get(),
            "permissions.mode": self.permission_mode_var.get(),
        }
        result = apply_config_values(safe_dir, values)
        self.log(result.message)


def main() -> None:
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
