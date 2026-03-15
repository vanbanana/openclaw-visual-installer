from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

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
        if not v.strip():
            continue
        cmd = [str(exe), "config", "set", k, v]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if proc.returncode != 0:
            msg = proc.stderr.strip() or proc.stdout.strip()
            return InstallResult(False, f"配置写入失败: {k}\n{msg}", cmd, install_root)

    return InstallResult(True, f"配置写入成功（隔离配置文件: {cfg_path}）", [str(exe), "config", "set"], install_root)
