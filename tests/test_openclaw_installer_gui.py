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
    # prepare fake executable in test mode
    app.install_openclaw(tmp_path)
    r = app.apply_config_values(tmp_path, {"models.default": "x"})
    assert r.ok
