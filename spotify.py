import customtkinter as ctk
import threading
import os
import re
import json
import urllib.request
from tkinter import filedialog, messagebox
import yt_dlp

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


def get_spotify_track_info(url):
    """Spotify oEmbed API로 곡 정보 가져오기 (인증 불필요)"""
    oembed_url = f"https://open.spotify.com/oembed?url={url}"
    req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    # title 형식: "Track Name" or "Track Name - Artist"
    title = data.get("title", "")
    return title


def get_spotify_playlist_tracks(url):
    """플레이리스트/앨범 페이지에서 트랙 목록 스크래핑"""
    track_id = re.search(r"spotify\.com/(?:track|album|playlist)/([A-Za-z0-9]+)", url)
    if not track_id:
        return []
    # oEmbed는 단일 트랙만 지원 → 플레이리스트는 title만 반환
    title = get_spotify_track_info(url)
    return [title] if title else []


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Spotify Downloader")
        self.geometry("680x560")
        self.resizable(False, False)
        self.download_dir = os.path.expanduser("~/Downloads")
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Spotify Downloader",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, pady=(28, 4), padx=24, sticky="w")

        ctk.CTkLabel(self, text="Spotify URL → YouTube 검색 → MP3 다운로드  (API 키 불필요)",
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=1, column=0, pady=(0, 18), padx=24, sticky="w")

        # URL
        ctk.CTkLabel(self, text="Spotify URL",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=2, column=0, padx=24, pady=(0, 4), sticky="w")

        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.grid(row=3, column=0, padx=24, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://open.spotify.com/track/...",
            height=40, font=ctk.CTkFont(size=12))
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(url_frame, text="붙여넣기", width=80, height=40,
                      command=self._paste_url).grid(row=0, column=1)

        # Options
        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.grid(row=4, column=0, padx=24, pady=(16, 0), sticky="ew")

        ctk.CTkLabel(opt, text="포맷", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        self.fmt_var = ctk.StringVar(value="mp3")
        ctk.CTkOptionMenu(opt, values=["mp3", "m4a", "wav", "flac"],
                          variable=self.fmt_var, width=100, height=36).grid(
            row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkLabel(opt, text="음질", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=1, padx=(24, 0), sticky="w")
        self.qual_var = ctk.StringVar(value="320k")
        ctk.CTkOptionMenu(opt, values=["320k", "256k", "192k", "128k"],
                          variable=self.qual_var, width=100, height=36).grid(
            row=1, column=1, padx=(24, 0), pady=(4, 0), sticky="w")

        ctk.CTkLabel(opt, text="저장 위치", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=2, padx=(24, 0), sticky="w")
        folder_row = ctk.CTkFrame(opt, fg_color="transparent")
        folder_row.grid(row=1, column=2, padx=(24, 0), pady=(4, 0))
        self.folder_lbl = ctk.CTkLabel(folder_row, text=self._short(self.download_dir),
                                       font=ctk.CTkFont(size=11), text_color="gray70")
        self.folder_lbl.grid(row=0, column=0)
        ctk.CTkButton(folder_row, text="변경", width=60, height=28,
                      command=self._pick_folder).grid(row=0, column=1, padx=(8, 0))

        # Progress
        self.status_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color="gray70")
        self.status_lbl.grid(row=5, column=0, padx=24, pady=(20, 4), sticky="w")

        self.progress = ctk.CTkProgressBar(self, height=12, corner_radius=6)
        self.progress.grid(row=6, column=0, padx=24, sticky="ew")
        self.progress.set(0)

        self.track_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11), text_color="gray60")
        self.track_lbl.grid(row=7, column=0, padx=24, pady=(4, 0), sticky="w")

        self.dl_btn = ctk.CTkButton(self, text="다운로드", height=48,
                                    font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self._start)
        self.dl_btn.grid(row=8, column=0, padx=24, pady=(20, 0), sticky="ew")

        ctk.CTkLabel(self, text="로그", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=9, column=0, padx=24, pady=(16, 4), sticky="w")
        self.log_box = ctk.CTkTextbox(self, height=110,
                                      font=ctk.CTkFont(family="Consolas", size=11),
                                      state="disabled")
        self.log_box.grid(row=10, column=0, padx=24, pady=(0, 24), sticky="ew")

    # ── helpers ──────────────────────────────────────────────

    def _short(self, p):
        h = os.path.expanduser("~")
        return ("~" + p[len(h):]) if p.startswith(h) else p

    def _paste_url(self):
        try:
            t = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, t.strip())
        except Exception:
            pass

    def _pick_folder(self):
        f = filedialog.askdirectory(initialdir=self.download_dir)
        if f:
            self.download_dir = f
            self.folder_lbl.configure(text=self._short(f))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set(self, status="", track="", pct=None):
        self.status_lbl.configure(text=status)
        self.track_lbl.configure(text=track)
        if pct is not None:
            self.progress.set(pct)

    # ── download ─────────────────────────────────────────────

    def _start(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("알림", "Spotify URL을 입력해 주세요.")
            return
        if "spotify.com" not in url:
            messagebox.showwarning("알림", "올바른 Spotify URL을 입력해 주세요.")
            return
        self.dl_btn.configure(state="disabled", text="다운로드 중...")
        self._set("곡 정보 가져오는 중...", "", 0)
        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _run(self, url):
        try:
            self.after(0, self._log, f"Spotify 정보 조회: {url}")
            title = get_spotify_track_info(url)
            if not title:
                raise Exception("곡 정보를 가져올 수 없습니다.")

            self.after(0, self._log, f"곡 정보: {title}")
            self.after(0, self._set, "YouTube에서 검색 중...", title, 0.1)

            fmt = self.fmt_var.get()
            quality = self.qual_var.get().replace("k", "")

            def progress_hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    done = d.get("downloaded_bytes", 0)
                    pct = 0.1 + (done / total * 0.8) if total else 0.1
                    speed = d.get("speed") or 0
                    spd = f"{speed/1024/1024:.1f} MB/s" if speed else ""
                    self.after(0, self._set, f"다운로드 중... {spd}", title, pct)
                elif d["status"] == "finished":
                    self.after(0, self._set, "변환 중...", title, 0.95)

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(self.download_dir, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": fmt,
                     "preferredquality": quality},
                    {"key": "FFmpegMetadata"},
                ],
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "default_search": "ytsearch1",
            }

            search_query = f"ytsearch1:{title}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([search_query])

            self.after(0, self._on_done, True, title)

        except Exception as e:
            self.after(0, self._on_done, False, str(e))

    def _on_done(self, ok, msg):
        if ok:
            self._set("완료!", "", 1.0)
            self._log(f"완료: {msg}")
            self._log(f"저장 위치: {self.download_dir}")
            messagebox.showinfo("완료", f"다운로드 완료!\n\n{msg}\n\n저장 위치: {self.download_dir}")
        else:
            self._set("오류 발생", "", 0)
            self._log(f"오류: {msg}")
            messagebox.showerror("오류", f"다운로드 실패:\n{msg}")
        self.dl_btn.configure(state="normal", text="다운로드")


if __name__ == "__main__":
    app = App()
    app.mainloop()
