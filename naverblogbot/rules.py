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

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐〰]")
