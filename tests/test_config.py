import os
from app.config import get_settings


def test_get_settings_reads_env(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("RICHPANEL_API_TOKEN", "rp-test")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DRY_RUN", "true")
    s = get_settings()
    assert s.anthropic_api_key == "sk-test"
    assert s.richpanel_api_token == "rp-test"
    assert s.dry_run is True
    assert s.host == "127.0.0.1"
    assert s.port == 8788
