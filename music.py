import customtkinter as ctk
import threading
import os
import re
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox
import yt_dlp

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DEFAULT_DIR = r"D:\Soulseek Downloads\complete"
MAX_WORKERS = 3  # 동시 다운로드 수


def get_spotify_title(url):
    oembed = f"https://open.spotify.com/oembed?url={url}"
    req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()).get("title", "")


# ── 개별 다운로드 행 위젯 ──────────────────────────────────────
class DownloadRow(ctk.CTkFrame):
    def __init__(self, master, url, index):
        super().__init__(master, fg_color=("gray85", "gray20"), corner_radius=8)
        self.url = url
        self.pack(fill="x", pady=(0, 6), padx=2)

        self.grid_columnconfigure(0, weight=1)

        short = url[:60] + "..." if len(url) > 60 else url
        self.name_lbl = ctk.CTkLabel(self, text=f"{index+1}. {short}",
                                     font=ctk.CTkFont(size=11), anchor="w",
                                     text_color="gray70")
        self.name_lbl.grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 2), sticky="ew")

        self.prog = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self.prog.grid(row=1, column=0, padx=10, pady=(2, 2), sticky="ew")
        self.prog.set(0)

        self.status_lbl = ctk.CTkLabel(self, text="대기 중", font=ctk.CTkFont(size=10),
                                       text_color="gray60", anchor="w")
        self.status_lbl.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    def set_title(self, title):
        short = title[:65] + "..." if len(title) > 65 else title
        self.name_lbl.configure(text=short)

    def update(self, status, pct=None):
        self.status_lbl.configure(text=status)
        if pct is not None:
            self.prog.set(pct)

    def done(self, ok):
        if ok:
            self.update("완료", 1.0)
            self.status_lbl.configure(text_color="#4CAF50")
            self.prog.configure(progress_color="#4CAF50")
        else:
            self.update("실패", 0)
            self.status_lbl.configure(text_color="#f44336")
            self.prog.configure(progress_color="#f44336")


# ── 공통 탭 ────────────────────────────────────────────────────
class BaseTab(ctk.CTkFrame):
    def __init__(self, master, dir_ref, source):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.dir_ref = dir_ref
        self.source = source  # "youtube" or "spotify"
        self._rows = []
        self._build()

    def _build(self):
        # URL 입력
        hint = ("YouTube URL (한 줄에 하나씩, 여러 개 가능)"
                if self.source == "youtube"
                else "Spotify URL (한 줄에 하나씩, track / album / playlist)")
        ctk.CTkLabel(self, text=hint,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, pady=(12, 4), sticky="w")

        self.url_box = ctk.CTkTextbox(self, height=80, font=ctk.CTkFont(size=12))
        self.url_box.grid(row=1, column=0, sticky="ew")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=(6, 0), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(btn_row, text="붙여넣기", width=90, height=32,
                      command=self._paste).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(btn_row, text="초기화", width=70, height=32,
                      fg_color="gray30",
                      command=lambda: self.url_box.delete("1.0", "end")).grid(
            row=0, column=1, padx=(8, 0), sticky="w")

        # 옵션
        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.grid(row=3, column=0, pady=(12, 0), sticky="ew")

        ctk.CTkLabel(opt, text="포맷", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
        self.fmt_var = ctk.StringVar(value="mp3")
        fmts = ["mp3","m4a","wav","mp4"] if self.source == "youtube" else ["mp3","m4a","wav","flac"]
        ctk.CTkOptionMenu(opt, values=fmts, variable=self.fmt_var,
                          width=90, height=32).grid(row=1, column=0, pady=(4,0), sticky="w")

        ctk.CTkLabel(opt, text="음질", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=1, padx=(20,0), sticky="w")
        self.qual_var = ctk.StringVar(value="320k")
        ctk.CTkOptionMenu(opt, values=["320k","256k","192k","128k"],
                          variable=self.qual_var, width=90, height=32).grid(
            row=1, column=1, padx=(20,0), pady=(4,0), sticky="w")

        worker_lbl = ctk.CTkLabel(opt, text="동시 다운로드",
                                  font=ctk.CTkFont(size=12, weight="bold"))
        worker_lbl.grid(row=0, column=2, padx=(20,0), sticky="w")
        self.worker_var = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(opt, values=["1","2","3","4","5"],
                          variable=self.worker_var, width=70, height=32).grid(
            row=1, column=2, padx=(20,0), pady=(4,0), sticky="w")

        # 다운로드 버튼
        self.dl_btn = ctk.CTkButton(self, text="다운로드", height=42,
                                    font=ctk.CTkFont(size=14, weight="bold"),
                                    command=self._start)
        self.dl_btn.grid(row=4, column=0, pady=(14, 0), sticky="ew")

        # 진행 목록
        ctk.CTkLabel(self, text="진행 상황", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=5, column=0, pady=(14, 4), sticky="w")
        self.queue_frame = ctk.CTkScrollableFrame(self, height=170)
        self.queue_frame.grid(row=6, column=0, pady=(0, 12), sticky="ew")
        self.queue_frame.grid_columnconfigure(0, weight=1)

    def _paste(self):
        try:
            t = self.clipboard_get().strip()
            self.url_box.insert("end", t + "\n")
        except Exception:
            pass

    def _get_urls(self):
        text = self.url_box.get("1.0", "end").strip()
        return [u.strip() for u in text.splitlines() if u.strip()]

    def _start(self):
        urls = self._get_urls()
        if not urls:
            messagebox.showwarning("알림", "URL을 입력해 주세요.")
            return

        # 큐 초기화
        for w in self.queue_frame.winfo_children():
            w.destroy()
        self._rows = []
        for i, url in enumerate(urls):
            row = DownloadRow(self.queue_frame, url, i)
            row.grid(row=i, column=0, sticky="ew", pady=(0, 4), padx=2)
            self._rows.append(row)

        self.dl_btn.configure(state="disabled", text=f"{len(urls)}개 다운로드 중...")
        workers = int(self.worker_var.get())
        threading.Thread(target=self._run_all, args=(urls, workers), daemon=True).start()

    def _run_all(self, urls, workers):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._download_one, url, i): i
                       for i, url in enumerate(urls)}
            for f in futures:
                f.result()  # 예외 수집 목적
        self.after(0, self._all_done)

    def _download_one(self, url, idx):
        raise NotImplementedError

    def _all_done(self):
        self.dl_btn.configure(state="normal", text="다운로드")


# ── YouTube 탭 ────────────────────────────────────────────────
class YoutubeTab(BaseTab):
    def __init__(self, master, dir_ref):
        super().__init__(master, dir_ref, "youtube")

    def _download_one(self, url, idx):
        row = self._rows[idx]
        fmt = self.fmt_var.get()
        quality = self.qual_var.get().replace("k", "")
        is_audio = fmt in ("mp3", "m4a", "wav")

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes", 0)
                pct = (done / total) if total else 0
                spd = d.get("speed") or 0
                s = f"{spd/1024/1024:.1f} MB/s" if spd else "..."
                self.after(0, row.update, f"다운로드 중 {pct*100:.0f}% — {s}", pct)
            elif d["status"] == "finished":
                self.after(0, row.update, "변환 중...", 0.95)

        pp = [{"key":"FFmpegExtractAudio","preferredcodec":fmt,"preferredquality":quality},
              {"key":"FFmpegMetadata"}] if is_audio else []
        opts = {
            "format": "bestaudio/best" if is_audio else "bestvideo+bestaudio/best",
            "outtmpl": os.path.join(self.dir_ref[0], "%(title)s.%(ext)s"),
            "postprocessors": pp,
            "progress_hooks": [hook],
            "quiet": True, "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            title = info.get("title", url)
            self.after(0, row.set_title, title)
            self.after(0, row.done, True)
        except Exception as e:
            self.after(0, row.update, str(e)[:60])
            self.after(0, row.done, False)


# ── Spotify 탭 ────────────────────────────────────────────────
class SpotifyTab(BaseTab):
    def __init__(self, master, dir_ref):
        super().__init__(master, dir_ref, "spotify")

    def _download_one(self, url, idx):
        row = self._rows[idx]
        fmt = self.fmt_var.get()
        quality = self.qual_var.get().replace("k", "")

        try:
            self.after(0, row.update, "Spotify 정보 가져오는 중...", 0.05)
            title = get_spotify_title(url)
            if not title:
                raise Exception("곡 정보 없음")
            self.after(0, row.set_title, title)
            self.after(0, row.update, "YouTube 검색 중...", 0.1)

            def hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    done = d.get("downloaded_bytes", 0)
                    pct = 0.1 + (done / total * 0.8) if total else 0.1
                    spd = d.get("speed") or 0
                    s = f"{spd/1024/1024:.1f} MB/s" if spd else "..."
                    self.after(0, row.update, f"다운로드 중 {pct*100:.0f}% — {s}", pct)
                elif d["status"] == "finished":
                    self.after(0, row.update, "변환 중...", 0.95)

            opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(self.dir_ref[0], "%(title)s.%(ext)s"),
                "postprocessors": [
                    {"key":"FFmpegExtractAudio","preferredcodec":fmt,"preferredquality":quality},
                    {"key":"FFmpegMetadata"},
                ],
                "progress_hooks": [hook],
                "quiet": True, "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"ytsearch1:{title}"])

            self.after(0, row.done, True)
        except Exception as e:
            self.after(0, row.update, str(e)[:60])
            self.after(0, row.done, False)


# ── 메인 앱 ────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Music Downloader")
        self.geometry("700x640")
        self.resizable(False, False)
        self.dir_ref = [DEFAULT_DIR]
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Music Downloader",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        # 저장 위치 바
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, padx=24, pady=(0, 10), sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="저장 위치:", font=ctk.CTkFont(size=12),
                     text_color="gray60").grid(row=0, column=0, sticky="w")
        self.folder_lbl = ctk.CTkLabel(bar, text=self.dir_ref[0],
                                       font=ctk.CTkFont(size=11), text_color="gray70", anchor="w")
        self.folder_lbl.grid(row=0, column=1, padx=(8,8), sticky="ew")
        ctk.CTkButton(bar, text="변경", width=60, height=26,
                      command=self._pick_folder).grid(row=0, column=2)

        # 탭
        self.tabs = ctk.CTkTabview(self, height=530)
        self.tabs.grid(row=2, column=0, padx=16, pady=(0,16), sticky="nsew")
        self.tabs.add("YouTube")
        self.tabs.add("Spotify")

        YoutubeTab(self.tabs.tab("YouTube"), self.dir_ref).pack(fill="both", expand=True, padx=8)
        SpotifyTab(self.tabs.tab("Spotify"), self.dir_ref).pack(fill="both", expand=True, padx=8)

    def _pick_folder(self):
        f = filedialog.askdirectory(initialdir=self.dir_ref[0])
        if f:
            self.dir_ref[0] = f
            self.folder_lbl.configure(text=f)


if __name__ == "__main__":
    app = App()
    app.mainloop()
