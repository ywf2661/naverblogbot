import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import anthropic

from . import editor, pipeline, settings
from .inputs import ReviewInput, missing_judgments, validate


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, s: settings.Settings):
        super().__init__(master)
        self.title("설정")
        self.s = s
        ttk.Label(self, text="Anthropic API 키").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.key = ttk.Entry(self, width=60, show="*")
        self.key.insert(0, s.api_key)
        self.key.grid(row=0, column=1, padx=8, pady=4)
        ttk.Label(self, text="모델").grid(row=1, column=0, sticky="w", padx=8)
        self.model = ttk.Combobox(self, values=["claude-opus-5", "claude-sonnet-5"], width=57)
        self.model.set(s.model)
        self.model.grid(row=1, column=1, padx=8, pady=4)
        ttk.Label(self, text="내 글 예시\n(직접 쓴 글 2~3개)").grid(row=2, column=0, sticky="nw", padx=8)
        self.samples = scrolledtext.ScrolledText(self, width=60, height=12)
        self.samples.insert("1.0", s.style_samples)
        self.samples.grid(row=2, column=1, padx=8, pady=4)
        ttk.Button(self, text="저장", command=self._save).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        self.grab_set()

    def _save(self):
        self.s.api_key = self.key.get().strip()
        self.s.model = self.model.get().strip() or "claude-opus-5"
        self.s.style_samples = self.samples.get("1.0", "end").strip()
        settings.save(self.s)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("네이버 맛집 리뷰 봇")
        self.s = settings.load()
        self.result: pipeline.Result | None = None
        self._build()
        if not self.s.api_key:
            self.after(200, self.open_settings)

    def _entry(self, row, label, width=50):
        ttk.Label(self.form, text=label).grid(row=row, column=0, sticky="w", pady=2)
        e = ttk.Entry(self.form, width=width)
        e.grid(row=row, column=1, columnspan=2, sticky="we", pady=2)
        return e

    def _text(self, row, label, height=3):
        ttk.Label(self.form, text=label).grid(row=row, column=0, sticky="nw", pady=2)
        t = tk.Text(self.form, width=50, height=height)
        t.grid(row=row, column=1, columnspan=2, sticky="we", pady=2)
        return t

    def _build(self):
        menu = tk.Menu(self)
        menu.add_command(label="설정", command=self.open_settings)
        self.config(menu=menu)
        self.form = ttk.Frame(self, padding=12)
        self.form.grid(row=0, column=0, sticky="nsew")
        ttk.Label(self.form, text="사진 폴더").grid(row=0, column=0, sticky="w")
        self.folder = ttk.Entry(self.form, width=40)
        self.folder.grid(row=0, column=1, sticky="we")
        ttk.Button(self.form, text="찾기", command=self._pick).grid(row=0, column=2)
        self.store = self._entry(1, "가게명")
        self.area = self._entry(2, "동네")
        self.impression = self._entry(3, "한 줄 소감")
        self.sponsored = tk.BooleanVar(value=False)
        ttk.Label(self.form, text="방문 유형").grid(row=4, column=0, sticky="w")
        vf = ttk.Frame(self.form)
        vf.grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(vf, text="내돈내산", variable=self.sponsored, value=False).pack(side="left")
        ttk.Radiobutton(vf, text="협찬", variable=self.sponsored, value=True).pack(side="left")
        self.sponsor = self._entry(5, "업체·체험단명")
        self.menu_t = self._text(6, "먹은 메뉴·가격")
        self.cons = self._entry(7, "아쉬운 점")
        self.target = self._entry(8, "추천 대상")
        self.extra = self._entry(9, "웨이팅·주차·영업시간")
        self.keywords = self._entry(10, "필수 키워드(쉼표)")
        self.guide_t = self._text(11, "캠페인 가이드")
        self.lookup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.form, text="영업시간·주차 자동 검색 (직접 적으면 검색 안 함, 약 200원·1~2분 추가)",
                        variable=self.lookup_var).grid(row=12, column=1, columnspan=2, sticky="w")
        self.make_btn = ttk.Button(self.form, text="초안 만들기", command=self.on_make)
        self.make_btn.grid(row=13, column=1, sticky="w", pady=8)
        self.status = ttk.Label(self.form, text="", foreground="#03c75a")
        self.status.grid(row=14, column=0, columnspan=3, sticky="w")

        res = ttk.LabelFrame(self, text="결과", padding=12)
        res.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        self.title_var = tk.IntVar(value=0)
        self.title_btns = [ttk.Radiobutton(res, variable=self.title_var, value=i) for i in range(3)]
        for i, b in enumerate(self.title_btns):
            b.grid(row=i, column=0, sticky="w")
        self.notes = scrolledtext.ScrolledText(res, width=60, height=18, state="disabled")
        self.notes.grid(row=3, column=0, pady=6)
        ttk.Label(res, text="① 작성용 크롬을 열고 직접 로그인 → 블로그 [글쓰기] 화면을 띄운 뒤 ② [에디터에 입력]",
                  foreground="#555").grid(row=4, column=0, sticky="w")
        bf = ttk.Frame(res)
        bf.grid(row=5, column=0, sticky="e", pady=4)
        ttk.Button(bf, text="미리보기 열기", command=self.on_preview).pack(side="left", padx=4)
        ttk.Button(bf, text="① 작성용 크롬 열기", command=self.on_open_browser).pack(side="left", padx=4)
        self.fill_btn = ttk.Button(bf, text="② 에디터에 입력", command=self.on_fill, state="disabled")
        self.fill_btn.pack(side="left")

    def _pick(self):
        path = filedialog.askdirectory(title="사진 폴더 선택")
        if path:
            self.folder.delete(0, "end")
            self.folder.insert(0, path)

    def _review(self) -> ReviewInput:
        return ReviewInput(
            photo_dir=Path(self.folder.get().strip()), store=self.store.get().strip(), area=self.area.get().strip(),
            impression=self.impression.get().strip(), sponsored=self.sponsored.get(), sponsor=self.sponsor.get().strip(),
            menu=self.menu_t.get("1.0", "end").strip(), cons=self.cons.get().strip(), target=self.target.get().strip(),
            extra=self.extra.get().strip(), keywords=self.keywords.get().strip(),
            guide=self.guide_t.get("1.0", "end").strip())

    def _set_status(self, text):
        self.after(0, lambda: self.status.config(text=text))

    def _show_notes(self, lines):
        self.notes.config(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", "\n".join(lines))
        self.notes.config(state="disabled")

    def open_settings(self):
        self.wait_window(SettingsDialog(self, self.s))

    def on_make(self):
        if not self.s.api_key:
            messagebox.showwarning("설정 필요", "먼저 설정에서 API 키를 입력하세요.")
            return
        r = self._review()
        errors = validate(r)
        if errors:
            messagebox.showerror("입력 확인", "\n".join(errors))
            return
        missing = missing_judgments(r)
        if missing and not messagebox.askyesno(
                "비어 있는 항목",
                f"{', '.join(missing)}이(가) 비어 있습니다.\n봇은 이 내용을 지어내지 않고 빼고 씁니다. 계속할까요?"):
            return
        self.make_btn.config(state="disabled")
        self._set_status("초안 만드는 중...")
        threading.Thread(target=self._make_worker, args=(r, self.lookup_var.get()), daemon=True).start()

    def _make_worker(self, r, lookup):
        try:
            client = anthropic.Anthropic(api_key=self.s.api_key)
            result = pipeline.make_draft(r, self.s, client, lookup=lookup, log=self._set_status)
            self.after(0, lambda: self._on_made(result))
        except Exception as e:
            msg = pipeline.friendly_error(e)
            self.after(0, lambda: self._on_failed(msg))

    def _on_made(self, result):
        self.result = result
        for b, t in zip(self.title_btns, result.draft.titles):
            b.config(text=f"{t} ({len(t)}자)")
        notes = []
        if result.warnings:
            notes += ["[경고]"] + [f"- {w}" for w in result.warnings] + [""]
        notes += ["[발행 전 체크리스트]"] + [f"- {c}" for c in result.checklist]
        self._show_notes(notes)
        self.make_btn.config(state="normal")
        self.fill_btn.config(state="normal")
        self._set_status(f"초안 완료. {result.html_path}에 저장했습니다.")

    def _on_failed(self, msg):
        self.make_btn.config(state="normal")
        self._set_status("")
        messagebox.showerror("초안 만들기 실패", msg)

    def on_preview(self):
        if self.result:
            webbrowser.open(self.result.html_path.as_uri())

    def on_open_browser(self):
        try:
            editor.open_browser()
            self._set_status("작성용 크롬을 열었습니다. 로그인하고 블로그 [글쓰기] 화면을 띄워 주세요.")
        except editor.EditorError as e:
            messagebox.showerror("크롬 열기 실패", str(e))

    def on_fill(self):
        if not self.result:
            return
        r = self._review()
        title = self.result.draft.titles[self.title_var.get()]
        self.fill_btn.config(state="disabled")
        threading.Thread(target=self._fill_worker, args=(r, title), daemon=True).start()

    def _on_filled(self, warnings):
        if warnings:
            self.after(0, lambda: messagebox.showwarning("에디터 입력 확인", "\n".join(warnings)))

    def _fill_worker(self, r, title):
        try:
            editor.fill(self.result.draft, r, title, log=self._set_status, on_done=self._on_filled)
        except editor.EditorError as e:
            msg = str(e)
            self.after(0, lambda: messagebox.showerror("에디터 입력 실패", msg))
        except Exception as e:
            msg = f"{e}\n\ndraft.html을 보고 직접 붙여넣어 주세요."
            self.after(0, lambda: messagebox.showerror("에디터 입력 실패", msg))
        finally:
            self.after(0, lambda: self.fill_btn.config(state="normal"))


def main():
    App().mainloop()
