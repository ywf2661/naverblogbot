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
    if str(r.photo_dir).strip() in ("", "."):
        return ["사진 폴더를 선택하세요."]
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
    heic = sum(e in HEIC_EXTS for e in exts)
    if heic:
        errors.append(f"HEIC 사진 {heic}장은 쓸 수 없습니다. JPG로 바꾸거나 폴더에서 빼 주세요 "
                      "(아이폰: 설정 > 카메라 > 포맷 > 높은 호환성).")
    elif not any(e in PHOTO_EXTS for e in exts):
        errors.append("폴더에 사진(jpg, png, webp)이 없습니다.")
    return errors


def missing_judgments(r: ReviewInput) -> list[str]:
    missing = []
    if not r.cons.strip():
        missing.append("아쉬운 점")
    if not r.target.strip():
        missing.append("추천 대상")
    return missing
