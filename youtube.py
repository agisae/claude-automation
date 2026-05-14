import customtkinter as ctk
import threading
import os
import re
from tkinter import filedialog, messagebox
import yt_dlp

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube MP3 Downloader")
        self.geometry("680x520")
        self.resizable(False, False)
        self.download_dir = os.path.expanduser("~/Downloads")
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self, text="YouTube MP3 Downloader",
                             font=ctk.CTkFont(size=22, weight="bold"))
        title.grid(row=0, column=0, pady=(28, 6), padx=24, sticky="w")

        subtitle = ctk.CTkLabel(self, text="Powered by yt-dlp",
                                font=ctk.CTkFont(size=12),
                                text_color="gray60")
        subtitle.grid(row=1, column=0, pady=(0, 20), padx=24, sticky="w")

        # URL input
        url_label = ctk.CTkLabel(self, text="YouTube URL", font=ctk.CTkFont(size=13, weight="bold"))
        url_label.grid(row=2, column=0, padx=24, pady=(0, 4), sticky="w")

        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.grid(row=3, column=0, padx=24, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="https://www.youtube.com/watch?v=...",
                                      height=40, font=ctk.CTkFont(size=13))
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
        fmt_menu = ctk.CTkOptionMenu(opt_frame, values=["mp3", "m4a", "wav", "mp4", "webm"],
                                     variable=self.fmt_var, width=100, height=36,
                                     command=self._on_format_change)
        fmt_menu.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Quality
        qual_label = ctk.CTkLabel(opt_frame, text="음질", font=ctk.CTkFont(size=13, weight="bold"))
        qual_label.grid(row=0, column=1, padx=(24, 0), sticky="w")
        self.qual_var = ctk.StringVar(value="320k")
        self.qual_menu = ctk.CTkOptionMenu(opt_frame, values=["320k", "256k", "192k", "128k"],
                                           variable=self.qual_var, width=100, height=36)
        self.qual_menu.grid(row=1, column=1, padx=(24, 0), pady=(4, 0), sticky="w")

        # Save folder
        folder_label = ctk.CTkLabel(opt_frame, text="저장 위치", font=ctk.CTkFont(size=13, weight="bold"))
        folder_label.grid(row=0, column=2, padx=(24, 0), sticky="w")
        folder_frame = ctk.CTkFrame(opt_frame, fg_color="transparent")
        folder_frame.grid(row=1, column=2, padx=(24, 0), pady=(4, 0), sticky="ew")

        self.folder_label = ctk.CTkLabel(folder_frame,
                                         text=self._short_path(self.download_dir),
                                         font=ctk.CTkFont(size=11),
                                         text_color="gray70",
                                         wraplength=180)
        self.folder_label.grid(row=0, column=0, sticky="w")
        folder_btn = ctk.CTkButton(folder_frame, text="변경", width=60, height=28,
                                   command=self._pick_folder)
        folder_btn.grid(row=0, column=1, padx=(8, 0))

        # Progress
        self.progress_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12),
                                           text_color="gray70")
        self.progress_label.grid(row=5, column=0, padx=24, pady=(20, 4), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self, height=12, corner_radius=6)
        self.progress_bar.grid(row=6, column=0, padx=24, sticky="ew")
        self.progress_bar.set(0)

        # Speed / ETA
        self.speed_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11),
                                        text_color="gray60")
        self.speed_label.grid(row=7, column=0, padx=24, pady=(4, 0), sticky="w")

        # Download button
        self.dl_btn = ctk.CTkButton(self, text="다운로드", height=48,
                                    font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self._start_download)
        self.dl_btn.grid(row=8, column=0, padx=24, pady=(20, 0), sticky="ew")

        # Log box
        log_label = ctk.CTkLabel(self, text="로그", font=ctk.CTkFont(size=12, weight="bold"))
        log_label.grid(row=9, column=0, padx=24, pady=(16, 4), sticky="w")

        self.log_box = ctk.CTkTextbox(self, height=100, font=ctk.CTkFont(family="Consolas", size=11),
                                      state="disabled")
        self.log_box.grid(row=10, column=0, padx=24, pady=(0, 24), sticky="ew")

    # ── helpers ──────────────────────────────────────────────

    def _short_path(self, path):
        home = os.path.expanduser("~")
        if path.startswith(home):
            return "~" + path[len(home):]
        return path

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

    def _on_format_change(self, fmt):
        is_audio = fmt in ("mp3", "m4a", "wav")
        self.qual_menu.configure(state="normal" if is_audio else "disabled")

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, value, label="", speed=""):
        self.progress_bar.set(value)
        self.progress_label.configure(text=label)
        self.speed_label.configure(text=speed)

    # ── download ─────────────────────────────────────────────

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("알림", "URL을 입력해 주세요.")
            return
        if not re.match(r"https?://", url):
            messagebox.showwarning("알림", "올바른 URL을 입력해 주세요.")
            return

        self.dl_btn.configure(state="disabled", text="다운로드 중...")
        self._set_progress(0, "준비 중...", "")
        self._log(f"시작: {url}")
        threading.Thread(target=self._download, args=(url,), daemon=True).start()

    def _download(self, url):
        fmt = self.fmt_var.get()
        is_audio = fmt in ("mp3", "m4a", "wav")
        quality = self.qual_var.get().replace("k", "")

        def progress_hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                pct = (downloaded / total) if total else 0

                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed > 0 else ""
                eta_str = f"  남은시간 {eta}초" if eta > 0 else ""
                pct_str = f"{pct*100:.0f}%  {speed_str}{eta_str}"
                self.after(0, self._set_progress, pct, f"다운로드 중... {pct_str}", "")

            elif d["status"] == "finished":
                self.after(0, self._set_progress, 1.0, "변환 중...", "")
                self.after(0, self._log, "파일 변환 중...")

        postprocessors = []
        if is_audio:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": quality,
            })
            postprocessors.append({"key": "FFmpegMetadata"})
            postprocessors.append({"key": "EmbedThumbnail"})

        ydl_opts = {
            "format": "bestaudio/best" if is_audio else "bestvideo+bestaudio/best",
            "outtmpl": os.path.join(self.download_dir, "%(title)s.%(ext)s"),
            "postprocessors": postprocessors,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": is_audio,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Unknown")
            self.after(0, self._on_done, True, title)
        except Exception as e:
            self.after(0, self._on_done, False, str(e))

    def _on_done(self, success, msg):
        if success:
            self._set_progress(1.0, "완료!", "")
            self._log(f"완료: {msg}")
            self._log(f"저장 위치: {self.download_dir}")
            messagebox.showinfo("완료", f"다운로드 완료!\n\n{msg}\n\n저장 위치: {self.download_dir}")
        else:
            self._set_progress(0, "오류 발생", "")
            self._log(f"오류: {msg}")
            messagebox.showerror("오류", f"다운로드 실패:\n{msg}")
        self.dl_btn.configure(state="normal", text="다운로드")


if __name__ == "__main__":
    app = App()
    app.mainloop()
