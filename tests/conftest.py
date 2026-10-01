import pytest


@pytest.fixture(autouse=True)
def _never_launch_real_claude_code(monkeypatch):
    """시험 중 실제 클로드 코드가 실행돼 구독 한도를 쓰지 않게 막는다."""
    from naverblogbot import cc

    def blocked(*args, **kwargs):
        raise AssertionError("시험에서 실제 클로드 코드를 실행하려 했습니다")
    monkeypatch.setattr(cc, "_run", blocked)
