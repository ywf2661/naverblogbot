from naverblogbot import settings


def test_app_dir_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVERBLOGBOT_HOME", str(tmp_path))
    assert settings.app_dir() == tmp_path
    assert settings.profile_dir() == tmp_path / "chrome-profile"


def test_load_missing_returns_defaults(tmp_path):
    s = settings.load(tmp_path / "settings.json")
    assert s.api_key == ""
    assert s.model == "claude-opus-5"


def test_save_then_load_roundtrip_korean(tmp_path):
    p = tmp_path / "sub" / "settings.json"
    settings.save(settings.Settings(api_key="sk-x", model="claude-sonnet-5", style_samples="안녕하세요~"), p)
    s = settings.load(p)
    assert (s.api_key, s.model, s.style_samples) == ("sk-x", "claude-sonnet-5", "안녕하세요~")


def test_load_ignores_unknown_keys(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"api_key": "k", "old_field": 1}', encoding="utf-8")
    assert settings.load(p).api_key == "k"
