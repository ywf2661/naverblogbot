import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from naverblogbot import cc
from naverblogbot.cc import CCError, build_command, find_claude, parse_output
from naverblogbot.inputs import ReviewInput
from naverblogbot.lookup import PlaceInfo
from tests.test_writer import DRAFT_JSON


def test_find_claude_prefers_real_exe_next_to_npm_shim(tmp_path, monkeypatch):
    exe = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    (tmp_path / "claude.cmd").write_text("x")
    monkeypatch.setattr(cc.shutil, "which", lambda name: str(tmp_path / "claude.cmd"))
    assert find_claude([]) == exe


def test_find_claude_candidates_and_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cc.shutil, "which", lambda name: None)
    (tmp_path / "claude.exe").write_bytes(b"x")
    assert find_claude([str(tmp_path / "none.exe"), str(tmp_path / "claude.exe")]) == tmp_path / "claude.exe"
    assert find_claude([str(tmp_path / "none.exe")]) is None


def test_build_command_flags(tmp_path):
    cmd = build_command(Path("claude.exe"), {"type": "object"}, ["Read"], "sonnet", tmp_path)
    assert cmd[:2] == ["claude.exe", "-p"]
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == {"type": "object"}
    assert cmd[cmd.index("--tools") + 1] == "Read" and cmd[cmd.index("--allowedTools") + 1] == "Read"
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--add-dir") + 1] == str(tmp_path)
    assert "--no-session-persistence" in cmd


def test_parse_output_success_and_errors():
    assert parse_output(json.dumps({"is_error": False, "structured_output": {"a": 1}})) == {"a": 1}
    with pytest.raises(CCError, match="한도"):
        parse_output(json.dumps({"is_error": True, "result": "Claude AI usage limit reached|1790830000"}))
    with pytest.raises(CCError, match="로그인"):
        parse_output(json.dumps({"is_error": True, "result": "Invalid API key · Please run /login"}))
    with pytest.raises(CCError, match="형식"):
        parse_output(json.dumps({"is_error": False, "result": "그냥 글"}))
    with pytest.raises(CCError, match="응답"):
        parse_output("not json")


class Recorder:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return SimpleNamespace(stdout=json.dumps({"is_error": False, "structured_output": self.result}), returncode=0)


def test_run_claude_uses_subscription_env_and_stdin(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    rec = Recorder({"ok": True})
    out = cc.run_claude("프롬프트", {"type": "object"}, ["Read"], "sonnet", tmp_path, exe=Path("claude.exe"), runner=rec)
    assert out == {"ok": True}
    cmd, kw = rec.calls[0]
    assert kw["input"] == "프롬프트"
    assert "ANTHROPIC_API_KEY" not in kw["env"]  # 키가 있으면 구독 대신 키로 과금된다


def test_write_draft_cc_saves_images_and_reads_them(tmp_path):
    Image.new("RGB", (60, 40)).save(tmp_path / "a.jpg")
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", False)
    rec = Recorder(DRAFT_JSON)
    d = cc.write_draft_cc(r, [tmp_path / "a.jpg"], "", [], PlaceInfo(parking="주차 가능"), model="sonnet", runner=rec,
                          exe=Path("claude.exe"))
    assert d.titles == DRAFT_JSON["titles"]
    cmd, kw = rec.calls[0]
    prompt = kw["input"]
    assert "사진 파일명: a.jpg" in prompt and "주차 가능" in prompt
    work = Path(cmd[cmd.index("--add-dir") + 1])
    assert str(work / "a.jpg.jpg") in prompt
    assert cmd[cmd.index("--tools") + 1] == "Read"


def test_lookup_cc_uses_web_search(tmp_path):
    rec = Recorder({"location": "", "hours": "매일 10~21시", "closed": "", "parking": "", "sources": ["https://x"]})
    info = cc.lookup_cc("도스마스", "여의도", model="sonnet", runner=rec, exe=Path("claude.exe"))
    assert info.hours == "매일 10~21시"
    cmd, kw = rec.calls[0]
    assert cmd[cmd.index("--tools") + 1] == "WebSearch" and "도스마스" in kw["input"]


def test_build_command_isolates_from_user_setup(tmp_path):
    sysfile = tmp_path / "system.txt"
    cmd = build_command(Path("claude.exe"), {"type": "object"}, ["Read"], "sonnet", tmp_path, system_file=sysfile)
    assert cmd[cmd.index("--system-prompt-file") + 1] == str(sysfile)  # 클로드 코드 기본 지시문 대신 우리 규칙
    assert cmd[cmd.index("--setting-sources") + 1] == "project"  # 사용자 플러그인·훅을 불러오지 않음
    assert "--strict-mcp-config" in cmd and "--disable-slash-commands" in cmd


def test_write_draft_cc_puts_rules_in_system_file(tmp_path):
    Image.new("RGB", (60, 40)).save(tmp_path / "a.jpg")
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", False)
    seen = {}

    def rec(cmd, **kw):
        seen["system"] = Path(cmd[cmd.index("--system-prompt-file") + 1]).read_text(encoding="utf-8")
        seen["input"] = kw["input"]
        return SimpleNamespace(stdout=json.dumps({"is_error": False, "structured_output": DRAFT_JSON}), returncode=0)
    cc.write_draft_cc(r, [tmp_path / "a.jpg"], "", [], model="sonnet", runner=rec, exe=Path("claude.exe"))
    assert "22자" in seen["system"] and "22자" not in seen["input"]
