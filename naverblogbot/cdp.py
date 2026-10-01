"""작성용 크롬의 '글쓰기 탭 하나'에만 개발자 도구 프로토콜(CDP)로 붙는 작은 클라이언트.

Playwright는 연결할 때 모든 탭에 붙는데, 크롬이 잠재운 뒤쪽 탭이 응답하지 않으면 연결이 멈추고
크롬 154의 browser_ui 대상에서는 드라이버가 죽는다. 그래서 글쓰기 탭 하나만 직접 다룬다.
에디터는 같은 출처의 #mainFrame 안에 있으므로 요소 찾기는 그 문서에서 한다.
"""
import json
import time
import urllib.request

KEYS = {
    "Enter": ("Enter", "Enter", 13, "\r"),
    "ArrowUp": ("ArrowUp", "ArrowUp", 38, None),
    "ArrowDown": ("ArrowDown", "ArrowDown", 40, None),
    "ArrowRight": ("ArrowRight", "ArrowRight", 39, None),
    "End": ("End", "End", 35, None),
    "Home": ("Home", "Home", 36, None),
    "Delete": ("Delete", "Delete", 46, None),
    "Escape": ("Escape", "Escape", 27, None),
    "a": ("a", "KeyA", 65, "a"),
}
MODIFIERS = {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}

_JS_PRELUDE = """
const __f = document.querySelector('#mainFrame');
const __d = (__f && __f.contentDocument) || document;
const __all = (sel, vis) => {
  let a = Array.from(__d.querySelectorAll(sel));
  if (vis) a = a.filter(e => e.getClientRects().length > 0);
  return a;
};
const __pick = (sel, idx, vis) => { const a = __all(sel, vis); return a[idx < 0 ? a.length + idx : idx]; };
"""


class CDPError(Exception):
    pass


def is_write_page(url: str) -> bool:
    return "Redirect=Write" in url or "/postwrite" in url or "PostWriteForm" in url


def key_events(combo: str) -> tuple[dict, dict]:
    *mods, key = combo.split("+")
    if key not in KEYS:
        raise ValueError(f"지원하지 않는 키: {combo}")
    name, code, vk, text = KEYS[key]
    modifiers = sum(MODIFIERS[m] for m in mods)
    down = {"type": "keyDown" if text and not modifiers else "rawKeyDown", "key": name, "code": code,
            "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk, "modifiers": modifiers}
    if text and not modifiers:
        down.update(text=text, unmodifiedText=text)
    up = {"type": "keyUp", "key": name, "code": code, "windowsVirtualKeyCode": vk,
          "nativeVirtualKeyCode": vk, "modifiers": modifiers}
    return down, up


def pick_write_target(targets: list[dict]) -> str | None:
    for t in targets:
        if t.get("type") == "page" and is_write_page(t.get("url", "")):
            return t["webSocketDebuggerUrl"]
    return None


class CDPPage:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self._events: list[tuple[str, dict]] = []

    # --- 프로토콜 ---
    def _recv(self, deadline: float) -> dict:
        self.ws.settimeout(max(0.05, deadline - time.time()))
        try:
            return json.loads(self.ws.recv())
        except Exception as e:  # 시간 초과·연결 끊김
            raise CDPError(f"크롬 응답이 없습니다: {e}") from e

    def send(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        self._id += 1
        my_id = self._id
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while True:
            msg = self._recv(deadline)
            if msg.get("id") == my_id:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})
            if "method" in msg:
                self._events.append((msg["method"], msg.get("params", {})))

    def wait_event(self, method: str, timeout: float = 10) -> dict:
        deadline = time.time() + timeout
        while True:
            for i, (m, params) in enumerate(self._events):
                if m == method:
                    del self._events[i]
                    return params
            if time.time() > deadline:
                raise CDPError(f"{method} 이벤트가 오지 않았습니다.")
            msg = self._recv(deadline)
            if "method" in msg:
                self._events.append((msg["method"], msg.get("params", {})))

    def eval(self, js: str):
        res = self.send("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in res:
            raise CDPError(f"스크립트 오류: {res['exceptionDetails'].get('text')}")
        return res.get("result", {}).get("value")

    # --- 에디터 문서(#mainFrame) 다루기 ---
    def _q(self, body: str):
        return self.eval(f"(() => {{{_JS_PRELUDE}{body}}})()")

    def count(self, sel: str, visible: bool = False) -> int:
        return self._q(f"return __all({json.dumps(sel)}, {json.dumps(visible)}).length;")

    def attr(self, sel: str, name: str, index: int = 0, visible: bool = False):
        return self._q(f"const e = __pick({json.dumps(sel)}, {index}, {json.dumps(visible)});"
                       f" return e ? e.getAttribute({json.dumps(name)}) : null;")

    def texts(self, sel: str, drop: str = "") -> list[str]:
        return self._q(f"return __all({json.dumps(sel)}, false).map(e => {{ const c = e.cloneNode(true);"
                       f" if ({json.dumps(drop)}) c.querySelectorAll({json.dumps(drop or 'x')}).forEach(x => x.remove());"
                       f" return c.textContent; }});")

    def has_text(self, sel: str, text: str) -> bool:
        return self._q(f"return __all({json.dumps(sel)}, true)"
                       f".some(e => e.innerText.includes({json.dumps(text, ensure_ascii=False)}));")

    def wait_for(self, sel: str, index: int = 0, visible: bool = True, timeout: float = 10) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._q(f"return !!__pick({json.dumps(sel)}, {index}, {json.dumps(visible)});"):
                return
            time.sleep(0.2)
        raise CDPError(f"화면 요소를 찾지 못했습니다: {sel}")

    def click(self, sel: str, index: int = 0, timeout: float = 10) -> None:
        self.wait_for(sel, index, visible=True, timeout=timeout)
        point = self._q(
            f"const e = __pick({json.dumps(sel)}, {index}, true); e.scrollIntoView({{block: 'center'}});"
            " const r = e.getBoundingClientRect(); const o = __f && __f.contentDocument ? __f.getBoundingClientRect() : {left: 0, top: 0};"
            " return [o.left + r.left + r.width / 2, o.top + r.top + r.height / 2];")
        x, y = point
        self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        self.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        self.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

    def insert_text(self, text: str) -> None:
        self.send("Input.insertText", {"text": text})

    def press(self, combo: str) -> None:
        down, up = key_events(combo)
        self.send("Input.dispatchKeyEvent", down)
        self.send("Input.dispatchKeyEvent", up)

    def fill(self, sel: str, text: str) -> None:
        self.click(sel)
        self.press("Control+a")
        self.press("Delete")
        self.insert_text(text)

    def choose_file(self, button_sel: str, path: str, timeout: float = 10) -> None:
        self._events = [e for e in self._events if e[0] != "Page.fileChooserOpened"]
        self.click(button_sel)
        opened = self.wait_event("Page.fileChooserOpened", timeout=timeout)
        self.send("DOM.setFileInputFiles", {"files": [path], "backendNodeId": opened["backendNodeId"]})

    def sleep(self, ms: int) -> None:
        time.sleep(ms / 1000)

    # --- 연결 ---
    def start(self) -> None:
        self.send("Page.enable")
        self.send("Page.bringToFront")
        self.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        self.send("Page.setInterceptFileChooserDialog", {"enabled": True})

    def close(self) -> None:
        """사용자가 나중에 직접 사진을 올릴 수 있도록 파일 선택 가로채기를 끄고 연결만 끊는다(탭은 그대로)."""
        try:
            self.send("Page.setInterceptFileChooserDialog", {"enabled": False}, timeout=5)
            self.send("Emulation.setFocusEmulationEnabled", {"enabled": False}, timeout=5)
        finally:
            self.ws.close()


def connect_write_page(port: int) -> CDPPage:
    import websocket

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
    except OSError as e:
        raise CDPError("작성용 크롬이 열려 있지 않습니다.") from e
    ws_url = pick_write_target(targets)
    if not ws_url:
        raise CDPError("글쓰기 화면을 찾지 못했습니다.")
    page = CDPPage(websocket.create_connection(ws_url, suppress_origin=True, timeout=30))
    page.start()
    return page
