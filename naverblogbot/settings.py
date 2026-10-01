import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Settings:
    api_key: str = ""
    model: str = "claude-opus-5"
    style_samples: str = ""


def app_dir() -> Path:
    if os.getenv("NAVERBLOGBOT_HOME"):
        return Path(os.environ["NAVERBLOGBOT_HOME"])
    return Path(os.environ["APPDATA"]) / "naverblogbot"


def profile_dir() -> Path:
    if os.getenv("NAVERBLOGBOT_HOME"):
        return Path(os.environ["NAVERBLOGBOT_HOME"]) / "browser-profile"
    return Path(os.environ["LOCALAPPDATA"]) / "naverblogbot" / "browser-profile"


def _default_path() -> Path:
    return app_dir() / "settings.json"


def load(path: Path | None = None) -> Settings:
    path = path or _default_path()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in data.items() if k in known})


def save(s: Settings, path: Path | None = None) -> None:
    path = path or _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(s), ensure_ascii=False, indent=2), encoding="utf-8")
