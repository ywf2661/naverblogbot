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


import subprocess

import imageio_ffmpeg

from naverblogbot.photos import is_video, list_media


def make_video(path, created=None):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "lavfi",
           "-i", "testsrc=duration=2:size=1920x1080:rate=10", "-pix_fmt", "yuv420p"]
    if created:
        cmd += ["-metadata", f"creation_time={created}"]
    subprocess.run(cmd + [str(path)], check=True)


def utc_of_local(local: str) -> str:
    """이 PC 시간대의 현지 시각을 동영상 메타데이터 형식(UTC)으로. 시험이 어느 시간대에서 돌아도 같게 한다."""
    from datetime import datetime, timezone
    return datetime.strptime(local, "%Y-%m-%d %H:%M:%S").astimezone().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_list_media_mixes_photos_and_videos_by_time(tmp_path):
    save_img(tmp_path / "a.jpg", taken="2026:10:01 13:50:00")
    save_img(tmp_path / "c.jpg", taken="2026:10:01 13:55:00")
    make_video(tmp_path / "b.mov", created=utc_of_local("2026-10-01 13:52:00"))
    assert [p.name for p in list_media(tmp_path)] == ["a.jpg", "b.mov", "c.jpg"]


def test_video_taken_at_is_local_time(tmp_path):
    make_video(tmp_path / "v.mp4", created=utc_of_local("2026-10-01 13:52:00"))
    assert taken_at(tmp_path / "v.mp4") == "2026:10:01 13:52:00"


def test_api_jpeg_from_video_frame(tmp_path):
    make_video(tmp_path / "v.mp4")
    out = Image.open(io.BytesIO(api_jpeg(tmp_path / "v.mp4")))
    assert out.format == "JPEG" and max(out.size) == 1280


def test_is_video():
    from pathlib import Path
    assert is_video(Path("a.MOV")) and is_video(Path("b.mp4")) and not is_video(Path("c.jpg"))
