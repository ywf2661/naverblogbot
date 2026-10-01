import json
from pathlib import Path

from .draft import Draft


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def remember(path: Path, d: Draft, keep: int = 3) -> None:
    lines = [x for b in d.blocks for x in b.lines]
    entries = (_load(path) + [{"first": lines[:3], "last": lines[-3:]}])[-keep:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def recent_phrases(path: Path) -> list[str]:
    return [x for e in _load(path) for x in e["first"] + e["last"]]
