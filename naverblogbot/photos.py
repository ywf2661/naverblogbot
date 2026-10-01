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
