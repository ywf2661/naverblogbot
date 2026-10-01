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
