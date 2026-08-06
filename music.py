import customtkinter as ctk
import threading
import os
import re
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DEFAULT_DIR = r"D:\Soulseek Downloads\complete"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def get_spotify_client():
    cfg = load_config()
    cid = cfg.get("spotify_client_id", "")
    secret = cfg.get("spotify_client_secret", "")
    if not cid or not secret:
        return None
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=cid, client_secret=secret))

def detect_source(url):
    if "spotify.com" in url:
        return "spotify"
    if re.search(r"(youtube\.com|youtu\.be)", url):
        return "youtube"
    return None

def spotify_url_type(url):
    if "/playlist/" in url:
        return "playlist"
    if "/album/" in url:
        return "album"
    return "track"

def get_spotify_tracks(url):
    url_type = spotify_url_type(url)
    sp = get_spotify_client()

    if url_type == "track" or sp is None:
        oembed = f"https://open.spotify.com/oembed?url={url}"
        req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        title = data.get("title", "")
        artist = data.get("author_name", "")
        query = f"{artist} - {title}" if artist else title
        return [query], title

    tracks = []
    if url_type == "playlist":
        playlist_id = re.search(r"/playlist/([A-Za-z0-9]+)", url).group(1)
        result = sp.playlist(playlist_id)
        name = result["name"]
        items = result["tracks"]["items"]
        while result["tracks"].get("next"):
            result["tracks"] = sp.next(result["tracks"])
            items += result["tracks"]["items"]
        for item in items:
            t = item.get("track")
            if t:
                artists = ", ".join(a["name"] for a in t["artists"])
                tracks.append(f"{artists} - {t['name']}")

    elif url_type == "album":
        album_id = re.search(r"/album/([A-Za-z0-9]+)", url).group(1)
        result = sp.album(album_id)
        name = result["name"]
        artist = result["artists"][0]["name"]
        items = result["tracks"]["items"]
        for t in items:
            tracks.append(f"{artist} - {t['name']}")

    return tracks, name


class DownloadRow(ctk.CTkFrame):
    def __init__(self, master, url, index):
        super().__init__(master, fg_color=("gray85", "gray20"), corner_radius=8)
        self.url = url
        self.grid_columnconfigure(0, weight=1)

        source = detect_source(url)
        badge = "  YT  " if source == "youtube" else "  SP  " if source == "spotify" else "  ??  "
        badge_color = "#FF4444" if source == "youtube" else "#1DB954" if source == "spotify" else "gray"

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text=badge, font=ctk.CTkFont(size=10, weight="bold"),
                     fg_color=badge_color, corner_radius=4, width=32).grid(row=0, column=0)

        short = url[:62] + "..." if len(url) > 62 else url
        self.name_lbl = ctk.CTkLabel(top, text=short, font=ctk.CTkFont(size=11),
                                     text_color="gray70", anchor="w")
        self.name_lbl.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self.prog = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self.prog.grid(row=1, column=0, padx=10, pady=(2, 2), sticky="ew")
        self.prog.set(0)

        self.status_lbl = ctk.CTkLabel(self, text="\ub300\uae30 \uc911", font=ctk.CTkFont(size=10),
                                       text_color="gray60", anchor="w")
        self.status_lbl.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    def set_title(self, title):
        short = title[:70] + "..." if len(title) > 70 else title
        self.name_lbl.configure(text=short)

    def update(self, status, pct=None):
        self.status_lbl.configure(text=status)
        if pct is not None:
            self.prog.set(pct)

    def done(self, ok):
        if ok:
            self.update("\uc644\ub8cc", 1.0)
            self.status_lbl.configure(text_color="#4CAF50")
            self.prog.configure(progress_color="#4CAF50")
        else:
            self.update("\uc2e4\ud328", 0)
            self.status_lbl.configure(text_color="#f44336")
            self.prog.configure(progress_color="#f44336")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Music Downloader")
        self.geometry("700x620")
        self.resizable(False, False)
        self.dir_ref = [DEFAULT_DIR]
        self._rows = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Music Downloader",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(22, 2), sticky="w")
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=1, column=0, padx=24, pady=(0, 14), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="YouTube \u00b7 Spotify URL\uc744 \uc790\ub3d9\uc73c\ub85c \uac10\uc9c0\ud569\ub2c8\ub2e4",
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="\u2699 Spotify \uc124\uc815", width=120, height=26,
                      fg_color="gray30", hover_color="gray40",
                      command=self._spotify_settings).grid(row=0, column=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, padx=24, pady=(0, 12), sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="\uc800\uc7a5 \uc704\uce58:", font=ctk.CTkFont(size=12),
                     text_color="gray60").grid(row=0, column=0)
        self.folder_lbl = ctk.CTkLabel(bar, text=self.dir_ref[0],
                                       font=ctk.CTkFont(size=11), text_color="gray70", anchor="w")
        self.folder_lbl.grid(row=0, column=1, padx=(8, 8), sticky="ew")
        ctk.CTkButton(bar, text="\ubcc0\uacbd", width=60, height=26,
                      command=self._pick_folder).grid(row=0, column=2)

        ctk.CTkLabel(self, text="URL \uc785\ub825  (YouTube / Spotify \uc11c\ub85c \uc11e\uc5b4\ub3c4 \ub429\ub2c8\ub2e4)",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=3, column=0, padx=24, pady=(0, 4), sticky="w")

        self.url_box = ctk.CTkTextbox(self, height=90, font=ctk.CTkFont(size=12))
        self.url_box.grid(row=4, column=0, padx=24, sticky="ew")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=5, column=0, padx=24, pady=(6, 0), sticky="ew")
        ctk.CTkButton(btn_row, text="\ubd99\uc5ec\ub123\uae30", width=90, height=30,
                      command=self._paste).grid(row=0, column=0)
        ctk.CTkButton(btn_row, text="\ucd08\uae30\ud654", width=70, height=30, fg_color="gray30",
                      command=lambda: self.url_box.delete("1.0", "end")).grid(
            row=0, column=1, padx=(8, 0))

        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.grid(row=6, column=0, padx=24, pady=(12, 0), sticky="ew")

        ctk.CTkLabel(opt, text="\ud3ec\ub9f7", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
        self.fmt_var = ctk.StringVar(value="mp3")
        ctk.CTkOptionMenu(opt, values=["mp3", "m4a", "wav", "flac"],
                          variable=self.fmt_var, width=90, height=32).grid(
            row=1, column=0, pady=(4, 0), sticky="w")

        ctk.CTkLabel(opt, text="\uc74c\uc9c8", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=1, padx=(20, 0), sticky="w")
        self.qual_var = ctk.StringVar(value="320k")
        ctk.CTkOptionMenu(opt, values=["320k", "256k", "192k", "128k"],
                          variable=self.qual_var, width=90, height=32).grid(
            row=1, column=1, padx=(20, 0), pady=(4, 0), sticky="w")

        ctk.CTkLabel(opt, text="\ub3d9\uc2dc \ub2e4\uc6b4\ub85c\ub4dc", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, padx=(20, 0), sticky="w")
        self.worker_var = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(opt, values=["1", "2", "3", "4", "5"],
                          variable=self.worker_var, width=70, height=32).grid(
            row=1, column=2, padx=(20, 0), pady=(4, 0), sticky="w")

        self.dl_btn = ctk.CTkButton(self, text="\ub2e4\uc6b4\ub85c\ub4dc", height=44,
                                    font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self._start)
        self.dl_btn.grid(row=7, column=0, padx=24, pady=(14, 0), sticky="ew")

        ctk.CTkLabel(self, text="\uc9c4\ud589 \uc0c1\ud669", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=8, column=0, padx=24, pady=(14, 4), sticky="w")
        self.queue_frame = ctk.CTkScrollableFrame(self, height=180)
        self.queue_frame.grid(row=9, column=0, padx=24, pady=(0, 20), sticky="ew")
        self.queue_frame.grid_columnconfigure(0, weight=1)

    def _paste(self):
        try:
            self.url_box.insert("end", self.clipboard_get().strip() + "\n")
        except Exception:
            pass

    def _pick_folder(self):
        f = filedialog.askdirectory(initialdir=self.dir_ref[0])
        if f:
            self.dir_ref[0] = f
            self.folder_lbl.configure(text=f)

    def _spotify_settings(self):
        cfg = load_config()
        win = ctk.CTkToplevel(self)
        win.title("Spotify API \uc124\uc815")
        win.geometry("460x220")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(win, text="Spotify Client ID",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(padx=24, pady=(20,4), anchor="w")
        cid_entry = ctk.CTkEntry(win, width=410, height=36)
        cid_entry.insert(0, cfg.get("spotify_client_id", ""))
        cid_entry.pack(padx=24)

        ctk.CTkLabel(win, text="Spotify Client Secret",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(padx=24, pady=(12,4), anchor="w")
        sec_entry = ctk.CTkEntry(win, width=410, height=36, show="*")
        sec_entry.insert(0, cfg.get("spotify_client_secret", ""))
        sec_entry.pack(padx=24)

        def save():
            cfg["spotify_client_id"] = cid_entry.get().strip()
            cfg["spotify_client_secret"] = sec_entry.get().strip()
            save_config(cfg)
            messagebox.showinfo("\uc800\uc7a5\ub428", "Spotify API \ud0a4\uac00 \uc800\uc7a5\ub418\uc5c8\uc2b5\ub2c8\ub2e4!")
            win.destroy()

        ctk.CTkButton(win, text="\uc800\uc7a5", height=36, command=save).pack(padx=24, pady=16, fill="x")

    def _get_urls(self):
        text = self.url_box.get("1.0", "end")
        urls = re.findall(r"https?://[^\s\"'<>]+", text)
        urls = [u for u in urls if detect_source(u)]
        if not urls:
            messagebox.showwarning("\uc54c\ub9bc", "YouTube \ub610\ub294 Spotify URL\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.")
        return urls

    def _start(self):
        urls = self._get_urls()
        if not urls:
            return

        for w in self.queue_frame.winfo_children():
            w.destroy()
        self._rows = []
        for i, url in enumerate(urls):
            row = DownloadRow(self.queue_frame, url, i)
            row.grid(row=i, column=0, sticky="ew", pady=(0, 4))
            self._rows.append(row)

        self.dl_btn.configure(state="disabled", text=f"{len(urls)}\uac1c \ub2e4\uc6b4\ub85c\ub4dc \uc911...")
        workers = int(self.worker_var.get())
        threading.Thread(target=self._run_all, args=(urls, workers), daemon=True).start()

    def _run_all(self, urls, workers):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._download_one, i, url) for i, url in enumerate(urls)]
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass
        self.after(0, lambda: self.dl_btn.configure(state="normal", text="\ub2e4\uc6b4\ub85c\ub4dc"))

    def _download_one(self, idx, url):
        row = self._rows[idx]
        source = detect_source(url)
        fmt = self.fmt_var.get()
        quality = self.qual_var.get().replace("k", "")

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes", 0)
                pct = (done / total) if total else 0
                spd = d.get("speed") or 0
                s = f"{spd/1024/1024:.1f} MB/s" if spd else "..."
                self.after(0, row.update, f"\ub2e4\uc6b4\ub85c\ub4dc \uc911 {pct*100:.0f}% \u2014 {s}", pct)
            elif d["status"] == "finished":
                self.after(0, row.update, "\ubcc0\ud658 \uc911...", 0.95)

        save_dir = self.dir_ref[0]
        os.makedirs(save_dir, exist_ok=True)

        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(save_dir, "%(title)s.%(ext)s"),
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": fmt, "preferredquality": quality},
                {"key": "FFmpegMetadata"},
            ],
            "progress_hooks": [hook],
            "ignoreerrors": True,
            "socket_timeout": 30,
            "retries": 3,
            "quiet": True, "no_warnings": True,
        }

        try:
            if source == "spotify":
                self.after(0, row.update, "Spotify \uc815\ubcf4 \uac00\uc838\uc624\ub294 \uc911...", 0.05)
                tracks, name = get_spotify_tracks(url)
                if not tracks:
                    raise Exception("\ud2b8\ub799 \uc815\ubcf4\ub97c \uac00\uc838\uc62c \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.")
                count = len(tracks)
                self.after(0, row.set_title, f"{name}  ({count}\uace1)" if count > 1 else name)
                for i, query in enumerate(tracks):
                    pct = 0.1 + (i / count * 0.85)
                    self.after(0, row.update, f"[{i+1}/{count}] {query[:50]}", pct)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([f"ytsearch1:{query}"])

            else:
                self.after(0, row.update, "\uc815\ubcf4 \uac00\uc838\uc624\ub294 \uc911...", 0.05)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                if info:
                    if info.get("_type") == "playlist":
                        count = len([e for e in (info.get("entries") or []) if e])
                        self.after(0, row.set_title, f"{info.get('title','')}  ({count}\uace1)")
                    else:
                        self.after(0, row.set_title, info.get("title", url))

            self.after(0, row.done, True)

        except Exception as e:
            err = str(e)
            self.after(0, row.update, err[:80] if err else "\uc54c \uc218 \uc5c6\ub294 \uc624\ub958")
            self.after(0, row.done, False)


if __name__ == "__main__":
    app = App()
    app.mainloop()
