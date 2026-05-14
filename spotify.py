import customtkinter as ctk
import threading
import os
import re
import subprocess
import sys
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Spotify Downloader")
        self.geometry("680x600")
        self.resizable(False, False)
        self.download_dir = os.path.expanduser("~/Downloads")
        self.cookie_file = ""
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self, text="Spotify Downloader",
                             font=ctk.CTkFont(size=22, weight="bold"))
        title.grid(row=0, column=0, pady=(28, 6), padx=24, sticky="w")

        subtitle = ctk.CTkLabel(self, text="Powered by spotdl  •  트랙 / 앨범 / 플레이리스트 모두 지원",
                                font=ctk.CTkFont(size=12),
                                text_color="gray60")
        subtitle.grid(row=1, column=0, pady=(0, 20), padx=24, sticky="w")

        # URL input
        url_label = ctk.CTkLabel(self, text="Spotify URL", font=ctk.CTkFont(size=13, weight="bold"))
        url_label.grid(row=2, column=0, padx=24, pady=(0, 4), sticky="w")

        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.grid(row=3, column=0, padx=24, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://open.spotify.com/track/... 또는 album/... 또는 playlist/...",
            height=40, font=ctk.CTkFont(size=12))
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        paste_btn = ctk.CTkButton(url_frame, text="붙여넣기", width=80, height=40,
                                  command=self._paste_url)
        paste_btn.grid(row=0, column=1)

        # Options row
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.grid(row=4, column=0, padx=24, pady=(16, 0), sticky="ew")

        # Format
        fmt_label = ctk.CTkLabel(opt_frame, text="포맷", font=ctk.CTkFont(size=13, weight="bold"))
        fmt_label.grid(row=0, column=0, sticky="w")
        self.fmt_var = ctk.StringVar(value="mp3")
        fmt_menu = ctk.CTkOptionMenu(opt_frame, values=["mp3", "m4a", "flac", "wav", "ogg"],
                                     variable=self.fmt_var, width=100, height=36)
        fmt_menu.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Quality
        qual_label = ctk.CTkLabel(opt_frame, text="음질", font=ctk.CTkFont(size=13, weight="bold"))
        qual_label.grid(row=0, column=1, padx=(24, 0), sticky="w")
        self.qual_var = ctk.StringVar(value="320")
        qual_menu = ctk.CTkOptionMenu(opt_frame, values=["320", "256", "192", "128"],
                                      variable=self.qual_var, width=100, height=36)
        qual_menu.grid(row=1, column=1, padx=(24, 0), pady=(4, 0), sticky="w")

        # Save folder
        folder_label = ctk.CTkLabel(opt_frame, text="저장 위치", font=ctk.CTkFont(size=13, weight="bold"))
        folder_label.grid(row=0, column=2, padx=(24, 0), sticky="w")
        folder_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        folder_row.grid(row=1, column=2, padx=(24, 0), pady=(4, 0))

        self.folder_label = ctk.CTkLabel(folder_row,
                                         text=self._short_path(self.download_dir),
                                         font=ctk.CTkFont(size=11), text_color="gray70")
        self.folder_label.grid(row=0, column=0)
        ctk.CTkButton(folder_row, text="변경", width=60, height=28,
                      command=self._pick_folder).grid(row=0, column=1, padx=(8, 0))

        # Cookie file
        cookie_frame = ctk.CTkFrame(self, fg_color="transparent")
        cookie_frame.grid(row=5, column=0, padx=24, pady=(14, 0), sticky="ew")
        cookie_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(cookie_frame, text="쿠키 파일 (YouTube Music 차단 시 필요)",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w")

        self.cookie_label = ctk.CTkLabel(cookie_frame, text="선택 안 됨",
                                         font=ctk.CTkFont(size=11), text_color="gray60")
        self.cookie_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(cookie_frame, text="파일 선택", width=90, height=28,
                      command=self._pick_cookie).grid(row=1, column=1, padx=(10, 0), pady=(4, 0), sticky="w")

        ctk.CTkButton(cookie_frame, text="초기화", width=60, height=28, fg_color="gray30",
                      command=self._clear_cookie).grid(row=1, column=2, padx=(6, 0), pady=(4, 0), sticky="w")

        # Progress
        self.progress_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12),
                                           text_color="gray70")
        self.progress_label.grid(row=6, column=0, padx=24, pady=(20, 4), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self, height=12, corner_radius=6)
        self.progress_bar.grid(row=7, column=0, padx=24, sticky="ew")
        self.progress_bar.set(0)

        self.track_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11),
                                        text_color="gray60")
        self.track_label.grid(row=8, column=0, padx=24, pady=(4, 0), sticky="w")

        # Download button
        self.dl_btn = ctk.CTkButton(self, text="다운로드", height=48,
                                    font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self._start_download)
        self.dl_btn.grid(row=9, column=0, padx=24, pady=(20, 0), sticky="ew")

        # Log
        ctk.CTkLabel(self, text="로그", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=10, column=0, padx=24, pady=(16, 4), sticky="w")

        self.log_box = ctk.CTkTextbox(self, height=110,
                                      font=ctk.CTkFont(family="Consolas", size=11),
                                      state="disabled")
        self.log_box.grid(row=11, column=0, padx=24, pady=(0, 24), sticky="ew")

    # ── helpers ──────────────────────────────────────────────

    def _short_path(self, path):
        home = os.path.expanduser("~")
        return ("~" + path[len(home):]) if path.startswith(home) else path

    def _paste_url(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def _pick_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_dir)
        if folder:
            self.download_dir = folder
            self.folder_label.configure(text=self._short_path(folder))

    def _pick_cookie(self):
        path = filedialog.askopenfilename(
            title="쿠키 파일 선택",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.cookie_file = path
            self.cookie_label.configure(text=os.path.basename(path), text_color="green")

    def _clear_cookie(self):
        self.cookie_file = ""
        self.cookie_label.configure(text="선택 안 됨", text_color="gray60")

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, label="", track="", progress=None):
        self.progress_label.configure(text=label)
        self.track_label.configure(text=track)
        if progress is not None:
            self.progress_bar.set(progress)

    # ── download ─────────────────────────────────────────────

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("알림", "Spotify URL을 입력해 주세요.")
            return
        if "spotify.com" not in url:
            messagebox.showwarning("알림", "올바른 Spotify URL을 입력해 주세요.\n예: https://open.spotify.com/track/...")
            return

        self.dl_btn.configure(state="disabled", text="다운로드 중...")
        self._set_status("준비 중...", "", 0)
        self._log(f"시작: {url}")
        threading.Thread(target=self._download, args=(url,), daemon=True).start()

    def _download(self, url):
        fmt = self.fmt_var.get()
        bitrate = self.qual_var.get()

        cmd = [
            sys.executable, "-m", "spotdl",
            url,
            "--format", fmt,
            "--bitrate", f"{bitrate}k",
            "--output", os.path.join(self.download_dir, "{artists} - {title}.{output-ext}"),
            "--audio", "piped", "youtube",
        ]
        if self.cookie_file and os.path.exists(self.cookie_file):
            cmd += ["--cookie-file", self.cookie_file]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            downloaded = 0
            total = 0

            for line in process.stdout:
                line = line.rstrip()
                if not line:
                    continue

                self.after(0, self._log, line)

                # Parse spotdl output
                if "Found" in line and "song" in line:
                    m = re.search(r"(\d+)\s+song", line)
                    if m:
                        total = int(m.group(1))
                        self.after(0, self._set_status,
                                   f"총 {total}곡 발견", "", 0)

                elif "Downloading" in line or "Downloaded" in line:
                    m = re.search(r'"(.+?)"', line)
                    track_name = m.group(1) if m else ""
                    if "Downloaded" in line:
                        downloaded += 1
                    pct = (downloaded / total) if total > 0 else 0
                    status = f"다운로드 중... {downloaded}/{total if total else '?'}곡"
                    self.after(0, self._set_status, status, track_name, pct)

                elif "Skipping" in line:
                    downloaded += 1

            process.wait()

            if process.returncode == 0:
                self.after(0, self._on_done, True, downloaded)
            else:
                self.after(0, self._on_done, False, "오류가 발생했습니다. 로그를 확인해 주세요.")

        except Exception as e:
            self.after(0, self._on_done, False, str(e))

    def _on_done(self, success, result):
        if success:
            self._set_status("완료!", "", 1.0)
            self._log(f"완료! {result}곡 저장됨 → {self.download_dir}")
            messagebox.showinfo("완료", f"다운로드 완료!\n\n{result}곡이 저장되었습니다.\n\n저장 위치: {self.download_dir}")
        else:
            self._set_status("오류 발생", "", 0)
            self._log(f"오류: {result}")
            messagebox.showerror("오류", f"다운로드 실패:\n{result}")
        self.dl_btn.configure(state="normal", text="다운로드")


if __name__ == "__main__":
    app = App()
    app.mainloop()
