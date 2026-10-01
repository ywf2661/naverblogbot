import re
from dataclasses import asdict, dataclass, field, replace

from . import rules
from .inputs import ReviewInput


@dataclass
class Block:
    type: str
    text: str = ""
    lines: list[str] = field(default_factory=list)
    file: str = ""


@dataclass
class PhotoInfo:
    file: str
    kind: str
    has_face: bool


@dataclass
class Draft:
    titles: list[str]
    blocks: list[Block]
    tags: list[str]
    photos: list[PhotoInfo]
    confirm: list[str]
    disclosure: str = ""

    @property
    def hashtag_line(self) -> str:
        tags = [t.strip().lstrip("#") for t in self.tags]
        return " ".join(f"#{t}" for t in tags if t)


def draft_from_dict(d: dict) -> Draft:
    return Draft(
        titles=list(d["titles"]),
        blocks=[Block(**b) for b in d["blocks"]],
        tags=list(d["tags"]),
        photos=[PhotoInfo(**p) for p in d["photos"]],
        confirm=list(d["confirm"]),
        disclosure=d.get("disclosure", ""),
    )


def draft_to_dict(d: Draft) -> dict:
    return asdict(d)


def wrap_line(line: str, max_len: int = rules.MAX_LINE) -> list[str]:
    out, cur = [], ""
    for word in line.split():
        while len(word) > max_len:
            if cur:
                out.append(cur)
                cur = ""
            out.append(word[:max_len])
            word = word[max_len:]
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_len:
            cur += " " + word
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def _josa_ro(word: str) -> str:
    last = word.strip()[-1]
    if not "가" <= last <= "힣":
        return "(으)로"
    batchim = (ord(last) - ord("가")) % 28
    return "로" if batchim in (0, 8) else "으로"  # 받침 없음 또는 ㄹ받침


def disclosure_text(sponsor: str) -> str:
    sponsor = sponsor.strip()
    return f"[협찬] 이 글은 {sponsor}{_josa_ro(sponsor)}부터 식사를 무상으로 제공받아 작성했습니다."


def _collapse_blanks(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        if b.type == "blank" and (not out or out[-1].type == "blank"):
            continue
        out.append(b)
    while out and out[-1].type == "blank":
        out.pop()
    return out


def finalize(d: Draft, r: ReviewInput) -> Draft:
    blocks = _collapse_blanks([replace(b, lines=[x for line in b.lines for x in wrap_line(line)]) for b in d.blocks])
    return replace(d, blocks=blocks, disclosure=disclosure_text(r.sponsor) if r.sponsored else "")


def _texts(d: Draft) -> list[str]:
    texts = [d.disclosure]
    for b in d.blocks:
        texts.append(b.text)
        texts.extend(b.lines)
    return texts


def body_char_count(d: Draft) -> int:
    return sum(len(re.sub(r"\s", "", t)) for t in _texts(d))


def check(d: Draft, r: ReviewInput, photo_names: list[str]) -> list[str]:
    warnings = []
    chars = body_char_count(d)
    if not rules.CHAR_MIN <= chars <= rules.CHAR_MAX:
        warnings.append(f"본문 글자 수가 {chars:,}자입니다. 상위 글 기준 {rules.CHAR_MIN:,}~{rules.CHAR_MAX:,}자를 벗어났어요. "
                        "짧다면 소감·메뉴 메모를 더 적고 다시 만들어 보세요.")
    if len(photo_names) < rules.PHOTO_MIN:
        warnings.append(f"사진이 {len(photo_names)}장입니다. 상위 글은 보통 {rules.PHOTO_MIN}장 이상이에요.")
    used = [b.file for b in d.blocks if b.type in ("photo", "video")]
    for name in photo_names:
        if name not in used:
            warnings.append(f"{name} 사진·동영상이 본문에서 빠졌습니다.")
    for name in used:
        if name not in photo_names:
            warnings.append(f"{name}은(는) 폴더에 없는 파일이라 입력하지 않습니다.")
    emoji = sum(len(rules.EMOJI_RE.findall(t)) for t in _texts(d))
    if emoji > rules.EMOJI_MAX:
        warnings.append(f"이모지가 {emoji}개입니다. {rules.EMOJI_MAX}개 이하로 줄이는 걸 권장해요.")
    haystack = " ".join(d.titles + _texts(d) + d.tags)
    for kw in r.keyword_list:
        if kw not in haystack:
            warnings.append(f"필수 키워드 '{kw}'가 제목·본문·태그에 없습니다.")
    return warnings


def checklist(d: Draft, r: ReviewInput) -> list[str]:
    items = []
    if r.sponsored:
        items.append("체험단 사이트에서 받은 공정위 배너를 글 맨 위에 넣었나요?")
        items.append("첫 줄 광고 문구의 크기·색을 확인하세요. 본문보다 크거나 다른 색이어야 해요 (지금은 굵게만 되어 있어요).")
    for c in d.confirm:
        items.append(f"확인 필요: {c} — 본문의 「확인」 표시를 고치거나 지우세요.")
    for p in d.photos:
        if p.has_face:
            items.append(f"{p.file}에 사람 얼굴이 보여요. 모자이크 처리하세요.")
    items.append("지도가 올바른 가게로 들어갔나요?")
    items.append("내가 하지 않은 말이 들어가 있지 않나요?")
    return items
