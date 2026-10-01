import io
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from .inputs import MEDIA_EXTS, PHOTO_EXTS, VIDEO_EXTS

_EXIF_IFD = 0x8769
_DATETIME_ORIGINAL = 36867
_DATETIME = 306
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # exe에서 검은 창이 뜨지 않게


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def _ffmpeg(*args: str) -> subprocess.CompletedProcess:
    import imageio_ffmpeg

    return subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", *args],
                          capture_output=True, creationflags=_NO_WINDOW)


def _video_created(path: Path) -> str | None:
    info = _ffmpeg("-i", str(path)).stderr.decode("utf-8", "replace")
    m = re.search(r"creation_time\s*:\s*(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", info)
    if not m:
        return None
    utc = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return utc.astimezone().strftime("%Y:%m:%d %H:%M:%S")


def taken_at(path: Path) -> str:
    if is_video(path):
        created = _video_created(path)
        if created:
            return created
    else:
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                value = exif.get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL) or exif.get(_DATETIME)
                if value:
                    return str(value)
        except OSError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y:%m:%d %H:%M:%S")


def _sorted(folder: Path, exts: set[str]) -> list[Path]:
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(files, key=lambda p: (taken_at(p), p.name))


def list_photos(folder: Path) -> list[Path]:
    return _sorted(folder, PHOTO_EXTS)


def list_media(folder: Path) -> list[Path]:
    """사진과 동영상을 촬영 시각 순으로."""
    return _sorted(folder, MEDIA_EXTS)


def _video_frame(path: Path) -> Image.Image:
    for start in ("0.5", "0"):  # 아주 짧은 영상은 0.5초 지점이 없을 수 있다
        out = _ffmpeg("-loglevel", "error", "-ss", start, "-i", str(path), "-frames:v", "1",
                      "-f", "image2pipe", "-vcodec", "mjpeg", "-").stdout
        if out:
            return Image.open(io.BytesIO(out))
    raise OSError(f"동영상에서 장면을 뽑지 못했습니다: {path.name}")


def api_jpeg(path: Path, max_side: int = 1280) -> bytes:
    """API 전송용 축소 JPEG. 동영상은 한 장면을 뽑아서 보낸다."""
    img = _video_frame(path) if is_video(path) else ImageOps.exif_transpose(Image.open(path))
    with img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()
