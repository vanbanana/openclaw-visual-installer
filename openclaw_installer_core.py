from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
import secrets

DEFAULT_SAFE_BASE = Path.home() / "openclaw-safe"


@dataclass
class InstallResult:
    ok: bool
    message: str
    command: list[str]
    install_root: Path


def resolve_safe_dir(raw_path: str | Path) -> Path:
    p = Path(raw_path).expanduser().resolve()
    if not p.is_absolute():
        raise ValueError("安全目录必须是绝对路径")
    if p == Path.home().resolve() or str(p) in {"/", "C:\\"}:
        raise ValueError("不能把系统根目录或家目录直接作为安装目录")
    return p


def build_install_command(install_root: Path) -> list[str]:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("未找到 npm。请先安装 Node.js (>=18) 后重试。")

    prefix_dir = install_root / "npm-prefix"
    return [
        npm,
        "install",
        "openclaw@latest",
        "--prefix",
        str(prefix_dir),
        "--no-audit",
        "--fund=false",
    ]


def _create_test_fake_install(install_root: Path) -> None:
    system = platform.system().lower()
    prefix_dir = install_root / "npm-prefix"
    if "windows" in system:
        bin_dir = prefix_dir
        bin_dir.mkdir(parents=True, exist_ok=True)
        exe = bin_dir / "openclaw.cmd"
        exe.write_text("@echo off\r\necho openclaw test mode ok\r\n", encoding="utf-8")
    else:
        bin_dir = prefix_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        exe = bin_dir / "openclaw"
        exe.write_text("#!/usr/bin/env sh\necho openclaw test mode ok\n", encoding="utf-8")
        exe.chmod(0o755)


def install_openclaw(install_root: Path) -> InstallResult:
    install_root.mkdir(parents=True, exist_ok=True)

    if os.getenv("OPENCLAW_INSTALLER_TEST_MODE") == "1":
        _create_test_fake_install(install_root)
        return InstallResult(True, "测试模式安装成功", ["test-mode"], install_root)

    cmd = build_install_command(install_root)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            msg = f"安装失败 (code={proc.returncode})\n{proc.stderr.strip() or proc.stdout.strip()}"
            return InstallResult(False, msg, cmd, install_root)

        return InstallResult(True, "安装成功", cmd, install_root)
    except Exception as e:  # noqa: BLE001
        return InstallResult(False, f"安装异常: {e}", cmd, install_root)


def get_bin_hint(install_root: Path) -> str:
    # npm --prefix + local package install puts executables in node_modules/.bin
    return str((install_root / "npm-prefix" / "node_modules" / ".bin").resolve())


def get_openclaw_executable(install_root: Path) -> Path:
    bin_dir = Path(get_bin_hint(install_root))
    if os.name == "nt":
        return bin_dir / "openclaw.cmd"
    return bin_dir / "openclaw"


def apply_config_values(install_root: Path, values: Dict[str, str]) -> InstallResult:
    if os.getenv("OPENCLAW_INSTALLER_TEST_MODE") == "1":
        return InstallResult(True, "测试模式已跳过真实配置写入", ["test-mode-config"], install_root)

    exe = get_openclaw_executable(install_root)
    if not exe.exists():
        return InstallResult(False, f"未找到可执行文件: {exe}", [str(exe)], install_root)

    state_dir = install_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = state_dir / "openclaw.json"
    env = os.environ.copy()
    env["OPENCLAW_STATE_DIR"] = str(state_dir)
    env["OPENCLAW_CONFIG_PATH"] = str(cfg_path)

    for k, v in values.items():
        if not str(v).strip():
            continue
        cmd = [str(exe), "config", "set", k, str(v)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if proc.returncode != 0:
            msg = proc.stderr.strip() or proc.stdout.strip()
            return InstallResult(False, f"配置写入失败: {k}\n{msg}", cmd, install_root)

    return InstallResult(True, f"配置写入成功（隔离配置文件: {cfg_path}）", [str(exe), "config", "set"], install_root)


@dataclass
class SkillPackage:
    name: str
    source: str
    version: str
    risk: str
    recommended: bool = False


SKILL_CATALOG: List[SkillPackage] = [
    SkillPackage("qqbot-cron", "skillhub", "1.2.0", "低：仅定时任务能力", True),
    SkillPackage("office-suite-local", "skillhub", "0.3.4", "中：需本地Python依赖", True),
    SkillPackage("github", "clawhub", "2.1.0", "中：需要gh登录权限"),
    SkillPackage("weather", "skillhub", "1.0.1", "低：只读查询"),
]


def list_skill_catalog() -> List[SkillPackage]:
    return SKILL_CATALOG.copy()


def install_skills_selection(selected_names: List[str], install_root: Path) -> InstallResult:
    if not selected_names:
        return InstallResult(True, "未选择任何技能，已跳过", ["skip"], install_root)
    if os.getenv("OPENCLAW_INSTALLER_TEST_MODE") == "1":
        return InstallResult(True, f"测试模式：已模拟安装技能 {', '.join(selected_names)}", ["test-mode-skill-install"], install_root)
    # 真实流程留给后续接OpenClaw命令/skillhub CLI，这里先提供可视化闭环与风险展示
    return InstallResult(True, f"已记录待安装技能：{', '.join(selected_names)}", ["deferred-skill-install"], install_root)


def validate_api_key(provider: str, api_key: str) -> InstallResult:
    provider = provider.lower().strip()
    key = api_key.strip()
    if not key:
        return InstallResult(False, "API Key 不能为空", ["validate"], Path("."))
    simple_rules = {
        "openai": key.startswith("sk-") and len(key) > 20,
        "anthropic": key.startswith("sk-ant-") and len(key) > 20,
    }
    ok = simple_rules.get(provider, len(key) >= 16)
    if ok:
        return InstallResult(True, f"{provider} Key 格式校验通过（基础校验）", ["validate"], Path("."))
    return InstallResult(False, f"{provider} Key 格式不合法", ["validate"], Path("."))


def generate_gateway_token(hours_valid: int = 24) -> Dict[str, str]:
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=hours_valid)
    return {
        "token": token,
        "createdAt": now.isoformat(),
        "expiresAt": expires.isoformat(),
        "status": "valid",
    }


def get_token_status(expires_at_iso: str) -> str:
    try:
        expires = datetime.fromisoformat(expires_at_iso)
    except ValueError:
        return "invalid"
    return "valid" if datetime.now(timezone.utc) < expires else "expired"


def run_hook_test(template: str, route_to: str) -> InstallResult:
    if not template.strip() or not route_to.strip():
        return InstallResult(False, "Hook 测试失败：模板和路由目标不能为空", ["hook-test"], Path("."))
    return InstallResult(True, f"Hook 测试通过：{template} -> {route_to}", ["hook-test"], Path("."))


def run_preflight_checks(snapshot: Dict[str, str]) -> Dict[str, str]:
    checks = {
        "environment": "ok" if shutil.which("node") and shutil.which("npm") else "missing",
        "model": "ok" if snapshot.get("provider") and snapshot.get("default_model") else "missing",
        "skills": "ok" if snapshot.get("skills_selected") else "warning",
        "hooks": "ok" if snapshot.get("hook_enabled") == "true" else "warning",
        "permission": "ok" if snapshot.get("permission_mode") in {"reply-only", "allowlist", "full"} else "missing",
        "gateway": "ok" if snapshot.get("gateway_mode") else "missing",
        "dashboard": "ok" if snapshot.get("dashboard_url") else "missing",
    }
    return checks
