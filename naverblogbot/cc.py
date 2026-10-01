"""구독 방식: 이 컴퓨터에 설치·로그인된 클로드 코드(수정하지 않은 공식 프로그램)를 불러서 쓴다.

봇은 구독 로그인 정보를 읽거나 저장하지 않는다. 클로드 코드가 스스로 로그인을 처리한다.
API 키 환경변수가 있으면 클로드 코드가 키로 과금하므로 실행할 때 빼고 넘긴다.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .draft import Draft, draft_from_dict
from .inputs import ReviewInput
from .lookup import PROMPT as LOOKUP_PROMPT
from .lookup import SCHEMA as LOOKUP_SCHEMA
from .lookup import PlaceInfo
from .photos import api_jpeg
from .writer import SCHEMA, build_memo, build_system, media_label

CANDIDATES = [
    r"~\.local\bin\claude.exe",
    r"%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe",
]
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TIMEOUT_S = 900
_run = subprocess.run  # 시험에서는 이것만 막는다(tests/conftest.py)


class CCError(Exception):
    pass


def find_claude(candidates: list[str] = CANDIDATES) -> Path | None:
    found = shutil.which("claude")
    if found:
        p = Path(found)
        # npm으로 깐 경우 claude.cmd가 실제 실행 파일로 넘겨준다. .cmd를 거치면 따옴표가 깨지므로 실제 파일을 직접 쓴다.
        real = p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if real.is_file():
            return real
        if p.suffix.lower() == ".exe":
            return p
    for c in candidates:
        p = Path(os.path.expanduser(os.path.expandvars(c)))
        if p.is_file():
            return p
    return None


def build_command(exe: Path, schema: dict, tools: list[str], model: str, add_dir: Path | None,
                  system_file: Path | None = None) -> list[str]:
    allowed = ",".join(tools)
    cmd = [str(exe), "-p", "--output-format", "json", "--json-schema", json.dumps(schema, ensure_ascii=False),
           "--tools", allowed, "--allowedTools", allowed, "--no-session-persistence", "--model", model,
           # 사용자의 플러그인·훅·연결 서비스를 불러오지 않는다. 불러오면 지시가 섞이고 한도를 30배 더 쓴다.
           "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands"]
    if system_file:
        cmd += ["--system-prompt-file", str(system_file)]  # 코딩용 기본 지시문 대신 우리 글쓰기 규칙
    if add_dir:
        cmd += ["--add-dir", str(add_dir)]
    return cmd


def parse_output(stdout: str) -> dict:
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as e:
        raise CCError(f"클로드 코드 응답을 읽지 못했습니다: {(stdout or '')[:200]}") from e
    if data.get("is_error"):
        msg = str(data.get("result", ""))
        low = msg.lower()
        if "limit" in low:
            raise CCError("구독 사용 한도에 도달했습니다. 한도가 풀린 뒤 다시 하거나, 설정에서 키 방식으로 바꾸세요.")
        if "login" in low or "api key" in low or "auth" in low:
            raise CCError("클로드 코드 로그인이 필요합니다. 명령 창에서 claude를 실행해 /login 으로 로그인하세요.")
        raise CCError(f"클로드 코드 오류: {msg[:300]}")
    out = data.get("structured_output")
    if not isinstance(out, dict):
        raise CCError(f"클로드 코드가 정해진 형식으로 답하지 않았습니다: {str(data.get('result', ''))[:200]}")
    return out


def run_claude(prompt: str, schema: dict, tools: list[str], model: str, add_dir: Path | None,
               system: str = "", exe: Path | None = None, runner=None) -> dict:
    runner = runner or _run
    exe = exe or find_claude()
    if not exe:
        raise CCError("클로드 코드를 찾을 수 없습니다. 클로드 코드를 설치하고 로그인하거나, 설정에서 키 방식으로 바꾸세요.")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    system_file = None
    if system and add_dir:
        system_file = Path(add_dir) / "system.txt"
        system_file.write_text(system, encoding="utf-8")
    try:
        proc = runner(build_command(exe, schema, tools, model, add_dir, system_file), input=prompt, capture_output=True,
                      text=True, encoding="utf-8", env=env, cwd=str(add_dir) if add_dir else None,
                      timeout=TIMEOUT_S, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as e:
        raise CCError(f"클로드 코드가 {TIMEOUT_S // 60}분 안에 끝나지 않았습니다.") from e
    return parse_output(proc.stdout)


def write_draft_cc(r: ReviewInput, paths: list[Path], style_samples: str, avoid: list[str],
                   place: PlaceInfo | None = None, model: str = "sonnet", runner=None,
                   exe: Path | None = None) -> Draft:
    with tempfile.TemporaryDirectory(prefix="naverblogbot-") as tmp:
        work = Path(tmp)
        files = []
        for p in paths:
            img = work / f"{p.name}.jpg"
            img.write_bytes(api_jpeg(p))
            files.append(f"- {media_label(p)} → 이미지: {img}")
        prompt = "\n\n".join([
            build_memo(r, paths, avoid, place),
            "아래 이미지 파일을 Read 도구로 모두 열어 본 뒤 작성하라. 시간을 줄이기 위해 한 번에 여러 파일을 동시에(병렬로) Read 한다. 블록의 file 값에는 이미지 경로가 아니라 파일명을 쓴다.\n"
            + "\n".join(files),
            "결과는 지정된 JSON 형식으로만 답한다.",
        ])
        data = run_claude(prompt, SCHEMA, ["Read"], model, work, system=build_system(style_samples),
                          exe=exe, runner=runner)
    return draft_from_dict(data)


def lookup_cc(store: str, area: str, model: str = "sonnet", runner=None, exe: Path | None = None) -> PlaceInfo:
    with tempfile.TemporaryDirectory(prefix="naverblogbot-") as tmp:
        data = run_claude(LOOKUP_PROMPT.format(store=store, area=area), LOOKUP_SCHEMA, ["WebSearch"], model,
                          Path(tmp), system="너는 웹 검색으로 가게 정보를 찾아 정리하는 도우미다.", exe=exe, runner=runner)
    return PlaceInfo(location=data.get("location", ""), hours=data.get("hours", ""), closed=data.get("closed", ""),
                     parking=data.get("parking", ""), sources=list(data.get("sources", [])))
