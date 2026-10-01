# naverblogbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 맛집 사진 폴더 + 메모를 받아 상위 노출 글 형식의 리뷰 초안을 만들고, 봇 전용 크롬의 네이버 에디터에 입력한 뒤 발행 직전에 멈추는 Windows exe를 만든다.

**Architecture:** 순수 로직 모듈(settings, inputs, photos, draft, history, writer, preview, pipeline)은 단위 테스트로 고정하고, 외부 의존(Claude API, 네이버 에디터, tkinter 창)은 얇은 껍데기로 분리한다. Claude 호출은 구조화 출력 1회, 광고 문구·줄 재분할·검사는 코드가 한다. 에디터 입력은 "동작 목록 생성(테스트 가능)"과 "실행(수동 검증)"으로 나눈다.

**Tech Stack:** Python 3.13, anthropic SDK, Pillow, Playwright(설치된 Chrome/Edge 사용), truststore, tkinter, pytest, PyInstaller, GitHub Actions(windows-latest)

**Spec:** `docs/superpowers/specs/2026-10-01-naverblogbot-design.md` (기준값 근거: `docs/research/2026-10-01-top-posts-analysis.md`)

## Global Constraints

- 발행 버튼·발행 설정 창은 절대 클릭하지 않는다. 대량·예약 발행 기능을 만들지 않는다.
- 협찬 광고 문구는 코드가 맨 앞에 강제 삽입하며 끄거나 옮기는 옵션을 만들지 않는다: `[협찬] 이 글은 {업체명}(으)로부터 식사를 무상으로 제공받아 작성했습니다.`
- 사실(맛·양·가격·영업시간·웨이팅·주차)은 사용자 입력에서만. 부족하면 지어내지 않고 경고.
- 기준값: 한 줄 최대 22자, 본문(공백 제외) 경고 범위 1,100~2,745자, 목표 1,500~2,300자, 사진 13장 미만 경고, 이모지 12개 초과 경고, 태그 10~20개, 제목 30~45자.
- 지원 사진: jpg/jpeg/png/webp. HEIC는 변환 안내만.
- API 전송용 사진 축소: 긴 변 1280px, EXIF 회전 반영, JPEG 품질 85. 업로드는 원본.
- 모델 기본값 `claude-opus-5`, 서버 거절 폴백 `fallbacks: "default"` (베타 헤더 `server-side-fallback-2026-07-01`).
- 설정 파일: `%APPDATA%\naverblogbot\settings.json`, 크롬 프로필: `%LOCALAPPDATA%\naverblogbot\chrome-profile`. 테스트는 환경변수 `NAVERBLOGBOT_HOME`으로 경로를 바꾼다.
- 회사망 대응: 진입점에서 `truststore.inject_into_ssl()`.
- 사용자에게 보이는 모든 문구(창, 오류, 체크리스트, README)는 한국어.
- 모든 명령은 저장소 루트 `C:\Users\HYGOOD\Downloads\autobot\naverblogbot`에서 Git Bash로 실행. 파이썬은 `.venv/Scripts/python`.

## Review Focus

1. 업체명이 받침 없는 글자·ㄹ받침·영문으로 끝날 때 광고 문구의 조사(로/으로)가 맞아야 한다 → Task 4 `test_disclosure_josa`
2. 폴더에 HEIC만 있거나 사진이 0장이면 원인을 한국어로 알려주고 Claude를 호출하지 않아야 한다 → Task 2 `test_validate_heic_only`, Task 3 `test_list_photos_ignores_heic`
3. Claude가 없는 파일명을 넣거나 사진을 빠뜨리면 경고하고, 에디터 입력은 없는 파일을 건너뛰어야 한다 → Task 4 `test_check_photo_mismatch`, Task 8 `test_plan_actions_skips_unknown_photo`
4. 띄어쓰기 없는 22자 초과 줄(가게 주소, 긴 메뉴명)도 잘려야 한다 → Task 4 `test_wrap_line_hard_split`
5. 잘못된 API 키·회사망 연결 실패 시 창이 죽지 않고 한국어 오류를 보여야 한다 → Task 7 `test_friendly_error_*`

---

### Task 1: 프로젝트 골격 + 설정 + 기준값

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `naverblogbot/__init__.py`, `naverblogbot/settings.py`, `naverblogbot/rules.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `settings.Settings(api_key: str = "", model: str = "claude-opus-5", style_samples: str = "")`
  - `settings.app_dir() -> Path` (`NAVERBLOGBOT_HOME` 있으면 그 경로, 없으면 `%APPDATA%\naverblogbot`)
  - `settings.profile_dir() -> Path` (`NAVERBLOGBOT_HOME/chrome-profile` 또는 `%LOCALAPPDATA%\naverblogbot\chrome-profile`)
  - `settings.load(path: Path | None = None) -> Settings`, `settings.save(s: Settings, path: Path | None = None) -> None`
  - `rules` 상수: `MAX_LINE=22`, `CHAR_MIN=1100`, `CHAR_MAX=2745`, `CHAR_TARGET=(1500, 2300)`, `PHOTO_MIN=13`, `EMOJI_MAX=12`, `TAG_RANGE=(10, 20)`, `TITLE_RANGE=(30, 45)`, `EMOJI_RE` (정규식)

- [ ] **Step 1: 가상환경과 의존성 파일 만들기**

`requirements.txt`:
```
anthropic
pillow
playwright
truststore
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
pyinstaller
```

`pytest.ini`:
```
[pytest]
testpaths = tests
pythonpath = .
```

`naverblogbot/__init__.py`: 빈 파일.

Run:
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -q -r requirements-dev.txt && .venv/Scripts/python -c "import anthropic, PIL, playwright, truststore; print(anthropic.__version__)"
```
Expected: 버전 번호 출력

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_settings.py`

```python
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
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_settings.py -v`
Expected: FAIL (`ImportError` / `AttributeError`)

- [ ] **Step 4: 구현** — `naverblogbot/settings.py`

```python
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
        return Path(os.environ["NAVERBLOGBOT_HOME"]) / "chrome-profile"
    return Path(os.environ["LOCALAPPDATA"]) / "naverblogbot" / "chrome-profile"


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
```

`naverblogbot/rules.py`:
```python
"""상위 노출 맛집 글 90개 실측(docs/research/2026-10-01-top-posts-analysis.md)에서 나온 기준값."""
import re

MAX_LINE = 22
CHAR_MIN = 1100
CHAR_MAX = 2745
CHAR_TARGET = (1500, 2300)
PHOTO_MIN = 13
EMOJI_MAX = 12
TAG_RANGE = (10, 20)
TITLE_RANGE = (30, 45)

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u3030]")
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_settings.py -v`
Expected: 4 passed

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt requirements-dev.txt pytest.ini naverblogbot tests/test_settings.py
git commit -m "feat: add settings storage and research-based rules"
```

---

### Task 2: 입력 검증 (inputs.py)

**Files:**
- Create: `naverblogbot/inputs.py`
- Test: `tests/test_inputs.py`

**Interfaces:**
- Consumes: 없음 (사진 확장자 판별은 이 파일 안의 `PHOTO_EXTS`, `HEIC_EXTS`)
- Produces:
  - `inputs.ReviewInput(photo_dir: Path, store: str, area: str, impression: str, sponsored: bool, sponsor: str = "", menu: str = "", cons: str = "", target: str = "", extra: str = "", keywords: str = "", guide: str = "")`
  - `ReviewInput.keyword_list -> list[str]` (쉼표 구분, 공백 제거, 빈 값 제외)
  - `inputs.validate(r: ReviewInput) -> list[str]` (막는 오류, 한국어)
  - `inputs.missing_judgments(r: ReviewInput) -> list[str]` (비어 있는 "아쉬운 점", "추천 대상")
  - `inputs.PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}`, `inputs.HEIC_EXTS = {".heic", ".heif"}`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_inputs.py`

```python
from pathlib import Path

from naverblogbot.inputs import ReviewInput, missing_judgments, validate


def make(tmp_path, **kw):
    base = dict(photo_dir=tmp_path, store="해미옥", area="판교", impression="수육이 부드러웠음", sponsored=False)
    base.update(kw)
    return ReviewInput(**base)


def touch(folder: Path, *names):
    for n in names:
        (folder / n).write_bytes(b"x")


def test_valid_input_has_no_errors(tmp_path):
    touch(tmp_path, "a.jpg")
    assert validate(make(tmp_path)) == []


def test_required_fields(tmp_path):
    touch(tmp_path, "a.jpg")
    errors = validate(make(tmp_path, store=" ", area="", impression=""))
    assert "가게명을 입력하세요." in errors
    assert "동네를 입력하세요." in errors
    assert "한 줄 소감을 입력하세요." in errors


def test_sponsored_requires_sponsor(tmp_path):
    touch(tmp_path, "a.jpg")
    assert "협찬이면 업체명(또는 체험단명)을 입력하세요." in validate(make(tmp_path, sponsored=True))


def test_missing_folder(tmp_path):
    errors = validate(make(tmp_path / "없음"))
    assert errors == ["사진 폴더를 찾을 수 없습니다."]


def test_validate_heic_only(tmp_path):
    touch(tmp_path, "a.HEIC", "b.heic")
    errors = validate(make(tmp_path))
    assert any("HEIC" in e and "JPG" in e for e in errors)


def test_no_photos(tmp_path):
    touch(tmp_path, "memo.txt")
    assert "폴더에 사진(jpg, png, webp)이 없습니다." in validate(make(tmp_path))


def test_keyword_list():
    r = ReviewInput(Path("."), "s", "a", "i", True, "x", keywords=" 판교맛집, ,해미옥 ,")
    assert r.keyword_list == ["판교맛집", "해미옥"]


def test_missing_judgments(tmp_path):
    assert missing_judgments(make(tmp_path)) == ["아쉬운 점", "추천 대상"]
    assert missing_judgments(make(tmp_path, cons="짰음", target="직장인")) == []
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_inputs.py -v`
Expected: FAIL (`ModuleNotFoundError: naverblogbot.inputs`)

- [ ] **Step 3: 구현** — `naverblogbot/inputs.py`

```python
from dataclasses import dataclass
from pathlib import Path

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
HEIC_EXTS = {".heic", ".heif"}


@dataclass
class ReviewInput:
    photo_dir: Path
    store: str
    area: str
    impression: str
    sponsored: bool
    sponsor: str = ""
    menu: str = ""
    cons: str = ""
    target: str = ""
    extra: str = ""
    keywords: str = ""
    guide: str = ""

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip() for k in self.keywords.split(",") if k.strip()]


def validate(r: ReviewInput) -> list[str]:
    folder = Path(r.photo_dir)
    if not folder.is_dir():
        return ["사진 폴더를 찾을 수 없습니다."]
    errors = []
    if not r.store.strip():
        errors.append("가게명을 입력하세요.")
    if not r.area.strip():
        errors.append("동네를 입력하세요.")
    if not r.impression.strip():
        errors.append("한 줄 소감을 입력하세요.")
    if r.sponsored and not r.sponsor.strip():
        errors.append("협찬이면 업체명(또는 체험단명)을 입력하세요.")
    exts = [p.suffix.lower() for p in folder.iterdir() if p.is_file()]
    if not any(e in PHOTO_EXTS for e in exts):
        if any(e in HEIC_EXTS for e in exts):
            errors.append("HEIC 사진은 쓸 수 없습니다. JPG로 바꿔 주세요 (아이폰: 설정 > 카메라 > 포맷 > 높은 호환성).")
        else:
            errors.append("폴더에 사진(jpg, png, webp)이 없습니다.")
    return errors


def missing_judgments(r: ReviewInput) -> list[str]:
    missing = []
    if not r.cons.strip():
        missing.append("아쉬운 점")
    if not r.target.strip():
        missing.append("추천 대상")
    return missing
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_inputs.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/inputs.py tests/test_inputs.py
git commit -m "feat: add review input validation"
```

---

### Task 3: 사진 처리 (photos.py)

**Files:**
- Create: `naverblogbot/photos.py`
- Test: `tests/test_photos.py`

**Interfaces:**
- Consumes: `inputs.PHOTO_EXTS`
- Produces:
  - `photos.list_photos(folder: Path) -> list[Path]` (촬영시각 → 파일명 순, HEIC·기타 제외)
  - `photos.taken_at(path: Path) -> str` (EXIF DateTimeOriginal → DateTime `"YYYY:MM:DD HH:MM:SS"`, 둘 다 없으면 파일 수정시각을 같은 형식으로)
  - `photos.api_jpeg(path: Path, max_side: int = 1280) -> bytes`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_photos.py`

```python
import io
import os

from PIL import Image

from naverblogbot.photos import api_jpeg, list_photos, taken_at


def save_img(path, size=(400, 300), taken=None, orientation=None):
    img = Image.new("RGB", size, "red")
    exif = Image.Exif()
    if taken:
        exif[306] = taken  # DateTime (기본 IFD)
    if orientation:
        exif[0x0112] = orientation
    img.save(path, exif=exif)


def test_list_photos_sorted_by_taken_time(tmp_path):
    save_img(tmp_path / "b.jpg", taken="2026:10:01 12:00:00")
    save_img(tmp_path / "a.jpg", taken="2026:10:01 12:05:00")
    save_img(tmp_path / "c.png")
    os.utime(tmp_path / "c.png", (0, 0))  # 1970 → 맨 앞
    names = [p.name for p in list_photos(tmp_path)]
    assert names == ["c.png", "b.jpg", "a.jpg"]


def test_list_photos_ignores_heic(tmp_path):
    save_img(tmp_path / "a.jpg")
    (tmp_path / "b.HEIC").write_bytes(b"x")
    (tmp_path / "draft.json").write_text("{}")
    assert [p.name for p in list_photos(tmp_path)] == ["a.jpg"]


def test_taken_at_reads_exif(tmp_path):
    save_img(tmp_path / "a.jpg", taken="2026:09:30 18:01:02")
    assert taken_at(tmp_path / "a.jpg") == "2026:09:30 18:01:02"


def test_api_jpeg_shrinks_long_side(tmp_path):
    save_img(tmp_path / "big.png", size=(4000, 3000))
    out = Image.open(io.BytesIO(api_jpeg(tmp_path / "big.png")))
    assert out.format == "JPEG"
    assert max(out.size) == 1280


def test_api_jpeg_applies_exif_rotation(tmp_path):
    save_img(tmp_path / "rot.jpg", size=(400, 300), orientation=6)  # 90도 회전 표시
    out = Image.open(io.BytesIO(api_jpeg(tmp_path / "rot.jpg")))
    assert out.size == (300, 400)


def test_api_jpeg_keeps_small_image(tmp_path):
    save_img(tmp_path / "s.jpg", size=(400, 300))
    out = Image.open(io.BytesIO(api_jpeg(tmp_path / "s.jpg")))
    assert out.size == (400, 300)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_photos.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현** — `naverblogbot/photos.py`

```python
import io
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from .inputs import PHOTO_EXTS

_EXIF_IFD = 0x8769
_DATETIME_ORIGINAL = 36867
_DATETIME = 306


def taken_at(path: Path) -> str:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            value = exif.get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL) or exif.get(_DATETIME)
            if value:
                return str(value)
    except OSError:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y:%m:%d %H:%M:%S")


def list_photos(folder: Path) -> list[Path]:
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXTS]
    return sorted(files, key=lambda p: (taken_at(p), p.name))


def api_jpeg(path: Path, max_side: int = 1280) -> bytes:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_photos.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/photos.py tests/test_photos.py
git commit -m "feat: add photo listing and API-size resizing"
```

---

### Task 4: 초안 구조·후처리·검사 (draft.py)

**Files:**
- Create: `naverblogbot/draft.py`
- Test: `tests/test_draft.py`

**Interfaces:**
- Consumes: `rules.*`, `inputs.ReviewInput`
- Produces:
  - `draft.Block(type: str, text: str = "", lines: list[str] = [], file: str = "")` — type ∈ `quote|lines|photo|map|blank`
  - `draft.PhotoInfo(file: str, kind: str, has_face: bool)`
  - `draft.Draft(titles: list[str], blocks: list[Block], tags: list[str], photos: list[PhotoInfo], confirm: list[str], disclosure: str = "")`, 속성 `Draft.hashtag_line -> str`
  - `draft.draft_from_dict(d: dict) -> Draft`, `draft.draft_to_dict(d: Draft) -> dict`
  - `draft.wrap_line(line: str, max_len: int = rules.MAX_LINE) -> list[str]`
  - `draft.disclosure_text(sponsor: str) -> str`
  - `draft.finalize(d: Draft, r: ReviewInput) -> Draft` (줄 재분할 + 협찬 문구)
  - `draft.body_char_count(d: Draft) -> int` (공백 제외, 인용구·줄·광고 문구 포함, 해시태그 제외)
  - `draft.check(d: Draft, r: ReviewInput, photo_names: list[str]) -> list[str]` (경고)
  - `draft.checklist(d: Draft, r: ReviewInput) -> list[str]` (발행 전 확인 항목)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_draft.py`

```python
from pathlib import Path

from naverblogbot.draft import (Block, Draft, PhotoInfo, body_char_count, check, checklist,
                                disclosure_text, draft_from_dict, draft_to_dict, finalize, wrap_line)
from naverblogbot.inputs import ReviewInput


def review(**kw):
    base = dict(photo_dir=Path("."), store="해미옥", area="판교", impression="좋음", sponsored=False)
    base.update(kw)
    return ReviewInput(**base)


def sample(lines=None, photos=("a.jpg",), tags=None):
    blocks = [Block("quote", text="📍 위치"), Block("lines", lines=lines or ["판교역에서 가까워요"]), Block("map")]
    blocks += [Block("photo", file=f) for f in photos]
    return Draft(titles=["판교 맛집 해미옥"], blocks=blocks, tags=tags or ["판교맛집"] * 12,
                 photos=[PhotoInfo(f, "food", False) for f in photos], confirm=[])


def test_wrap_line_short_unchanged():
    assert wrap_line("판교역에서 가까워요") == ["판교역에서 가까워요"]


def test_wrap_line_splits_on_spaces():
    out = wrap_line("점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요")
    assert all(len(x) <= 22 for x in out)
    assert " ".join(out) == "점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요"


def test_wrap_line_hard_split():
    s = "경기성남시분당구판교역로192번길16일층해미옥판교본점"
    out = wrap_line(s)
    assert all(len(x) <= 22 for x in out)
    assert "".join(out) == s


def test_disclosure_josa():
    assert disclosure_text("리뷰노트") == "[협찬] 이 글은 리뷰노트로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("강남맛집") == "[협찬] 이 글은 강남맛집으로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("디너의여왕 체험단") == "[협찬] 이 글은 디너의여왕 체험단으로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("서울") == "[협찬] 이 글은 서울로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("REVU") == "[협찬] 이 글은 REVU(으)로부터 식사를 무상으로 제공받아 작성했습니다."


def test_finalize_wraps_and_adds_disclosure():
    d = finalize(sample(lines=["점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요"]),
                 review(sponsored=True, sponsor="리뷰노트"))
    assert d.disclosure.startswith("[협찬] 이 글은 리뷰노트로부터")
    assert all(len(x) <= 22 for b in d.blocks for x in b.lines)


def test_finalize_no_disclosure_when_not_sponsored():
    assert finalize(sample(), review()).disclosure == ""


def test_hashtag_line():
    d = sample(tags=["판교맛집", "#해미옥", " "])
    assert d.hashtag_line == "#판교맛집 #해미옥"


def test_body_char_count_excludes_spaces_and_hashtags():
    d = sample(lines=["가 나", "다"])
    d.disclosure = "광고 문구"
    # "📍 위치"(3) + "가나"(2) + "다"(1) + "광고문구"(4)
    assert body_char_count(d) == 10


def test_dict_roundtrip():
    d = sample()
    assert draft_from_dict(draft_to_dict(d)) == d


def test_check_short_and_few_photos():
    warnings = check(sample(), review(), ["a.jpg"])
    assert any("글자 수" in w and "1,100" in w for w in warnings)
    assert any("사진이 1장" in w for w in warnings)


def test_check_photo_mismatch():
    d = sample(photos=("a.jpg", "zzz.jpg"))
    warnings = check(d, review(), ["a.jpg", "b.jpg"])
    assert any("b.jpg" in w and "빠졌" in w for w in warnings)
    assert any("zzz.jpg" in w and "없는" in w for w in warnings)


def test_check_missing_keywords():
    warnings = check(sample(), review(keywords="판교맛집, 수육맛집"), ["a.jpg"])
    assert any("수육맛집" in w for w in warnings)
    assert not any("'판교맛집'" in w for w in warnings)


def test_check_too_many_emoji():
    d = sample(lines=["😀" * 13])
    assert any("이모지" in w for w in check(d, review(), ["a.jpg"]))


def test_checklist_items():
    d = sample()
    d.photos = [PhotoInfo("a.jpg", "food", True)]
    d.confirm = ["돈가스 12,000원"]
    items = checklist(d, review(sponsored=True, sponsor="리뷰노트"))
    assert any("배너" in i for i in items)
    assert any("광고 문구" in i and "크기" in i for i in items)
    assert any("a.jpg" in i and "모자이크" in i for i in items)
    assert any("돈가스 12,000원" in i for i in items)
    assert any("지도" in i for i in items)
    assert not any("배너" in i for i in checklist(d, review()))
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_draft.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현** — `naverblogbot/draft.py`

```python
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


def finalize(d: Draft, r: ReviewInput) -> Draft:
    blocks = [replace(b, lines=[x for line in b.lines for x in wrap_line(line)]) for b in d.blocks]
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
    used = [b.file for b in d.blocks if b.type == "photo"]
    for name in photo_names:
        if name not in used:
            warnings.append(f"{name} 사진이 본문에서 빠졌습니다.")
    for name in used:
        if name not in photo_names:
            warnings.append(f"{name}은(는) 폴더에 없는 사진이라 입력하지 않습니다.")
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
        items.append("첫 줄 광고 문구가 본문보다 크거나 다른 색으로 눈에 띄나요? (지금은 굵게만 되어 있어요)")
    for c in d.confirm:
        items.append(f"확인 필요: {c} — 본문의 「확인」 표시를 고치거나 지우세요.")
    for p in d.photos:
        if p.has_face:
            items.append(f"{p.file}에 사람 얼굴이 보여요. 모자이크 처리하세요.")
    items.append("지도가 올바른 가게로 들어갔나요?")
    items.append("내가 하지 않은 말이 들어가 있지 않나요?")
    return items
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_draft.py -v`
Expected: 15 passed

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/draft.py tests/test_draft.py
git commit -m "feat: add draft model, post-processing and checks"
```

---

### Task 5: 최근 초안 기억 (history.py)

**Files:**
- Create: `naverblogbot/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: `draft.Draft`
- Produces:
  - `history.remember(path: Path, d: Draft, keep: int = 3) -> None` (첫 3줄·끝 3줄 저장, 최근 keep개 유지)
  - `history.recent_phrases(path: Path) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_history.py`

```python
from naverblogbot.draft import Block, Draft
from naverblogbot.history import recent_phrases, remember


def d(first, last):
    return Draft(titles=[], blocks=[Block("lines", lines=first), Block("photo", file="a.jpg"), Block("lines", lines=last)],
                 tags=[], photos=[], confirm=[])


def test_empty_when_no_file(tmp_path):
    assert recent_phrases(tmp_path / "h.json") == []


def test_remember_first_and_last_lines(tmp_path):
    p = tmp_path / "h.json"
    remember(p, d(["안녕하세요", "오늘은", "판교", "중간"], ["끝1", "끝2", "끝3"]))
    assert recent_phrases(p) == ["안녕하세요", "오늘은", "판교", "끝1", "끝2", "끝3"]


def test_keeps_only_recent(tmp_path):
    p = tmp_path / "h.json"
    for i in range(5):
        remember(p, d([f"첫{i}"], [f"끝{i}"]), keep=3)
    phrases = recent_phrases(p)
    assert "첫0" not in phrases and "첫1" not in phrases
    assert "첫4" in phrases
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_history.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — `naverblogbot/history.py`

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_history.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/history.py tests/test_history.py
git commit -m "feat: remember recent draft openings and closings"
```

---

### Task 6: Claude 호출 (writer.py)

**Files:**
- Create: `naverblogbot/writer.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Consumes: `inputs.ReviewInput`, `photos.api_jpeg`, `draft.draft_from_dict`, `draft.Draft`
- Produces:
  - `writer.SCHEMA: dict` (구조화 출력 스키마)
  - `writer.DraftError(Exception)`
  - `writer.build_system(style_samples: str) -> str`
  - `writer.build_user_content(r: ReviewInput, photo_paths: list[Path], avoid: list[str]) -> list[dict]`
  - `writer.write_draft(client, model: str, r: ReviewInput, photo_paths: list[Path], style_samples: str, avoid: list[str]) -> Draft`
  - `client`는 `anthropic.Anthropic` 또는 `client.beta.messages.stream(**kwargs)` 컨텍스트 매니저를 가진 가짜 객체

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_writer.py`

```python
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from naverblogbot.inputs import ReviewInput
from naverblogbot.writer import DraftError, SCHEMA, build_system, build_user_content, write_draft

DRAFT_JSON = {
    "titles": ["판교역 점심 맛집 해미옥 수육 후기"] * 3,
    "blocks": [{"type": "photo", "text": "", "lines": [], "file": "a.jpg"}],
    "tags": ["판교맛집"],
    "photos": [{"file": "a.jpg", "kind": "food", "has_face": False}],
    "confirm": [],
}


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, text=json.dumps(DRAFT_JSON, ensure_ascii=False), stop_reason="end_turn"):
        self.calls = []
        msg = SimpleNamespace(stop_reason=stop_reason, content=[
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self._msg = msg

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._msg)


@pytest.fixture
def setup(tmp_path):
    Image.new("RGB", (50, 50)).save(tmp_path / "a.jpg")
    r = ReviewInput(tmp_path, "해미옥", "판교", "수육이 부드러웠음", True, "리뷰노트",
                    menu="수육 정식 15,000원", keywords="판교맛집")
    return r, [tmp_path / "a.jpg"]


def test_system_includes_rules_and_style():
    s = build_system("저는 ~했어용 말투")
    assert "22자" in s and "1,500~2,300자" in s
    assert "저는 ~했어용 말투" in s
    assert "<내 글 예시>" not in build_system("")


def test_user_content_has_memo_and_labeled_images(setup):
    r, paths = setup
    content = build_user_content(r, paths, avoid=["안녕하세요 여러분"])
    memo = content[0]["text"]
    assert "해미옥" in memo and "수육 정식 15,000원" in memo and "판교맛집" in memo
    assert "안녕하세요 여러분" in memo
    assert "협찬" in memo
    assert content[1] == {"type": "text", "text": "사진 파일명: a.jpg"}
    assert content[2]["type"] == "image" and content[2]["source"]["media_type"] == "image/jpeg"


def test_write_draft_request_shape(setup):
    r, paths = setup
    client = FakeClient()
    d = write_draft(client, "claude-opus-5", r, paths, "", [])
    assert d.titles[0].startswith("판교역")
    call = client.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["extra_body"] == {"fallbacks": "default"}
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}


def test_refusal_raises(setup):
    r, paths = setup
    with pytest.raises(DraftError, match="거절"):
        write_draft(FakeClient(stop_reason="refusal"), "m", r, paths, "", [])


def test_bad_json_raises(setup):
    r, paths = setup
    with pytest.raises(DraftError, match="형식"):
        write_draft(FakeClient(text="{not json"), "m", r, paths, "", [])
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_writer.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — `naverblogbot/writer.py`

```python
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
    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return draft_from_dict(json.loads(text))
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise DraftError(f"AI 응답 형식이 올바르지 않습니다: {e}") from e
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_writer.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/writer.py tests/test_writer.py
git commit -m "feat: add Claude draft writer with structured output"
```

---

### Task 7: 미리보기 저장 + 전체 흐름 (preview.py, pipeline.py)

**Files:**
- Create: `naverblogbot/preview.py`, `naverblogbot/pipeline.py`
- Test: `tests/test_preview.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `draft.*`, `inputs.*`, `photos.list_photos`, `history.*`, `writer.write_draft`, `writer.DraftError`, `settings.Settings`, `settings.app_dir`
- Produces:
  - `preview.render_html(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> str`
  - `preview.save(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> Path` (`draft.json`, `draft.html`를 사진 폴더에 저장, html 경로 반환)
  - `pipeline.Result(draft: Draft, warnings: list[str], checklist: list[str], html_path: Path)`
  - `pipeline.make_draft(r: ReviewInput, s: Settings, client, history_path: Path | None = None) -> Result`
  - `pipeline.load_saved(r: ReviewInput) -> Draft` (사진 폴더의 `draft.json`)
  - `pipeline.friendly_error(e: Exception) -> str`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_preview.py`

```python
import json
from pathlib import Path

from naverblogbot.draft import Block, Draft, PhotoInfo
from naverblogbot.inputs import ReviewInput
from naverblogbot.preview import render_html, save


def sample():
    return Draft(titles=["제목<1>", "제목2", "제목3"],
                 blocks=[Block("quote", text="📍 위치"), Block("lines", lines=["줄 하나", "줄 둘"]),
                         Block("blank"), Block("photo", file="a.jpg"), Block("map")],
                 tags=["판교맛집"], photos=[PhotoInfo("a.jpg", "food", False)], confirm=[],
                 disclosure="[협찬] 이 글은 리뷰노트로부터 식사를 무상으로 제공받아 작성했습니다.")


def test_render_html_contents():
    r = ReviewInput(Path("."), "해미옥", "판교", "좋음", True, "리뷰노트")
    html = render_html(sample(), r, ["경고 하나"], ["확인 하나"])
    assert "제목&lt;1&gt;" in html
    assert '<img src="a.jpg"' in html
    assert "<b>[협찬]" in html
    assert "경고 하나" in html and "확인 하나" in html
    assert "#판교맛집" in html
    assert "지도" in html


def test_save_writes_files(tmp_path):
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", False)
    html_path = save(sample(), r, [], [])
    assert html_path == tmp_path / "draft.html"
    assert json.loads((tmp_path / "draft.json").read_text(encoding="utf-8"))["titles"][1] == "제목2"
```

`tests/test_pipeline.py`:
```python
import json
from pathlib import Path

import anthropic
from PIL import Image

from naverblogbot.inputs import ReviewInput
from naverblogbot.pipeline import friendly_error, load_saved, make_draft
from naverblogbot.settings import Settings
from naverblogbot.writer import DraftError
from tests.test_writer import DRAFT_JSON, FakeClient


def test_make_draft_end_to_end(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (50, 50)).save(photos / "a.jpg")
    r = ReviewInput(photos, "해미옥", "판교", "좋음", True, "리뷰노트")
    result = make_draft(r, Settings(api_key="k"), FakeClient(), history_path=tmp_path / "h.json")
    assert result.draft.disclosure.startswith("[협찬]")
    assert result.html_path.exists()
    assert any("글자 수" in w for w in result.warnings)
    assert any("배너" in c for c in result.checklist)
    assert (tmp_path / "h.json").exists()
    assert load_saved(r).titles == DRAFT_JSON["titles"]


def test_friendly_error_auth():
    e = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    assert "API 키" in friendly_error(e)


def test_friendly_error_connection():
    e = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    assert "연결" in friendly_error(e)


def test_friendly_error_draft_and_unknown():
    assert friendly_error(DraftError("거절됨")) == "거절됨"
    assert "알 수 없는 오류" in friendly_error(ValueError("x"))
```

`tests/__init__.py`: 빈 파일 (테스트 간 가짜 클라이언트 재사용용).

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_preview.py tests/test_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — `naverblogbot/preview.py`

```python
import html
import json
from pathlib import Path

from .draft import Draft, draft_to_dict
from .inputs import ReviewInput

_CSS = """body{font-family:'Malgun Gothic',sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#222}
.post p{text-align:center;margin:0;line-height:1.8}.post .blank{height:1.8em}
.quote{text-align:center;border-left:4px solid #03c75a;margin:24px 0;padding:8px;font-weight:bold}
.post img{display:block;max-width:100%;margin:12px auto}.map{text-align:center;color:#03c75a;margin:12px}
.box{background:#f6f6f6;padding:12px 16px;border-radius:8px;margin-bottom:16px}.warn{background:#fff4e5}"""


def render_html(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> str:
    e = html.escape
    out = [f"<title>{e(r.store)} 초안</title><style>{_CSS}</style>"]
    if warnings:
        out.append("<div class='box warn'><b>경고</b><ul>" + "".join(f"<li>{e(w)}</li>" for w in warnings) + "</ul></div>")
    out.append("<div class='box'><b>발행 전 체크리스트</b><ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul></div>")
    out.append("<div class='box'><b>제목 후보</b><ol>" + "".join(f"<li>{e(t)}</li>" for t in d.titles) + "</ol></div>")
    out.append("<div class='post'>")
    if d.disclosure:
        out.append(f"<p><b>{e(d.disclosure)}</b></p>")
    for b in d.blocks:
        if b.type == "quote":
            out.append(f"<div class='quote'>{e(b.text)}</div>")
        elif b.type == "lines":
            out.extend(f"<p>{e(x)}</p>" for x in b.lines)
        elif b.type == "blank":
            out.append("<div class='blank'></div>")
        elif b.type == "photo":
            out.append(f'<img src="{e(b.file)}" alt="{e(b.file)}">')
        elif b.type == "map":
            out.append(f"<div class='map'>[지도: {e(r.store)} {e(r.area)}]</div>")
    out.append(f"<p>{e(d.hashtag_line)}</p></div>")
    return "\n".join(out)


def save(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> Path:
    folder = Path(r.photo_dir)
    (folder / "draft.json").write_text(json.dumps(draft_to_dict(d), ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = folder / "draft.html"
    html_path.write_text(render_html(d, r, warnings, items), encoding="utf-8")
    return html_path
```

`naverblogbot/pipeline.py`:
```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 모든 테스트 통과 (settings 4, inputs 8, photos 6, draft 15, history 3, writer 5, preview 2, pipeline 4)

- [ ] **Step 5: 커밋**

```bash
git add naverblogbot/preview.py naverblogbot/pipeline.py tests/__init__.py tests/test_preview.py tests/test_pipeline.py
git commit -m "feat: add draft preview and end-to-end pipeline"
```

---

### Task 8: 에디터 입력 동작 목록 + 실행기 (editor.py)

**Files:**
- Create: `naverblogbot/editor.py`, `tools/probe_editor.py`
- Test: `tests/test_editor.py`

**Interfaces:**
- Consumes: `draft.Draft`, `inputs.ReviewInput`, `settings.profile_dir`
- Produces:
  - `editor.plan_actions(d: Draft, r: ReviewInput, title: str) -> list[tuple]` — 동작: `("title", str)`, `("bold_line", str)`, `("line", str)`, `("enter",)`, `("quote", str)`, `("photo", str 절대경로)`, `("map", str 검색어)`, `("align_all_center",)`
  - `editor.fill(d: Draft, r: ReviewInput, title: str, log=print, on_done=None) -> list[str]` (입력이 끝나면 `on_done(warnings)`을 바로 호출하고, 사용자가 브라우저를 닫을 때까지 기다린 뒤 경고 반환. 발행 버튼 클릭 없음)
  - `editor.SEL: dict[str, str]` (화면 요소 선택자)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_editor.py`

```python
from pathlib import Path

from naverblogbot.draft import Block, Draft
from naverblogbot.editor import plan_actions
from naverblogbot.inputs import ReviewInput


def make(tmp_path, sponsored=False):
    (tmp_path / "a.jpg").write_bytes(b"x")
    d = Draft(titles=["t"], tags=["판교맛집", "해미옥"], photos=[], confirm=[],
              blocks=[Block("lines", lines=["첫 줄", "둘째 줄"]), Block("blank"), Block("quote", text="📍 위치"),
                      Block("map"), Block("photo", file="a.jpg"), Block("photo", file="없음.jpg")],
              disclosure="[협찬] 문구" if sponsored else "")
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", sponsored, "리뷰노트" if sponsored else "")
    return d, r


def test_plan_actions_order(tmp_path):
    d, r = make(tmp_path)
    acts = plan_actions(d, r, "선택한 제목")
    assert acts == [
        ("title", "선택한 제목"),
        ("line", "첫 줄"), ("line", "둘째 줄"),
        ("enter",),
        ("quote", "📍 위치"),
        ("map", "해미옥 판교"),
        ("photo", str(tmp_path / "a.jpg")),
        ("line", "#판교맛집 #해미옥"),
        ("align_all_center",),
    ]


def test_plan_actions_disclosure_first(tmp_path):
    d, r = make(tmp_path, sponsored=True)
    acts = plan_actions(d, r, "t")
    assert acts[1] == ("bold_line", "[협찬] 문구")


def test_plan_actions_skips_unknown_photo(tmp_path):
    d, r = make(tmp_path)
    assert not any(a[0] == "photo" and "없음.jpg" in a[1] for a in plan_actions(d, r, "t"))
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_editor.py -v`
Expected: FAIL

- [ ] **Step 3: 동작 목록 구현** — `naverblogbot/editor.py`

```python
"""네이버 스마트에디터에 초안을 입력한다. 발행 버튼은 절대 누르지 않는다."""
from pathlib import Path

from .draft import Draft
from .inputs import ReviewInput
from .settings import profile_dir

WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"
LOGIN_TIMEOUT_MS = 5 * 60 * 1000

# 네이버가 화면을 바꾸면 여기만 고친다. Task 8 Step 5의 탐색 스크립트로 확인한 값.
SEL = {
    "frame": "#mainFrame",
    "title": ".se-documentTitle .se-text-paragraph",
    "body_text": ".se-component.se-text .se-text-paragraph",
    "popup_cancel": ".se-popup-button-cancel",
    "help_close": ".se-help-panel-close-button",
    "photo_button": "button.se-image-toolbar-button",
    "quote_button": "button.se-insert-quotation-default-toolbar-button",
    "map_button": "button.se-map-toolbar-button",
    "map_search": ".se-place-search-keyword input, input.react-autosuggest__input",
    "map_result_add": ".se-place-map-search-result-item:first-child .se-place-add-button",
    "map_confirm": ".se-popup-button-confirm",
    "image_component": ".se-component.se-image",
    "align_button": "button.se-align-left-toolbar-button, button[data-name='align-drop-down-with-justify']",
    "align_center": "button.se-toolbar-option-align-center-button",
}


def plan_actions(d: Draft, r: ReviewInput, title: str) -> list[tuple]:
    folder = Path(r.photo_dir)
    acts: list[tuple] = [("title", title)]
    if d.disclosure:
        acts.append(("bold_line", d.disclosure))
    for b in d.blocks:
        if b.type == "lines":
            acts.extend(("line", x) for x in b.lines)
        elif b.type == "blank":
            acts.append(("enter",))
        elif b.type == "quote":
            acts.append(("quote", b.text))
        elif b.type == "map":
            acts.append(("map", f"{r.store} {r.area}"))
        elif b.type == "photo" and (folder / b.file).is_file():
            acts.append(("photo", str(folder / b.file)))
    acts.append(("line", d.hashtag_line))
    acts.append(("align_all_center",))
    return acts
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_editor.py -v`
Expected: 3 passed

- [ ] **Step 5: 에디터 화면 탐색 (사용자 로그인 필요)**

`tools/probe_editor.py`:
```python
"""봇 전용 크롬으로 네이버 글쓰기 화면을 열고 툴바·입력 요소를 출력한다. 처음엔 창에서 로그인 필요."""
import truststore

truststore.inject_into_ssl()

from playwright.sync_api import sync_playwright

from naverblogbot.editor import SEL, WRITE_URL
from naverblogbot.settings import profile_dir

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(profile_dir()), channel="chrome", headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(WRITE_URL)
    print("로그인 후 글쓰기 화면이 뜨면 기다리세요...")
    frame = page.frame_locator(SEL["frame"])
    frame.locator(".se-toolbar").wait_for(timeout=300_000)
    for el in frame.locator(".se-toolbar button").all():
        print(el.get_attribute("class"), "|", el.get_attribute("data-name"), "|", (el.inner_text() or "").strip()[:20])
    page.screenshot(path="probe.png")
    for key, sel in SEL.items():
        if key == "frame":
            continue
        print(key, frame.locator(sel).count())
    input("엔터를 누르면 종료합니다")
    ctx.close()
```

Run: `PYTHONPATH=. .venv/Scripts/python tools/probe_editor.py`
사용자에게 "봇 창에서 네이버 로그인해 주세요"라고 요청한다. 출력된 버튼 클래스로 `SEL`의 `photo_button`, `quote_button`, `map_button`, `align_button`, `align_center`를 실제 값으로 고친다. 이어서 같은 창에서 수동으로 인용구·사진·장소를 한 번씩 넣어 보고, 각 팝업의 입력창·버튼 클래스를 개발자 도구로 확인해 `map_search`, `map_result_add`, `map_confirm`을 고친다. 인용구 입력 후 커서가 인용구 밖으로 나오는 방법(마지막 텍스트 문단 클릭으로 충분한지)과 Ctrl+B가 굵게 전환하는지 확인해 Step 6 코드에 반영한다. `probe.png`는 커밋하지 않는다(`.gitignore`에 추가).

- [ ] **Step 6: 실행기 구현** — `naverblogbot/editor.py`에 추가

```python
def _try_click(frame, selector: str, timeout: int = 1500) -> bool:
    try:
        frame.locator(selector).first.click(timeout=timeout)
        return True
    except Exception:
        return False


def _cursor_to_end(page, frame) -> None:
    frame.locator(SEL["body_text"]).last.click()
    page.keyboard.press("Control+End")


def _insert_map(page, frame, query: str) -> bool:
    try:
        frame.locator(SEL["map_button"]).click()
        search = frame.locator(SEL["map_search"]).first
        search.fill(query)
        search.press("Enter")
        frame.locator(SEL["map_result_add"]).first.click(timeout=8000)
        frame.locator(SEL["map_confirm"]).first.click(timeout=5000)
        return True
    except Exception:
        page.keyboard.press("Escape")
        return False


def _run(page, frame, act: tuple, warnings: list[str]) -> None:
    kind = act[0]
    if kind == "title":
        frame.locator(SEL["title"]).click()
        page.keyboard.insert_text(act[1])
        frame.locator(SEL["body_text"]).first.click()
    elif kind == "bold_line":
        page.keyboard.press("Control+b")
        page.keyboard.insert_text(act[1])
        page.keyboard.press("Control+b")
        page.keyboard.press("Enter")
    elif kind == "line":
        page.keyboard.insert_text(act[1])
        page.keyboard.press("Enter")
    elif kind == "enter":
        page.keyboard.press("Enter")
    elif kind == "quote":
        frame.locator(SEL["quote_button"]).click()
        page.keyboard.insert_text(act[1])
        _cursor_to_end(page, frame)
    elif kind == "photo":
        before = frame.locator(SEL["image_component"]).count()
        with page.expect_file_chooser() as fc:
            frame.locator(SEL["photo_button"]).click()
        fc.value.set_files(act[1])
        frame.locator(SEL["image_component"]).nth(before).wait_for(timeout=60_000)
        _cursor_to_end(page, frame)
    elif kind == "map":
        if not _insert_map(page, frame, act[1]):
            page.keyboard.insert_text(f"[지도: {act[1]}]")
            page.keyboard.press("Enter")
            warnings.append(f"지도를 자동으로 넣지 못했습니다. '[지도: {act[1]}]' 자리에 직접 넣어 주세요.")
        _cursor_to_end(page, frame)
    elif kind == "align_all_center":
        frame.locator(SEL["body_text"]).first.click()
        page.keyboard.press("Control+a")
        frame.locator(SEL["align_button"]).first.click()
        frame.locator(SEL["align_center"]).first.click()


def fill(d: Draft, r: ReviewInput, title: str, log=print, on_done=None) -> list[str]:
    from playwright.sync_api import sync_playwright

    warnings: list[str] = []
    acts = plan_actions(d, r, title)
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(str(profile_dir()), channel="chrome", headless=False)
        except Exception:
            ctx = p.chromium.launch_persistent_context(str(profile_dir()), channel="msedge", headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(WRITE_URL)
        log("브라우저 창에서 네이버에 로그인되어 있지 않다면 로그인해 주세요. (최대 5분 대기)")
        frame = page.frame_locator(SEL["frame"])
        frame.locator(SEL["title"]).wait_for(timeout=LOGIN_TIMEOUT_MS)
        _try_click(frame, SEL["popup_cancel"])
        _try_click(frame, SEL["help_close"])
        for i, act in enumerate(acts, 1):
            log(f"입력 중 {i}/{len(acts)}")
            try:
                _run(page, frame, act, warnings)
            except Exception as e:
                warnings.append(f"{i}번째 항목({act[0]}) 입력 중 멈췄습니다: {e}. 나머지는 draft.html을 보고 직접 넣어 주세요.")
                break
        log("입력을 마쳤습니다. 브라우저에서 검토한 뒤 직접 발행하세요.")
        if on_done:
            on_done(warnings)
        page.wait_for_event("close", timeout=0)
        ctx.close()
    return warnings
```

주의: 입력이 끝나면 `on_done(warnings)`로 경고를 바로 넘기고, `page.wait_for_event("close", timeout=0)`로 사용자가 브라우저 탭을 닫을 때까지 기다린다. 창(app.py)은 이 함수를 백그라운드 스레드에서 호출한다.

- [ ] **Step 7: 실제 네이버로 수동 검증**

사진 3장짜리 테스트 폴더와 손으로 쓴 `draft.json`(블록: lines 2줄, blank, quote, map, photo 3개)으로:
```bash
.venv/Scripts/python -c "from naverblogbot.pipeline import load_saved; from naverblogbot.inputs import ReviewInput; from naverblogbot.editor import fill; r=ReviewInput(r'C:\\Users\\HYGOOD\\Downloads\\테스트맛집','해미옥','판교','좋음',True,'리뷰노트'); print(fill(load_saved(r), r, '테스트 제목'))"
```
확인: 제목, 굵은 광고 문구, 줄, 빈 줄, 인용구, 지도, 사진 3장, 해시태그, 가운데 정렬이 순서대로 들어가고 발행 버튼은 눌리지 않음. **확인 후 이 테스트 글은 발행하지 말고 닫는다** (임시저장본은 네이버 글쓰기의 "작성 중인 글" 목록에서 삭제). 문제가 있으면 `SEL`이나 `_run`을 고치고 반복.

- [ ] **Step 8: 커밋**

```bash
echo probe.png >> .gitignore
git add naverblogbot/editor.py tools/probe_editor.py tests/test_editor.py .gitignore
git commit -m "feat: add Naver editor filler that stops before publishing"
```

---

### Task 9: 창 (app.py) + 진입점 (run.py)

**Files:**
- Create: `naverblogbot/app.py`, `run.py`

**Interfaces:**
- Consumes: `settings.load/save/Settings`, `inputs.ReviewInput/validate/missing_judgments`, `pipeline.make_draft/load_saved/friendly_error/Result`, `editor.fill`
- Produces: `app.main() -> None`

- [ ] **Step 1: 구현** — `naverblogbot/app.py`

```python
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import anthropic

from . import editor, pipeline, settings
from .inputs import ReviewInput, missing_judgments, validate


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, s: settings.Settings):
        super().__init__(master)
        self.title("설정")
        self.s = s
        self.saved = False
        ttk.Label(self, text="Anthropic API 키").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.key = ttk.Entry(self, width=60, show="*")
        self.key.insert(0, s.api_key)
        self.key.grid(row=0, column=1, padx=8, pady=4)
        ttk.Label(self, text="모델").grid(row=1, column=0, sticky="w", padx=8)
        self.model = ttk.Combobox(self, values=["claude-opus-5", "claude-sonnet-5"], width=57)
        self.model.set(s.model)
        self.model.grid(row=1, column=1, padx=8, pady=4)
        ttk.Label(self, text="내 글 예시\n(직접 쓴 글 2~3개)").grid(row=2, column=0, sticky="nw", padx=8)
        self.samples = scrolledtext.ScrolledText(self, width=60, height=12)
        self.samples.insert("1.0", s.style_samples)
        self.samples.grid(row=2, column=1, padx=8, pady=4)
        ttk.Button(self, text="저장", command=self._save).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        self.grab_set()

    def _save(self):
        self.s.api_key = self.key.get().strip()
        self.s.model = self.model.get().strip() or "claude-opus-5"
        self.s.style_samples = self.samples.get("1.0", "end").strip()
        settings.save(self.s)
        self.saved = True
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("네이버 맛집 리뷰 봇")
        self.s = settings.load()
        self.result: pipeline.Result | None = None
        self._build()
        if not self.s.api_key:
            self.after(200, self.open_settings)

    def _entry(self, row, label, width=50):
        ttk.Label(self.form, text=label).grid(row=row, column=0, sticky="w", pady=2)
        e = ttk.Entry(self.form, width=width)
        e.grid(row=row, column=1, columnspan=2, sticky="we", pady=2)
        return e

    def _text(self, row, label, height=3):
        ttk.Label(self.form, text=label).grid(row=row, column=0, sticky="nw", pady=2)
        t = tk.Text(self.form, width=50, height=height)
        t.grid(row=row, column=1, columnspan=2, sticky="we", pady=2)
        return t

    def _build(self):
        menu = tk.Menu(self)
        menu.add_command(label="설정", command=self.open_settings)
        self.config(menu=menu)
        self.form = ttk.Frame(self, padding=12)
        self.form.grid(row=0, column=0, sticky="nsew")
        ttk.Label(self.form, text="사진 폴더").grid(row=0, column=0, sticky="w")
        self.folder = ttk.Entry(self.form, width=40)
        self.folder.grid(row=0, column=1, sticky="we")
        ttk.Button(self.form, text="찾기", command=self._pick).grid(row=0, column=2)
        self.store = self._entry(1, "가게명")
        self.area = self._entry(2, "동네")
        self.impression = self._entry(3, "한 줄 소감")
        self.sponsored = tk.BooleanVar(value=False)
        vf = ttk.Frame(self.form)
        vf.grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Label(self.form, text="방문 유형").grid(row=4, column=0, sticky="w")
        ttk.Radiobutton(vf, text="내돈내산", variable=self.sponsored, value=False).pack(side="left")
        ttk.Radiobutton(vf, text="협찬", variable=self.sponsored, value=True).pack(side="left")
        self.sponsor = self._entry(5, "업체·체험단명")
        self.menu_t = self._text(6, "먹은 메뉴·가격")
        self.cons = self._entry(7, "아쉬운 점")
        self.target = self._entry(8, "추천 대상")
        self.extra = self._entry(9, "웨이팅·주차·영업시간")
        self.keywords = self._entry(10, "필수 키워드(쉼표)")
        self.guide_t = self._text(11, "캠페인 가이드")
        self.make_btn = ttk.Button(self.form, text="초안 만들기", command=self.on_make)
        self.make_btn.grid(row=12, column=1, sticky="w", pady=8)
        self.status = ttk.Label(self.form, text="", foreground="#03c75a")
        self.status.grid(row=13, column=0, columnspan=3, sticky="w")
        res = ttk.LabelFrame(self, text="결과", padding=12)
        res.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        self.title_var = tk.IntVar(value=0)
        self.title_btns = [ttk.Radiobutton(res, variable=self.title_var, value=i) for i in range(3)]
        for i, b in enumerate(self.title_btns):
            b.grid(row=i, column=0, sticky="w")
        self.notes = scrolledtext.ScrolledText(res, width=60, height=20, state="disabled")
        self.notes.grid(row=3, column=0, pady=6)
        bf = ttk.Frame(res)
        bf.grid(row=4, column=0, sticky="e")
        ttk.Button(bf, text="미리보기 열기", command=self.on_preview).pack(side="left", padx=4)
        self.fill_btn = ttk.Button(bf, text="네이버 에디터에 입력", command=self.on_fill, state="disabled")
        self.fill_btn.pack(side="left")

    def _pick(self):
        path = filedialog.askdirectory(title="사진 폴더 선택")
        if path:
            self.folder.delete(0, "end")
            self.folder.insert(0, path)

    def _review(self) -> ReviewInput:
        return ReviewInput(
            photo_dir=Path(self.folder.get().strip()), store=self.store.get().strip(), area=self.area.get().strip(),
            impression=self.impression.get().strip(), sponsored=self.sponsored.get(), sponsor=self.sponsor.get().strip(),
            menu=self.menu_t.get("1.0", "end").strip(), cons=self.cons.get().strip(), target=self.target.get().strip(),
            extra=self.extra.get().strip(), keywords=self.keywords.get().strip(), guide=self.guide_t.get("1.0", "end").strip())

    def _set_status(self, text):
        self.after(0, lambda: self.status.config(text=text))

    def _show_notes(self, lines):
        self.notes.config(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", "\n".join(lines))
        self.notes.config(state="disabled")

    def open_settings(self):
        dlg = SettingsDialog(self, self.s)
        self.wait_window(dlg)

    def on_make(self):
        if not self.s.api_key:
            messagebox.showwarning("설정 필요", "먼저 설정에서 API 키를 입력하세요.")
            return
        r = self._review()
        errors = validate(r)
        if errors:
            messagebox.showerror("입력 확인", "\n".join(errors))
            return
        missing = missing_judgments(r)
        if missing and not messagebox.askyesno(
                "비어 있는 항목", f"{', '.join(missing)}이(가) 비어 있습니다.\n봇은 이 내용을 지어내지 않고 빼고 씁니다. 계속할까요?"):
            return
        self.make_btn.config(state="disabled")
        self._set_status("초안 만드는 중... (1분 정도 걸려요)")
        threading.Thread(target=self._make_worker, args=(r,), daemon=True).start()

    def _make_worker(self, r):
        try:
            client = anthropic.Anthropic(api_key=self.s.api_key)
            result = pipeline.make_draft(r, self.s, client)
            self.after(0, lambda: self._on_made(result))
        except Exception as e:
            msg = pipeline.friendly_error(e)
            self.after(0, lambda: self._on_failed(msg))

    def _on_made(self, result):
        self.result = result
        for b, t in zip(self.title_btns, result.draft.titles):
            b.config(text=f"{t} ({len(t)}자)")
        notes = []
        if result.warnings:
            notes += ["[경고]"] + [f"- {w}" for w in result.warnings] + [""]
        notes += ["[발행 전 체크리스트]"] + [f"- {c}" for c in result.checklist]
        self._show_notes(notes)
        self.make_btn.config(state="normal")
        self.fill_btn.config(state="normal")
        self._set_status(f"초안 완료. {result.html_path}에 저장했습니다.")

    def _on_failed(self, msg):
        self.make_btn.config(state="normal")
        self._set_status("")
        messagebox.showerror("초안 만들기 실패", msg)

    def on_preview(self):
        if self.result:
            webbrowser.open(self.result.html_path.as_uri())

    def on_fill(self):
        if not self.result:
            return
        r = self._review()
        title = self.result.draft.titles[self.title_var.get()]
        self.fill_btn.config(state="disabled")
        threading.Thread(target=self._fill_worker, args=(r, title), daemon=True).start()

    def _on_filled(self, warnings):
        if warnings:
            self.after(0, lambda: messagebox.showwarning("에디터 입력 확인", "\n".join(warnings)))

    def _fill_worker(self, r, title):
        try:
            editor.fill(self.result.draft, r, title, log=self._set_status, on_done=self._on_filled)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("에디터 입력 실패", f"{e}\n\ndraft.html을 보고 직접 붙여넣어 주세요."))
        finally:
            self.after(0, lambda: self.fill_btn.config(state="normal"))


def main():
    App().mainloop()
```

`run.py`:
```python
import truststore

truststore.inject_into_ssl()

from naverblogbot.app import main

main()
```

- [ ] **Step 2: 창 실행 확인 (수동)**

Run: `NAVERBLOGBOT_HOME=$(mktemp -d) .venv/Scripts/python run.py`
확인: 설정 창이 자동으로 뜨고, 저장 후 메인 창의 모든 입력란이 보임. 빈 가게명으로 [초안 만들기] → "가게명을 입력하세요." 오류창. 창을 닫으면 종료.

- [ ] **Step 3: 실제 Claude 호출 확인 (API 비용 약 400원, 사용자 API 키 필요)**

사용자에게 실제 맛집 사진 폴더(또는 테스트용 음식 사진 13장 이상)를 받아 `run.py`로 초안 생성. 확인: 1~2분 안에 제목 3개·체크리스트 표시, `draft.html` 열면 가운데 정렬·짧은 줄·인용구·사진 순서·해시태그가 보이고 메모에 없는 사실이 없음. 문제가 있으면 `writer._RULES`를 고치고 반복.

- [ ] **Step 4: 전체 테스트 + 커밋**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 모두 통과

```bash
git add naverblogbot/app.py run.py
git commit -m "feat: add desktop window and entry point"
```

---

### Task 10: exe 빌드 + 자동 배포 + 사용 설명서

**Files:**
- Create: `build.bat`, `.github/workflows/release.yml`, `README.md`

- [ ] **Step 1: 빌드 스크립트** — `build.bat`

```bat
@echo off
.venv\Scripts\python -m PyInstaller --noconfirm --onefile --windowed --name naverblogbot --collect-all playwright run.py
```

- [ ] **Step 2: 로컬 빌드 + 실행 확인**

Run: `cmd //c build.bat && ls -la dist/naverblogbot.exe`
Expected: `dist/naverblogbot.exe` 생성 (약 60~120MB)
확인: exe 더블클릭 → 창이 뜸 → 설정 저장 → (Task 9 Step 3의 사진 폴더로) 초안 만들기 성공 → [네이버 에디터에 입력]으로 크롬이 열리고 입력됨. 회사망에서 AI 연결 오류가 나지 않아야 함(truststore). 실패 시 `--collect-all playwright` 누락 여부, 콘솔 창을 보려면 `--windowed`를 잠시 빼고 다시 빌드해 오류 확인.

- [ ] **Step 3: 자동 배포** — `.github/workflows/release.yml`

```yaml
name: release

on:
  push:
    tags: ["v*"]
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m pytest -q
      - run: python -m PyInstaller --noconfirm --onefile --windowed --name naverblogbot --collect-all playwright run.py
      - uses: actions/upload-artifact@v4
        with:
          name: naverblogbot
          path: dist/naverblogbot.exe
      - uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: dist/naverblogbot.exe
```

- [ ] **Step 4: 사용 설명서** — `README.md`

```markdown
# 네이버 맛집 리뷰 봇

맛집 사진과 한 줄 소감을 넣으면, 상위 노출 맛집 글 형식에 맞춘 리뷰 초안을 만들어 네이버 글쓰기 화면에 입력해 줍니다. **발행 버튼은 누르지 않습니다.** 검토 후 직접 발행하세요.

## 설치

1. [Releases](../../releases)에서 `naverblogbot.exe`를 내려받습니다.
2. 처음 실행하면 "Windows의 PC 보호" 창이 뜹니다. **추가 정보 → 실행**을 누르세요. (코드 서명이 없는 프로그램이라 뜨는 경고입니다)
3. 크롬이 설치되어 있어야 합니다. 없으면 엣지로 엽니다.

## 처음 설정

- 설정 창에 Anthropic API 키를 넣습니다. 키는 이 PC의 `%APPDATA%\naverblogbot\settings.json`에만 저장됩니다.
- "내 글 예시"에 직접 쓴 블로그 글 2~3개를 붙여넣으면 내 말투를 따라 씁니다.

## 사용법

1. 사진을 폴더 하나에 모읍니다 (jpg, png, webp. 아이폰 HEIC는 JPG로 바꿔 주세요).
2. 가게명, 동네, 한 줄 소감, 방문 유형을 채웁니다. 협찬이면 업체명, 필수 키워드, 캠페인 가이드도 넣습니다.
3. **초안 만들기** → 1~2분 뒤 제목 후보와 체크리스트가 나옵니다. 사진 폴더에 `draft.html`(미리보기)이 저장됩니다.
4. 제목을 고르고 **네이버 에디터에 입력** → 봇 전용 크롬 창이 열립니다. 처음 한 번은 그 창에서 네이버에 로그인하세요.
5. 입력이 끝나면 체크리스트대로 확인하고 직접 발행합니다.

## 지켜야 할 것

- 협찬 글은 첫 줄 광고 문구가 자동으로 들어갑니다. 체험단 사이트에서 받은 공정위 배너는 직접 글 맨 위에 넣으세요.
- 봇은 메모에 없는 맛·가격·영업시간을 지어내지 않습니다. 「확인: …」 표시는 반드시 고치세요.
- 한 번에 한 글씩 쓰고 직접 발행하세요. 대량 자동 발행은 네이버 운영정책상 위험합니다.

## 비용

글 하나에 AI 사용료 약 400원(사진 15장 기준, 기본 모델). 설정에서 더 저렴한 모델로 바꿀 수 있습니다.

## 개발

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements-dev.txt
    .venv\Scripts\python -m pytest
    build.bat

`v1.0.0` 같은 태그를 올리면 GitHub Actions가 exe를 빌드해 Releases에 올립니다.
```

- [ ] **Step 5: 커밋 + 태그로 배포 확인**

```bash
git add build.bat .github/workflows/release.yml README.md
git commit -m "build: add exe build, release workflow and Korean README"
git push origin main
git tag v0.1.0 && git push origin v0.1.0
```
확인: GitHub Actions의 release 작업이 성공하고 Releases v0.1.0에 `naverblogbot.exe`가 첨부됨. 실패 시 작업 로그를 보고 고친 뒤 태그를 새로(v0.1.1) 올린다.
