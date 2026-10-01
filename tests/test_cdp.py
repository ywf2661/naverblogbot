import json

import pytest

from naverblogbot.cdp import CDPError, CDPPage, key_events, pick_write_target


def test_key_events_enter_has_text():
    down, up = key_events("Enter")
    assert down == {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                    "nativeVirtualKeyCode": 13, "modifiers": 0, "text": "\r", "unmodifiedText": "\r"}
    assert up["type"] == "keyUp" and up["windowsVirtualKeyCode"] == 13


def test_key_events_arrow_is_raw():
    down, up = key_events("ArrowDown")
    assert down["type"] == "rawKeyDown" and down["windowsVirtualKeyCode"] == 40 and "text" not in down


def test_key_events_ctrl_a():
    down, _ = key_events("Control+a")
    assert down["modifiers"] == 2 and down["key"] == "a" and down["code"] == "KeyA"
    assert down["windowsVirtualKeyCode"] == 65 and down["type"] == "rawKeyDown"


def test_key_events_unknown():
    with pytest.raises(ValueError):
        key_events("F13")


def test_pick_write_target():
    targets = [
        {"type": "browser_ui", "url": "chrome://omnibox-popup.top-chrome/", "webSocketDebuggerUrl": "ws://x/ui"},
        {"type": "page", "url": "https://www.naver.com/", "webSocketDebuggerUrl": "ws://x/main"},
        {"type": "page", "url": "https://blog.naver.com/ywf2661?Redirect=Write&", "webSocketDebuggerUrl": "ws://x/write"},
    ]
    assert pick_write_target(targets) == "ws://x/write"
    assert pick_write_target(targets[:2]) is None


class FakeWS:
    def __init__(self, incoming):
        self.sent = []
        self.incoming = list(incoming)

    def send(self, data):
        self.sent.append(json.loads(data))

    def recv(self):
        return json.dumps(self.incoming.pop(0))

    def settimeout(self, t):
        pass


def test_send_matches_id_and_keeps_events():
    ws = FakeWS([{"method": "Page.fileChooserOpened", "params": {"backendNodeId": 7}},
                 {"id": 1, "result": {"ok": True}}])
    page = CDPPage(ws)
    assert page.send("Page.enable") == {"ok": True}
    assert ws.sent == [{"id": 1, "method": "Page.enable", "params": {}}]
    assert page.wait_event("Page.fileChooserOpened", timeout=1) == {"backendNodeId": 7}


def test_send_raises_on_error():
    page = CDPPage(FakeWS([{"id": 1, "error": {"message": "boom"}}]))
    with pytest.raises(CDPError, match="boom"):
        page.send("Runtime.evaluate")


def test_eval_returns_value_and_raises_on_exception():
    page = CDPPage(FakeWS([{"id": 1, "result": {"result": {"type": "number", "value": 3}}},
                           {"id": 2, "result": {"result": {}, "exceptionDetails": {"text": "bad js"}}}]))
    assert page.eval("1+2") == 3
    with pytest.raises(CDPError, match="bad js"):
        page.eval("x(")
