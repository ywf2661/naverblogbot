import json
from dataclasses import dataclass
from pathlib import Path

import anthropic

from . import history, preview
from .draft import Draft, check, checklist, draft_from_dict, finalize
from .inputs import ReviewInput
from .photos import list_photos
from .settings import Settings, app_dir
from .writer import DraftError, write_draft


@dataclass
class Result:
    draft: Draft
    warnings: list[str]
    checklist: list[str]
    html_path: Path


def make_draft(r: ReviewInput, s: Settings, client, history_path: Path | None = None) -> Result:
    history_path = history_path or app_dir() / "history.json"
    paths = list_photos(r.photo_dir)
    raw = write_draft(client, s.model, r, paths, s.style_samples, history.recent_phrases(history_path))
    d = finalize(raw, r)
    warnings = check(d, r, [p.name for p in paths])
    items = checklist(d, r)
    html_path = preview.save(d, r, warnings, items)
    history.remember(history_path, d)
    return Result(d, warnings, items, html_path)


def load_saved(r: ReviewInput) -> Draft:
    return draft_from_dict(json.loads((Path(r.photo_dir) / "draft.json").read_text(encoding="utf-8")))


def friendly_error(e: Exception) -> str:
    if isinstance(e, DraftError):
        return str(e)
    if isinstance(e, anthropic.AuthenticationError):
        return "API 키가 올바르지 않습니다. 설정에서 키를 다시 입력하세요."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "이 API 키로는 선택한 모델을 쓸 수 없습니다. 설정에서 모델을 확인하세요."
    if isinstance(e, anthropic.RateLimitError):
        return "요청이 많아 잠시 막혔습니다. 1분 뒤 다시 시도하세요."
    if isinstance(e, anthropic.APIConnectionError):
        return "AI 서버에 연결하지 못했습니다. 인터넷 연결이나 회사망 보안 설정을 확인하세요."
    if isinstance(e, anthropic.APIStatusError):
        return f"AI 서버 오류입니다 ({getattr(e, 'status_code', '?')}). 잠시 뒤 다시 시도하세요."
    return f"알 수 없는 오류가 났습니다: {e}"
