import base64
import json
from pathlib import Path

from .draft import Draft, draft_from_dict
from .inputs import ReviewInput
from .photos import api_jpeg

_BLOCK = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["quote", "lines", "photo", "map", "blank"]},
        "text": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "file": {"type": "string"},
    },
    "required": ["type", "text", "lines", "file"],
    "additionalProperties": False,
}
_PHOTO = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "kind": {"type": "string", "enum": ["exterior", "interior", "menu", "food", "other"]},
        "has_face": {"type": "boolean"},
    },
    "required": ["file", "kind", "has_face"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}},
        "blocks": {"type": "array", "items": _BLOCK},
        "tags": {"type": "array", "items": {"type": "string"}},
        "photos": {"type": "array", "items": _PHOTO},
        "confirm": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titles", "blocks", "tags", "photos", "confirm"],
    "additionalProperties": False,
}

_RULES = """너는 네이버 블로그 맛집 후기 초안을 쓰는 보조 작가다. 사용자가 준 사진과 메모만으로 초안을 쓰고, 사용자가 발행 전에 직접 검토하고 고친다.

사실 규칙
- 맛, 양, 온도, 친절도, 가격, 영업시간, 웨이팅, 주차는 메모에 있는 것만 쓴다. 메모에 없으면 언급하지 않는다.
- 사진에서 보이는 것(색, 담음새, 재료, 실내 모습, 간판 글자)은 묘사해도 된다.
- 메뉴판 사진에서 읽은 메뉴명·가격은 본문에 「확인: 돈가스 12,000원」처럼 표시하고 confirm 목록에 같은 문구(「확인:」 뒤 내용)를 넣는다. 메모에 메뉴·가격이 있으면 메모를 따르고 표시하지 않는다.
- 메모에 없는 감정, 동행인, 방문 계기, 추천 대상, 아쉬운 점을 지어내지 않는다.
- 광고·협찬 문구는 쓰지 않는다. 프로그램이 따로 넣는다.

구성 (blocks 순서)
1. 도입: lines 2~4줄로 가게와 방문 상황 소개.
2. quote "📍 위치·정보" → lines(가게명, 동네, 메모에 있는 영업시간·주차·웨이팅) → map
3. 외관·내부 사진 → 사진마다 lines 2~6줄
4. 메뉴 quote → 메뉴판 사진 → lines
5. 음식 사진들 → 사진마다 lines 2~6줄
6. 총평 quote → lines: 추천 대상은 "✔"로 시작하는 줄, 아쉬운 점·재방문 의사는 메모에 있을 때만
- 사진 순서는 외관 → 내부 → 메뉴판 → 음식이 기본이고, 같은 종류는 주어진 순서를 따른다.
- 모든 사진을 정확히 한 번씩 photo 블록으로 배치한다. file 값은 주어진 파일명 그대로.
- map 블록은 한 번만 쓴다.
- 쓰지 않는 필드는 빈 문자열이나 빈 배열로 둔다.

줄과 문단
- lines의 한 줄은 구절 단위로 끊은 14~20자, 최대 22자(공백 포함). 한 문장을 여러 줄에 나눠도 된다.
- 문단 사이에는 blank 블록을 넣는다. lines 블록 하나는 2~4줄.
- 본문 글자 수(공백 제외)는 1,500~2,300자. 캠페인 가이드에 글자 수가 있으면 그것을 따른다. 분량을 채우려고 같은 말을 반복하지 않는다. 재료가 부족하면 짧게 쓴다.

말투
- 기본은 "~요" 체, 가끔 "~다"를 섞는다. "ㅎㅎ"는 글 전체에서 2번 이하.
- 이모지는 글 전체 5~10개, quote 소제목 앞과 ✔ 줄에만 쓴다.
- "맛있어요" 같은 일반적인 칭찬만 반복하지 말고 사진과 메모의 구체적인 디테일을 쓴다.
- 메모의 "피할 문장"과 같은 문장을 쓰지 않는다.

제목 titles 3개
- 각 30~45자. "동네+맛집 키워드 → 가게명(+지점) → 대표 메뉴 → 후기/솔직후기/재방문 같은 수식어" 순서.
- 필수 키워드가 있으면 3개 모두에 자연스럽게 넣는다.

태그 tags 10~20개
- # 없이 쓴다. 절반 이상은 동네명 조합(예: 판교맛집, 판교역맛집, 판교점심, 판교수육). 가게명, 가게명+지점, 메모에 근거한 상황(데이트, 회식, 혼밥 등).
- 필수 키워드가 있으면 모두 포함한다.

photos 목록
- 모든 사진마다 kind(exterior/interior/menu/food/other)와 has_face(알아볼 수 있는 사람 얼굴이 있으면 true)."""


class DraftError(Exception):
    pass


def build_system(style_samples: str) -> str:
    if not style_samples.strip():
        return _RULES
    return (_RULES + "\n\n내 말투\n- 아래는 사용자가 직접 쓴 글이다. 어미, 문장 길이, 말버릇을 따르고 내용은 가져오지 않는다.\n"
            f"<내 글 예시>\n{style_samples.strip()}\n</내 글 예시>")


def build_user_content(r: ReviewInput, photo_paths: list[Path], avoid: list[str]) -> list[dict]:
    visit = f"협찬 ({r.sponsor})" if r.sponsored else "내돈내산"
    memo = "\n".join([
        f"가게명: {r.store}",
        f"동네: {r.area}",
        f"방문 유형: {visit}",
        f"한 줄 소감: {r.impression}",
        f"먹은 메뉴·가격: {r.menu or '(없음 — 메뉴판 사진에서 읽고 확인 표시)'}",
        f"아쉬운 점: {r.cons or '(없음 — 쓰지 말 것)'}",
        f"추천 대상: {r.target or '(없음 — 쓰지 말 것)'}",
        f"웨이팅·주차·영업시간: {r.extra or '(없음 — 쓰지 말 것)'}",
        f"필수 키워드: {', '.join(r.keyword_list) or '(없음)'}",
        f"캠페인 가이드: {r.guide or '(없음)'}",
        "피할 문장: " + (" / ".join(avoid) if avoid else "(없음)"),
        f"사진 {len(photo_paths)}장이 아래에 파일명과 함께 있다.",
    ])
    content = [{"type": "text", "text": memo}]
    for p in photo_paths:
        data = base64.standard_b64encode(api_jpeg(p)).decode("ascii")
        content.append({"type": "text", "text": f"사진 파일명: {p.name}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    return content


def write_draft(client, model: str, r: ReviewInput, photo_paths: list[Path],
                style_samples: str, avoid: list[str]) -> Draft:
    with client.beta.messages.stream(
        model=model,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        system=build_system(style_samples),
        messages=[{"role": "user", "content": build_user_content(r, photo_paths, avoid)}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise DraftError("AI가 이 요청을 거절했습니다. 사진이나 메모에 문제가 될 내용이 없는지 확인해 주세요.")
    # 폴백이 일어나면 거절한 모델의 미완성 출력이 앞에 남으므로 마지막 텍스트 블록을 쓴다.
    text = next((b.text for b in reversed(message.content) if b.type == "text"), "")
    try:
        return draft_from_dict(json.loads(text))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise DraftError(f"AI 응답 형식이 올바르지 않습니다: {e}") from e
