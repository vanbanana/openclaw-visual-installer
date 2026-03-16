import os
from pathlib import Path

import openclaw_installer_core as app


def test_resolve_safe_dir_absolute(tmp_path: Path):
    p = app.resolve_safe_dir(tmp_path)
    assert p == tmp_path.resolve()


def test_resolve_safe_dir_reject_home():
    try:
        app.resolve_safe_dir(Path.home())
    except ValueError as e:
        assert "家目录" in str(e)
    else:
        raise AssertionError("Expected ValueError for home directory")


def test_test_mode_install_no_side_effect(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_INSTALLER_TEST_MODE", "1")
    res = app.install_openclaw(tmp_path)
    assert res.ok

    if os.name == "nt":
        expected = tmp_path / "npm-prefix" / "openclaw.cmd"
    else:
        expected = tmp_path / "npm-prefix" / "bin" / "openclaw"

    assert expected.exists(), f"Expected fake binary at {expected}"


def test_bin_hint_path(tmp_path: Path):
    hint = app.get_bin_hint(tmp_path)
    assert "npm-prefix" in hint


def test_apply_config_in_test_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_INSTALLER_TEST_MODE", "1")
    app.install_openclaw(tmp_path)
    r = app.apply_config_values(tmp_path, {"models.default": "x"})
    assert r.ok


def test_skill_catalog_and_install(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_INSTALLER_TEST_MODE", "1")
    items = app.list_skill_catalog()
    assert len(items) >= 1
    res = app.install_skills_selection([items[0].name], tmp_path)
    assert res.ok


def test_validate_api_key_basic():
    ok = app.validate_api_key("openai", "sk-abcdefghijklmnopqrstuvwxyz")
    bad = app.validate_api_key("openai", "abc")
    assert ok.ok is True
    assert bad.ok is False


def test_gateway_token_status():
    token = app.generate_gateway_token(1)
    assert token["status"] == "valid"
    assert app.get_token_status(token["expiresAt"]) == "valid"


def test_preflight_checks():
    checks = app.run_preflight_checks(
        {
            "provider": "openai",
            "default_model": "gpt-5.3-codex",
            "skills_selected": "qqbot-cron",
            "hook_enabled": "true",
            "permission_mode": "allowlist",
            "gateway_mode": "local",
            "dashboard_url": "http://127.0.0.1:18789/dashboard",
        }
    )
    assert checks["model"] == "ok"
    assert checks["permission"] == "ok"
