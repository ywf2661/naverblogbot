import base64
import json
from pathlib import Path

from .draft import Draft, draft_from_dict
from .inputs import ReviewInput
from .lookup import PlaceInfo
from .photos import api_jpeg, is_video

_BLOCK = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["quote", "lines", "photo", "video", "map", "blank"]},
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

_RULES = """너는 네이버 블로그에 맛집 후기를 쓰는 평범한 블로거의 초안을 대신 써 준다. 사용자가 준 사진·동영상 장면과 메모만으로 쓰고, 사용자가 발행 전에 직접 검토하고 고친다.

무엇을 쓸까: 읽는 사람이 궁금해하는 것
- 우선순위: 어떤 가게인지 한 줄 / 찾아가는 길 / 영업시간·휴무·주차 / 웨이팅·혼잡 / 먹은 메뉴와 가격 / 맛·식감·양·온도 / 가성비 / 분위기·좌석(혼밥·단체·데이트) / 포장·배달 / 추천 대상 / 아쉬운 점.
- 쓰지 않는 것: 주문 번호, 영수증·주문서의 시각, 키오스크 화면 문구나 남은 시간, 의자 재질, 벽 색, 테이블 위 물건 나열, 퇴식구·안내판 그림처럼 사진에 찍혔을 뿐 읽는 사람에게 쓸모없는 디테일.
- 키오스크 주문, 셀프 물, 반찬 리필처럼 이용 방법은 쓸모 있으니 한 줄로 쓴다.
- 메뉴판을 통째로 옮기지 않는다. 먹은 메뉴와, 눈에 띄는 메뉴 1~2개의 이름·가격만 쓴다.

사실 규칙
- 맛, 양, 온도, 친절도, 가격, 웨이팅은 메모에 있는 것만 쓴다. 메모에 없으면 언급하지 않는다.
- 위치·찾아가는 길·영업시간·휴무·주차는 메모에 있으면 그대로, 없으면 "웹 검색으로 찾은 정보"를 쓴다. 둘 다 없으면 아예 언급하지 않는다("방문 전 확인하세요" 같은 빈말 금지). "골목 안쪽", "역 근처"처럼 근거 없는 위치 묘사도 하지 않는다.
- 사진·장면에서 보이는 것(음식의 색, 단면, 담음새, 양, 실내 분위기)은 그 판단이 읽는 사람에게 도움될 때만 쓴다.
- 메뉴판 사진에서 읽은 메뉴명·가격은 「확인: 돈가스 12,000원」처럼 표시하고 confirm 목록에 같은 문구(「확인:」 뒤 내용)를 넣는다. 메모에 메뉴·가격이 있으면 메모를 따르고 표시하지 않는다.
- 메모에 없는 감정, 동행인, 방문 계기, 추천 대상, 아쉬운 점을 지어내지 않는다.
- 광고·협찬 문구는 쓰지 않는다. 프로그램이 따로 넣는다.

사람이 쓴 것처럼
- 1인칭 블로거 말투로, 정보 사이사이에 짧은 감상과 연결 말을 섞는다. 예: "이제 본격적으로 먹어볼게요", "이건 진짜 예상 밖이었어요" (사실을 지어내지 않는 연결 말과 반응은 괜찮다).
- "상호는 ○○, 동네는 ○○"처럼 항목을 나열하는 말투를 쓰지 않는다. 가게명과 위치는 문장 속에 자연스럽게 녹인다.
- 같은 어미를 세 번 넘게 연달아 쓰지 않고, 문장 길이를 섞는다.

구성 (blocks 순서)
1. 도입: lines 2~4줄로 어떤 가게인지와 방문 상황.
2. quote 위치·정보 소제목 → lines(찾아가는 길, 영업시간·휴무·주차·웨이팅 중 아는 것) → map
3. 외관·내부 → 메뉴 → 음식 순으로 사진·동영상을 배치하고, 같은 종류는 주어진 순서를 따른다.
4. 총평 quote → lines: 추천 대상은 "✔"로 시작하는 줄, 아쉬운 점·재방문 의사는 메모에 있을 때만.
- 모든 사진은 photo, 모든 동영상은 video 블록으로 정확히 한 번씩 넣는다. file 값은 주어진 파일명 그대로.
- 사진·동영상을 먼저 놓고 그 아래에 그 이야기를 쓴다. 글 → 사진이 아니라 사진 → 글 순서다.
- 사진마다 설명을 붙이지 않아도 된다. 비슷한 사진 2~3장을 연달아 놓고 한 번에 1~3줄로 말해도 된다. 설명할 게 없으면 사진만 둔다.
- 동영상은 그 장면이 보여 주는 순간(지글지글 굽는 모습, 치즈가 늘어나는 모습 등) 근처에 두고 1~2줄을 붙인다.
- map 블록은 한 번만 쓴다. 쓰지 않는 필드는 빈 문자열이나 빈 배열로 둔다.

줄과 문단
- lines의 한 줄은 구절 단위로 끊은 14~20자, 최대 22자(공백 포함). 한 문장을 여러 줄에 나눠도 된다.
- 문단 사이에는 blank 블록을 한 개 넣는다. lines 블록 하나는 1~4줄.
- 본문 글자 수(공백 제외)는 1,500자 이상, 2,300자 이하를 목표로 한다. 캠페인 가이드에 글자 수가 있으면 그것을 따른다.
- 분량은 쓸모 있는 것으로 채운다: 음식에서 보이는 것(단면, 속 재료, 소스, 양, 크기), 메모의 맛·식감에 대한 풀어쓰기, 주문·포장·좌석 같은 이용 팁, 짧은 감상과 연결 말. 쓸모없는 디테일이나 같은 말 반복으로 채우지 않는다.

말투
- 기본은 "~요" 체, 가끔 "~다"를 섞는다. "ㅎㅎ"는 글 전체에서 2번 이하.
- 이모지는 글 전체 5~10개, quote 소제목 앞과 ✔ 줄에만 쓴다.
- 메모의 "피할 문장"과 같은 문장을 쓰지 않는다.

제목 titles 3개
- 각 30~45자. "동네+맛집 키워드 → 가게명(+지점) → 대표 메뉴 → 후기/솔직후기/재방문 같은 수식어" 순서.
- 필수 키워드가 있으면 3개 모두에 자연스럽게 넣는다.

태그 tags 10~20개
- # 없이 쓴다. 절반 이상은 동네명 조합(예: 판교맛집, 판교역맛집, 판교점심, 판교수육). 가게명, 가게명+지점, 메모에 근거한 상황(데이트, 회식, 혼밥 등).
- 필수 키워드가 있으면 모두 포함한다.

photos 목록
- 모든 사진과 동영상마다 kind(exterior/interior/menu/food/other)와 has_face(알아볼 수 있는 사람 얼굴이 있으면 true)."""


class DraftError(Exception):
    pass


def build_system(style_samples: str) -> str:
    if not style_samples.strip():
        return _RULES
    return (_RULES + "\n\n내 말투\n- 아래는 사용자가 직접 쓴 글이다. 어미, 문장 길이, 말버릇을 따르고 내용은 가져오지 않는다.\n"
            f"<내 글 예시>\n{style_samples.strip()}\n</내 글 예시>")


def build_user_content(r: ReviewInput, photo_paths: list[Path], avoid: list[str],
                       place: PlaceInfo | None = None) -> list[dict]:
    visit = f"협찬 ({r.sponsor})" if r.sponsored else "내돈내산"
    memo = "\n".join([
        f"가게명: {r.store}",
        f"동네: {r.area}",
        f"방문 유형: {visit}",
        f"한 줄 소감: {r.impression}",
        f"먹은 메뉴·가격: {r.menu or '(없음 — 메뉴판 사진에서 읽고 확인 표시)'}",
        f"아쉬운 점: {r.cons or '(없음 — 쓰지 말 것)'}",
        f"추천 대상: {r.target or '(없음 — 쓰지 말 것)'}",
        f"웨이팅·주차·영업시간(메모): {r.extra or '(없음)'}",
        f"웹 검색으로 찾은 정보: {place.memo() if place and place.found else '(없음)'}",
        f"필수 키워드: {', '.join(r.keyword_list) or '(없음)'}",
        f"캠페인 가이드: {r.guide or '(없음)'}",
        "피할 문장: " + (" / ".join(avoid) if avoid else "(없음)"),
        f"사진·동영상 {len(photo_paths)}개가 아래에 파일명과 함께 있다. 동영상은 영상 속 한 장면만 보여 준다.",
    ])
    content = [{"type": "text", "text": memo}]
    for p in photo_paths:
        data = base64.standard_b64encode(api_jpeg(p)).decode("ascii")
        label = f"동영상 파일명: {p.name} (영상 속 한 장면)" if is_video(p) else f"사진 파일명: {p.name}"
        content.append({"type": "text", "text": label})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    return content


def write_draft(client, model: str, r: ReviewInput, photo_paths: list[Path],
                style_samples: str, avoid: list[str], place: PlaceInfo | None = None) -> Draft:
    with client.beta.messages.stream(
        model=model,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        system=build_system(style_samples),
        messages=[{"role": "user", "content": build_user_content(r, photo_paths, avoid, place)}],
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
