"""Regression: secrets copied from a Windows .env carried a trailing \\r\\n into Cloud Run, and
Google rejected GOOGLE_CLIENT_ID as an unknown client (invalid_client). Every setting is read
through config.env(), which strips surrounding whitespace."""

import importlib

import pytest

import app.config as config


def test_env_strips_crlf_and_spaces(monkeypatch):
    monkeypatch.setenv("SPA_TEST_VALUE", "  abc.apps.googleusercontent.com\r\n")
    assert config.env("SPA_TEST_VALUE") == "abc.apps.googleusercontent.com"


def test_env_default_when_unset(monkeypatch):
    monkeypatch.delenv("SPA_TEST_MISSING", raising=False)
    assert config.env("SPA_TEST_MISSING", "fallback") == "fallback"
    assert config.env("SPA_TEST_MISSING") == ""


@pytest.fixture
def reloaded_config(monkeypatch):
    """Re-import config under a patched environment, then restore the original module state."""

    def load(**values):
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(config)

    yield load
    monkeypatch.undo()
    importlib.reload(config)


def test_settings_read_from_env_have_no_line_endings(reloaded_config):
    cfg = reloaded_config(
        GOOGLE_CLIENT_ID="cid.apps.googleusercontent.com\r\n",
        GOOGLE_CLIENT_SECRET="secret-value\r\n",
        SESSION_SECRET="s" * 32 + "\n",
        S3_REGION="auto\r\n",
        MAX_ACTIVE_JOBS_PER_USER="3\r\n",  # numbers parse too
    )
    settings = cfg.load_settings()
    assert settings.google_client_id == "cid.apps.googleusercontent.com"
    assert settings.google_client_secret == "secret-value"
    assert settings.session_secret == "s" * 32
    assert settings.s3_region == "auto"
    assert settings.max_active_jobs_per_user == 3
