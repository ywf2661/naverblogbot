import json
from dataclasses import dataclass
from pathlib import Path

import anthropic

from . import history, preview
from .draft import Draft, check, checklist, draft_from_dict, finalize
from .inputs import ReviewInput
from .lookup import PlaceInfo, lookup_place
from .photos import list_media
from .settings import Settings, app_dir
from .writer import DraftError, write_draft


@dataclass
class Result:
    draft: Draft
    warnings: list[str]
    checklist: list[str]
    html_path: Path


def make_draft(r: ReviewInput, s: Settings, client, history_path: Path | None = None,
               lookup: bool = True, log=lambda m: None) -> Result:
    history_path = history_path or app_dir() / "history.json"
    pre_warnings: list[str] = []
    place = PlaceInfo()
    if lookup and not r.extra.strip():  # 직접 입력한 정보가 있으면 검색하지 않는다
        log("영업시간·주차 검색 중... (1~2분)")
        try:
            place = lookup_place(client, s.model, r.store, r.area)
        except Exception as e:
            pre_warnings.append(f"영업시간·주차 자동 검색에 실패해 빼고 썼습니다: {friendly_error(e)}")
    log("초안 쓰는 중... (1~2분)")
    paths = list_media(r.photo_dir)
    raw = write_draft(client, s.model, r, paths, s.style_samples, history.recent_phrases(history_path), place=place)
    d = finalize(raw, r)
    warnings = pre_warnings + check(d, r, [p.name for p in paths])
    items = checklist(d, r)
    if place.found:
        sources = " ".join(place.sources[:3])
        items.insert(0, f"검색으로 찾은 정보({place.memo()})가 지금도 맞는지 확인하세요. 출처: {sources}")
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
    if isinstance(e, anthropic.NotFoundError):
        return "모델 이름을 찾을 수 없습니다. 설정에서 모델 이름을 확인하세요."
    if isinstance(e, anthropic.APIStatusError):
        status = getattr(e, "status_code", 0) or 0
        message = getattr(e, "message", "") or ""
        if "credit balance" in message:
            return "API 사용 잔액이 부족합니다. Anthropic 콘솔에서 결제 수단·잔액을 확인하세요."
        if 400 <= status < 500:
            return f"AI 서버가 요청을 받아들이지 않았습니다 ({status}): {message}"
        return f"AI 서버 오류입니다 ({status}). 잠시 뒤 다시 시도하세요."
    return f"알 수 없는 오류가 났습니다: {e}"
