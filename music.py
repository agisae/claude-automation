import customtkinter as ctk
import threading
import os
import re
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox
import yt_dlp
import base64
import urllib.error
import urllib.parse
import http.server
import webbrowser

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

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPE = "playlist-read-private playlist-read-collaborative"
TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".spotify_cache")

def _exchange_token(cid, secret, params):
    creds = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(params).encode(),
        headers={"Authorization": f"Basic {creds}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        raise Exception(f"Spotify 인증 실패 ({e.code}): {body}")

def _spotify_token():
    """Return a valid access token, refreshing if needed."""
    cfg = load_config()
    cid = cfg.get("spotify_client_id", "").strip()
    secret = cfg.get("spotify_client_secret", "").strip()
    if not cid or not secret:
        return None

    # Try cached user token first
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE) as f:
            cached = json.load(f)
        import time
        if cached.get("expires_at", 0) > time.time() + 60:
            return cached["access_token"]
        if cached.get("refresh_token"):
            try:
                data = _exchange_token(cid, secret, {
                    "grant_type": "refresh_token",
                    "refresh_token": cached["refresh_token"]})
                import time as _t
                cached["access_token"] = data["access_token"]
                cached["expires_at"] = _t.time() + data.get("expires_in", 3600)
                if "refresh_token" in data:
                    cached["refresh_token"] = data["refresh_token"]
                with open(TOKEN_CACHE, "w") as f:
                    json.dump(cached, f)
                return cached["access_token"]
            except Exception as e:
                # Delete stale cache so next run doesn't get stuck trying to refresh
                try:
                    os.remove(TOKEN_CACHE)
                except Exception:
                    pass
                raise Exception(
                    f"Spotify 토큰이 만료되었습니다. 다시 로그인해 주세요.\n"
                    f"⚙ Spotify 설정 → 🔑 Spotify 로그인\n오류: {e}")

    # Fall back to Client Credentials (public playlists/albums only)
    try:
        data = _exchange_token(cid, secret, {"grant_type": "client_credentials"})
        return data["access_token"]
    except Exception as e:
        raise Exception(str(e))

def build_auth_url(cid):
    """OAuth 인증 URL 생성 (항상 로그인 화면 표시)."""
    params = urllib.parse.urlencode({
        "client_id": cid, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "scope": SPOTIFY_SCOPE,
        "show_dialog": "true"})
    return f"https://accounts.spotify.com/authorize?{params}"

def wait_for_oauth_code(on_ready=None):
    """로컬 서버를 열어 Spotify OAuth 콜백 코드를 기다린다. code를 반환."""
    code_box = [None]

    class _Server(http.server.HTTPServer):
        allow_reuse_address = True

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            p = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in p:
                code_box[0] = p["code"][0]
                body = "<html><meta charset='utf-8'><body><h2>로그인 완료! 이 탭을 닫으세요.</h2></body></html>"
                body_bytes = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_response(204)
                self.end_headers()
        def log_message(self, *args): pass

    server = _Server(("127.0.0.1", 8888), Handler)
    if on_ready:
        on_ready()
    server.serve_forever()
    return code_box[0]

def finish_oauth(cid, secret, code):
    """코드로 토큰 교환 후 저장. Spotify 계정명 반환."""
    import time
    data = _exchange_token(cid, secret, {
        "grant_type": "authorization_code",
        "code": code, "redirect_uri": REDIRECT_URI})
    access_token = data["access_token"]
    with open(TOKEN_CACHE, "w") as f:
        json.dump({"access_token": access_token,
                   "refresh_token": data.get("refresh_token", ""),
                   "expires_at": time.time() + data.get("expires_in", 3600)}, f)
    # 토큰이 실제로 작동하는지 확인
    me = _spotify_get(access_token, "me")
    return me.get("display_name") or me.get("id") or "알 수 없음"

def _get_anon_token():
    """Spotify 웹플레이어 익명 토큰 — 공개 콘텐츠는 API 키 없이 접근 가능."""
    req = urllib.request.Request(
        "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    token = data.get("accessToken")
    if not token:
        raise Exception("Spotify 익명 토큰을 가져올 수 없습니다.")
    return token

def _spotify_get(token, path):
    """Call Spotify Web API and return parsed JSON."""
    req = urllib.request.Request(
        f"https://api.spotify.com/v1/{path}",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        raise Exception(f"Spotify {e.code}: {body}")

def clean_url(url):
    """Normalize YouTube URL and strip tracking params that break yt-dlp."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    url = re.sub(r"https?://(m\.)?youtube\.com", "https://www.youtube.com", url)
    parsed = urlparse(url)
    if re.search(r"(youtube\.com|youtu\.be)", parsed.netloc):
        params = parse_qs(parsed.query, keep_blank_values=True)
        keep = {k: v for k, v in params.items() if k in ("v", "list", "index", "t", "start")}
        return urlunparse(parsed._replace(query=urlencode(keep, doseq=True)))
    return url

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

def _oembed_track(url):
    oembed = f"https://open.spotify.com/oembed?url={url}"
    req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    title = data.get("title", "")
    artist = data.get("author_name", "")
    query = f"{artist} - {title}" if artist else title
    return [query], title or "Spotify Track"

def _fetch_playlist_tracks(token, playlist_id):
    name = _spotify_get(token, f"playlists/{playlist_id}")["name"]
    tracks = []
    offset = 0
    while True:
        page = _spotify_get(token,
            f"playlists/{playlist_id}/tracks?limit=100&offset={offset}")
        for item in page.get("items", []):
            t = item.get("track")
            if t and t.get("name"):
                artists = ", ".join(a["name"] for a in t.get("artists", []))
                tracks.append(f"{artists} - {t['name']}" if artists else t["name"])
        if not page.get("next"):
            break
        offset += 100
    return tracks, name

def _fetch_via_embed(url_type, item_id):
    """Spotify 임베드 페이지에서 트랙 목록을 스크래핑 (API 키 불필요).
    페이지에 포함된 access token으로 100곡 초과 플레이리스트도 전부 가져온다."""
    embed_url = f"https://open.spotify.com/embed/{url_type}/{item_id}"
    req = urllib.request.Request(embed_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        raise Exception("임베드 페이지에서 __NEXT_DATA__ 없음")

    data = json.loads(m.group(1))
    page_props = data["props"]["pageProps"]

    # Access token embedded in the page — not from our developer app quota
    embed_token = page_props.get("accessToken")

    try:
        entity = page_props["state"]["data"]["entity"]
    except (KeyError, TypeError):
        raise Exception("임베드 데이터 구조가 예상과 다릅니다")

    name = entity.get("name", "Unknown")
    tracks = []

    # Playlists use trackList[], albums may use tracks.items[]
    track_list = entity.get("trackList") or []
    for t in track_list:
        if not t:
            continue
        title = (t.get("title") or "").strip()
        artist = (t.get("subtitle") or "").strip()
        if title:
            tracks.append(f"{artist} - {title}" if artist else title)

    if not tracks:
        # Album fallback path
        items = (entity.get("tracks") or {}).get("items") or []
        for t in items:
            if not t:
                continue
            title = (t.get("name") or "").strip()
            artists = ", ".join(a["name"] for a in t.get("artists", []) if a.get("name"))
            if title:
                tracks.append(f"{artists} - {title}" if artists else title)

    if not tracks:
        raise Exception("임베드에서 트랙을 찾을 수 없습니다")

    # Paginate remaining tracks using the page-embedded token (bypasses dev app quota)
    # Don't rely on a total-count field — just keep going while API returns a next link
    if embed_token and url_type == "playlist":
        offset = len(tracks)
        while True:
            try:
                page = _spotify_get(embed_token,
                    f"playlists/{item_id}/tracks?limit=100&offset={offset}")
            except Exception:
                break
            added = 0
            for item in page.get("items", []):
                t = item.get("track")
                if t and t.get("name"):
                    artists = ", ".join(a["name"] for a in t.get("artists", []))
                    tracks.append(f"{artists} - {t['name']}" if artists else t["name"])
                    added += 1
            if not page.get("next") or added == 0:
                break
            offset += 100

    return tracks, name

def _fetch_via_ytdlp(url):
    """yt-dlp 내장 Spotify 추출기로 트랙 목록 가져오기."""
    tracks = []
    name = "Spotify"

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise Exception("yt-dlp: 정보 없음")

    name = info.get("title") or info.get("playlist_title") or name
    entries = info.get("entries") or []
    if not entries:
        title = (info.get("title") or "").strip()
        artist = (info.get("uploader") or info.get("artist") or "").strip()
        if title:
            tracks.append(f"{artist} - {title}" if artist else title)
    else:
        for e in entries:
            if not e:
                continue
            title = (e.get("title") or "").strip()
            artist = (e.get("uploader") or e.get("artist") or "").strip()
            if title:
                tracks.append(f"{artist} - {title}" if artist else title)

    if not tracks:
        raise Exception("yt-dlp: 트랙 없음")
    return tracks, name

def get_spotify_tracks(url):
    url_type = spotify_url_type(url)

    if url_type == "track":
        return _oembed_track(url)

    m = re.search(r"/(playlist|album)/([A-Za-z0-9]+)", url)
    item_id = m.group(2) if m else None

    errors = []

    # Method 1: 임베드 페이지 스크래핑 (API 키 / 개발자 앱 제한 없음)
    if item_id:
        try:
            result = _fetch_via_embed(url_type, item_id)
            print(f"[Spotify] embed 방식 성공: {len(result[0])}곡")
            return result
        except Exception as e:
            print(f"[Spotify] embed 실패: {e}")
            errors.append(f"embed: {e}")

    # Method 2: yt-dlp 내장 Spotify 추출기
    try:
        result = _fetch_via_ytdlp(url)
        print(f"[Spotify] yt-dlp 방식 성공: {len(result[0])}곡")
        return result
    except Exception as e:
        print(f"[Spotify] yt-dlp 실패: {e}")
        errors.append(f"yt-dlp: {e}")

    # Method 3: OAuth API (개발자 앱 Extended Quota Mode 필요)
    tokens_to_try = []
    try:
        t = _spotify_token()
        if t:
            tokens_to_try.append(("oauth", t))
    except Exception:
        pass
    try:
        tokens_to_try.append(("anon", _get_anon_token()))
    except Exception:
        pass

    for token_type, token in tokens_to_try:
        print(f"[Spotify] API({token_type}) 시도 중...")
        try:
            if url_type == "playlist":
                playlist_id = re.search(r"/playlist/([A-Za-z0-9]+)", url).group(1)
                result = _fetch_playlist_tracks(token, playlist_id)
                print(f"[Spotify] API 성공: {len(result[0])}곡")
                return result
            elif url_type == "album":
                album_id = re.search(r"/album/([A-Za-z0-9]+)", url).group(1)
                data = _spotify_get(token, f"albums/{album_id}")
                name = data["name"]
                artist = data["artists"][0]["name"]
                tracks = [f"{artist} - {t['name']}" for t in data["tracks"]["items"]]
                return tracks, name
        except Exception as e:
            print(f"[Spotify] API({token_type}) 실패: {e}")
            errors.append(f"API({token_type}): {e}")

    raise Exception("Spotify 접근 실패 (모든 방법 시도함):\n" + "\n".join(errors[-3:]))


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

        self.status_lbl = ctk.CTkLabel(self, text="대기 중", font=ctk.CTkFont(size=10),
                                       text_color="gray60", anchor="w")
        self.status_lbl.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    def set_title(self, title):
        short = title[:70] + "..." if len(title) > 70 else title
        self.name_lbl.configure(text=short)

    def set_status(self, status, pct=None):
        self.status_lbl.configure(text=status)
        if pct is not None:
            self.prog.set(pct)

    def done(self, ok, msg=""):
        if ok:
            self.set_status("완료", 1.0)
            self.status_lbl.configure(text_color="#4CAF50")
            self.prog.configure(progress_color="#4CAF50")
        else:
            self.set_status(msg or "실패", 0)
            self.status_lbl.configure(text_color="#f44336")
            self.prog.configure(progress_color="#f44336")


def _run_ydl(ydl_opts, query, timeout=180):
    """Run yt-dlp in a sub-thread so we can enforce a hard timeout on Windows."""
    exc = [None]

    def _do():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([query])
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"다운로드 시간 초과 ({timeout}초)")
    if exc[0]:
        raise exc[0]


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
        ctk.CTkLabel(hdr, text="YouTube · Spotify URL을 자동으로 감지합니다",
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="⚙ Spotify 설정", width=120, height=26,
                      fg_color="gray30", hover_color="gray40",
                      command=self._spotify_settings).grid(row=0, column=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, padx=24, pady=(0, 12), sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="저장 위치:", font=ctk.CTkFont(size=12),
                     text_color="gray60").grid(row=0, column=0)
        self.folder_lbl = ctk.CTkLabel(bar, text=self.dir_ref[0],
                                       font=ctk.CTkFont(size=11), text_color="gray70", anchor="w")
        self.folder_lbl.grid(row=0, column=1, padx=(8, 8), sticky="ew")
        ctk.CTkButton(bar, text="변경", width=60, height=26,
                      command=self._pick_folder).grid(row=0, column=2)

        ctk.CTkLabel(self, text="URL 입력  (YouTube / Spotify 서로 섞어도 됩니다)",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=3, column=0, padx=24, pady=(0, 4), sticky="w")

        self.url_box = ctk.CTkTextbox(self, height=90, font=ctk.CTkFont(size=12))
        self.url_box.grid(row=4, column=0, padx=24, sticky="ew")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=5, column=0, padx=24, pady=(6, 0), sticky="ew")
        ctk.CTkButton(btn_row, text="붙여넣기", width=90, height=30,
                      command=self._paste).grid(row=0, column=0)
        ctk.CTkButton(btn_row, text="초기화", width=70, height=30, fg_color="gray30",
                      command=lambda: self.url_box.delete("1.0", "end")).grid(
            row=0, column=1, padx=(8, 0))

        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.grid(row=6, column=0, padx=24, pady=(12, 0), sticky="ew")

        ctk.CTkLabel(opt, text="포맷", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
        self.fmt_var = ctk.StringVar(value="mp3")
        ctk.CTkOptionMenu(opt, values=["mp3", "m4a", "wav", "flac"],
                          variable=self.fmt_var, width=90, height=32).grid(
            row=1, column=0, pady=(4, 0), sticky="w")

        ctk.CTkLabel(opt, text="음질", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=1, padx=(20, 0), sticky="w")
        self.qual_var = ctk.StringVar(value="320k")
        ctk.CTkOptionMenu(opt, values=["320k", "256k", "192k", "128k"],
                          variable=self.qual_var, width=90, height=32).grid(
            row=1, column=1, padx=(20, 0), pady=(4, 0), sticky="w")

        ctk.CTkLabel(opt, text="동시 다운로드", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, padx=(20, 0), sticky="w")
        self.worker_var = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(opt, values=["1", "2", "3", "4", "5"],
                          variable=self.worker_var, width=70, height=32).grid(
            row=1, column=2, padx=(20, 0), pady=(4, 0), sticky="w")

        self.dl_btn = ctk.CTkButton(self, text="다운로드", height=44,
                                    font=ctk.CTkFont(size=15, weight="bold"),
                                    command=self._start)
        self.dl_btn.grid(row=7, column=0, padx=24, pady=(14, 0), sticky="ew")

        ctk.CTkLabel(self, text="진행 상황", font=ctk.CTkFont(size=12, weight="bold")).grid(
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
        init = self.dir_ref[0] if os.path.isdir(self.dir_ref[0]) else os.path.expanduser("~")
        f = filedialog.askdirectory(initialdir=init)
        if f:
            self.dir_ref[0] = f
            self.folder_lbl.configure(text=f)

    def _spotify_settings(self):
        cfg = load_config()
        win = ctk.CTkToplevel(self)
        win.title("Spotify API 설정")
        win.geometry("460x480")
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

        # Show login status (dynamic label so logout can update it)
        import time as _time

        def _get_login_status():
            if os.path.exists(TOKEN_CACHE):
                try:
                    with open(TOKEN_CACHE) as _f:
                        _c = json.load(_f)
                    if _c.get("expires_at", 0) > _time.time():
                        return "✅ Spotify 로그인됨 (OAuth 토큰 유효)", "#4CAF50"
                    elif _c.get("refresh_token"):
                        return "⚠️ 로그인됨 (토큰 만료, 자동 갱신 예정)", "#FF9800"
                    else:
                        return "❌ 갱신 불가 — 다시 로그인 필요", "#f44336"
                except Exception:
                    return "❌ 캐시 손상 — 다시 로그인 필요", "#f44336"
            return "로그인 상태: 없음", "gray60"

        status_txt, status_col = _get_login_status()
        status_lbl = ctk.CTkLabel(win, text=status_txt, font=ctk.CTkFont(size=11),
                                  text_color=status_col)
        status_lbl.pack(padx=24, pady=(8, 0), anchor="w")

        def logout():
            try:
                os.remove(TOKEN_CACHE)
            except Exception:
                pass
            status_lbl.configure(text="로그인 상태: 없음", text_color="gray60")
            test_lbl.configure(text="로그아웃 완료. 다시 🔑 로그인해 주세요.", text_color="gray60")

        logout_btn = ctk.CTkButton(win, text="로그아웃", width=80, height=26,
                                   fg_color="gray25", hover_color="gray35",
                                   font=ctk.CTkFont(size=11), command=logout)
        logout_btn.pack(padx=24, pady=(4, 0), anchor="w")

        test_lbl = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=11))
        test_lbl.pack(padx=24, pady=(2, 0), anchor="w")

        def test_connection():
            cid = cid_entry.get().strip()
            sec = sec_entry.get().strip()
            if not cid or not sec:
                test_lbl.configure(text="ID와 Secret을 입력하세요", text_color="gray")
                return
            test_lbl.configure(text="테스트 중...", text_color="gray60")
            win.update_idletasks()
            try:
                creds = base64.b64encode(f"{cid}:{sec}".encode()).decode()
                req = urllib.request.Request(
                    "https://accounts.spotify.com/api/token",
                    data=b"grant_type=client_credentials",
                    headers={"Authorization": f"Basic {creds}",
                             "Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    json.loads(r.read())["access_token"]
                test_lbl.configure(text="연결 성공!", text_color="#4CAF50")
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="ignore")
                test_lbl.configure(text=f"실패 ({e.code}): {body[:60]}", text_color="#f44336")
            except Exception as e:
                test_lbl.configure(text=f"실패: {str(e)[:60]}", text_color="#f44336")

        def save():
            cfg["spotify_client_id"] = cid_entry.get().strip()
            cfg["spotify_client_secret"] = sec_entry.get().strip()
            save_config(cfg)
            messagebox.showinfo("저장됨", "Spotify API 키가 저장되었습니다!")
            win.destroy()

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(8, 4), fill="x")
        ctk.CTkButton(btn_frame, text="연결 테스트", width=110, height=34,
                      fg_color="gray30", hover_color="gray40",
                      command=test_connection).pack(side="left")
        ctk.CTkButton(btn_frame, text="저장", width=80, height=34,
                      command=save).pack(side="right")

        def run_diagnostics():
            diag_win = ctk.CTkToplevel(win)
            diag_win.title("Spotify 진단")
            diag_win.geometry("560x420")
            diag_win.grab_set()
            log = ctk.CTkTextbox(diag_win, font=ctk.CTkFont(family="Courier", size=11))
            log.pack(fill="both", expand=True, padx=12, pady=12)

            TEST_PL = "37i9dQZF1DXcBWIGoYBM5M"  # Spotify 공식 차트 (함수 밖 정의)

            def add(line):
                try:
                    log.insert("end", line + "\n")
                    log.see("end")
                    diag_win.update_idletasks()
                except Exception:
                    pass  # 창이 닫혀도 thread crash 방지

            def _run():
                cid = cid_entry.get().strip()
                sec = sec_entry.get().strip()
                add("=== Spotify 진단 시작 ===\n")

                # 1. 익명 토큰
                add("[1] 익명 토큰 (get_access_token)...")
                try:
                    anon = _get_anon_token()
                    add(f"    OK: {anon[:40]}...\n")
                except Exception as e:
                    add(f"    FAIL: {e}\n")
                    anon = None

                # 2. 익명 토큰으로 공개 플레이리스트 접근
                if anon:
                    add("[2] 익명 토큰으로 공개 플레이리스트 접근...")
                    try:
                        data = _spotify_get(anon, f"playlists/37i9dQZF1DXcBWIGoYBM5M")
                        add(f"    OK: '{data.get('name')}'\n")
                    except Exception as e:
                        add(f"    FAIL: {e}\n")

                # 3. OAuth 캐시 확인
                add("[3] OAuth 캐시 확인...")
                import time as _t
                oauth_token = None
                if os.path.exists(TOKEN_CACHE):
                    try:
                        with open(TOKEN_CACHE) as f:
                            cached = json.load(f)
                        exp = cached.get("expires_at", 0)
                        remaining = int(exp - _t.time())
                        add(f"    캐시 있음 — 만료까지 {remaining}초")
                        if remaining > 0:
                            oauth_token = cached["access_token"]
                            add(f"    토큰: {oauth_token[:40]}...\n")
                        else:
                            add("    토큰 만료됨\n")
                    except Exception as e:
                        add(f"    캐시 읽기 오류: {e}\n")
                else:
                    add("    캐시 없음 (로그인 필요)\n")

                # 4. OAuth 토큰으로 /me 접근
                if oauth_token:
                    add("[4] OAuth 토큰으로 /me 접근...")
                    try:
                        me = _spotify_get(oauth_token, "me")
                        add(f"    OK: {me.get('display_name') or me.get('id')}\n")
                    except Exception as e:
                        add(f"    FAIL: {e}\n")

                    add("[5] OAuth 토큰으로 공개 플레이리스트 접근...")
                    try:
                        data = _spotify_get(oauth_token, f"playlists/37i9dQZF1DXcBWIGoYBM5M")
                        add(f"    OK: '{data.get('name')}'\n")
                    except Exception as e:
                        add(f"    FAIL: {e}\n")

                # 5. Client Credentials
                if cid and sec:
                    add("[6] Client Credentials 토큰...")
                    try:
                        cc_data = _exchange_token(cid, sec, {"grant_type": "client_credentials"})
                        cc_token = cc_data["access_token"]
                        add(f"    OK: {cc_token[:40]}...\n")
                        add("[7] CC 토큰으로 공개 플레이리스트 접근...")
                        try:
                            data = _spotify_get(cc_token, f"playlists/37i9dQZF1DXcBWIGoYBM5M")
                            add(f"    OK: '{data.get('name')}'\n")
                        except Exception as e:
                            add(f"    FAIL: {e}\n")
                    except Exception as e:
                        add(f"    FAIL: {e}\n")

                add("=== 진단 완료 ===")

            threading.Thread(target=_run, daemon=True).start()

        ctk.CTkButton(win, text="🔍 진단 실행", height=30,
                      fg_color="gray25", hover_color="gray35",
                      font=ctk.CTkFont(size=12),
                      command=run_diagnostics).pack(padx=24, pady=(0, 4), fill="x")

        url_box = ctk.CTkEntry(win, width=410, height=28, font=ctk.CTkFont(size=10),
                               placeholder_text="로그인 버튼을 누르면 인증 URL이 여기에 표시됩니다")
        url_box.pack(padx=24, pady=(4, 0))

        def copy_url():
            txt = url_box.get()
            if txt:
                win.clipboard_clear()
                win.clipboard_append(txt)
                test_lbl.configure(text="URL 복사됨 — 브라우저 주소창에 붙여넣어 여세요", text_color="gray60")

        def open_url():
            txt = url_box.get()
            if txt:
                opened = webbrowser.open(txt)
                if not opened:
                    test_lbl.configure(text="브라우저 자동 열기 실패 — URL을 직접 복사해 여세요", text_color="#FF9800")

        url_btn_row = ctk.CTkFrame(win, fg_color="transparent")
        url_btn_row.pack(padx=24, pady=(2, 0), fill="x")
        ctk.CTkButton(url_btn_row, text="URL 복사", width=90, height=26,
                      fg_color="gray30", hover_color="gray40",
                      font=ctk.CTkFont(size=11), command=copy_url).pack(side="left")
        ctk.CTkButton(url_btn_row, text="브라우저로 열기", width=110, height=26,
                      fg_color="gray30", hover_color="gray40",
                      font=ctk.CTkFont(size=11), command=open_url).pack(side="left", padx=(6, 0))

        def login():
            cid = cid_entry.get().strip()
            sec = sec_entry.get().strip()
            if not cid or not sec:
                test_lbl.configure(text="ID와 Secret을 먼저 저장하세요", text_color="gray")
                return
            cfg["spotify_client_id"] = cid
            cfg["spotify_client_secret"] = sec
            save_config(cfg)

            auth_url = build_auth_url(cid)
            url_box.delete(0, "end")
            url_box.insert(0, auth_url)
            test_lbl.configure(text="대기 중 — 브라우저에서 로그인 후 이 창으로 돌아오세요", text_color="gray60")
            win.update_idletasks()

            def _do():
                try:
                    webbrowser.open(auth_url)
                    code = wait_for_oauth_code()
                    if not code:
                        raise Exception("인증 코드를 받지 못했습니다. 브라우저에서 승인했는지 확인해 주세요.")
                    name = finish_oauth(cid, sec, code)
                    msg = f"✅ 로그인 완료! ({name})"
                    col = "#4CAF50"
                except Exception as e:
                    msg = f"오류: {e}"
                    col = "#f44336"
                win.after(0, lambda: test_lbl.configure(text=msg, text_color=col))
            threading.Thread(target=_do, daemon=True).start()

        ctk.CTkButton(win, text="🔑 Spotify 로그인", height=34,
                      fg_color="#1DB954", hover_color="#1aa34a",
                      command=login).pack(padx=24, pady=(8, 4), fill="x")

    def _get_urls(self):
        text = self.url_box.get("1.0", "end")
        urls = re.findall(r"https?://[^\s\"'<>]+", text)
        urls = [u for u in urls if detect_source(u)]
        if not urls:
            messagebox.showwarning("알림", "YouTube 또는 Spotify URL을 찾을 수 없습니다.")
        return urls

    def _start(self):
        urls = self._get_urls()
        if not urls:
            return

        save_dir = self.dir_ref[0]
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("저장 폴더 오류",
                f"저장 위치를 만들 수 없습니다:\n{save_dir}\n\n{e}\n\n'변경' 버튼으로 다른 폴더를 선택해 주세요.")
            return

        for w in self.queue_frame.winfo_children():
            w.destroy()
        self._rows = []
        for i, url in enumerate(urls):
            row = DownloadRow(self.queue_frame, url, i)
            row.grid(row=i, column=0, sticky="ew", pady=(0, 4))
            self._rows.append(row)

        self.dl_btn.configure(state="disabled", text=f"{len(urls)}개 다운로드 중...")
        workers = int(self.worker_var.get())
        fmt = self.fmt_var.get()
        quality = self.qual_var.get().replace("k", "")
        threading.Thread(target=self._run_all,
                         args=(urls, workers, fmt, quality, save_dir),
                         daemon=True).start()

    def _run_all(self, urls, workers, fmt, quality, save_dir):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self._download_one, i, url, fmt, quality, save_dir)
                       for i, url in enumerate(urls)]
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass
        self.after(0, lambda: self.dl_btn.configure(state="normal", text="다운로드"))

    def _download_one(self, idx, url, fmt, quality, save_dir):
        row = self._rows[idx]
        url = clean_url(url)
        source = detect_source(url)
        self.after(0, row.set_status, "시작 중...", 0.02)

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes", 0)
                pct = (done / total) if total else 0
                spd = d.get("speed") or 0
                s = f"{spd/1024/1024:.1f} MB/s" if spd else "..."
                self.after(0, row.set_status, f"다운로드 중 {pct*100:.0f}% — {s}", pct)
            elif d["status"] == "finished":
                self.after(0, row.set_status, "변환 중...", 0.95)

        os.makedirs(save_dir, exist_ok=True)

        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(save_dir, "%(title)s.%(ext)s"),
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": fmt, "preferredquality": quality},
                {"key": "FFmpegMetadata"},
            ],
            "progress_hooks": [hook],
            "socket_timeout": 30,
            "retries": 3,
            "quiet": True, "no_warnings": True,
            "windowsfilenames": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "nooverwrites": True,
            "download_archive": os.path.join(save_dir, ".ytdl_archive"),
        }

        sp_history_file = os.path.join(save_dir, ".spotify_downloaded")

        def _file_exists_in_dir(query):
            """저장 폴더에서 쿼리 키워드가 포함된 음악 파일이 있는지 확인."""
            if not os.path.isdir(save_dir):
                return False
            normalized = re.sub(r"[^\w\s]", " ", query.lower()).strip()
            words = [w for w in normalized.split() if len(w) > 2][:4]
            if not words:
                return False
            try:
                for fname in os.listdir(save_dir):
                    if not fname.lower().endswith(("." + fmt,)):
                        continue
                    fname_norm = re.sub(r"[^\w\s]", " ", fname.lower())
                    if sum(1 for w in words if w in fname_norm) >= min(len(words), 2):
                        return True
            except Exception:
                pass
            return False

        def _already_done(query):
            """히스토리 파일 또는 폴더 스캔으로 이미 다운됐는지 확인."""
            if os.path.exists(sp_history_file):
                try:
                    with open(sp_history_file, encoding="utf-8") as _f:
                        if query.strip().lower() in {l.strip().lower() for l in _f}:
                            return True
                except Exception:
                    pass
            return _file_exists_in_dir(query)

        def _mark_done(query):
            try:
                with open(sp_history_file, "a", encoding="utf-8") as _f:
                    _f.write(query.strip() + "\n")
            except Exception:
                pass

        try:
            if source == "spotify":
                self.after(0, row.set_status, "Spotify 정보 가져오는 중...", 0.05)
                tracks, name = get_spotify_tracks(url)
                if not tracks:
                    raise Exception("트랙 정보를 가져올 수 없습니다.")
                count = len(tracks)
                self.after(0, row.set_title, f"{name}  ({count}곡)" if count > 1 else name)
                skipped = 0
                for i, query in enumerate(tracks):
                    pct = 0.1 + (i / count * 0.85)
                    if _already_done(query):
                        skipped += 1
                        self.after(0, row.set_status,
                            f"[{i+1}/{count}] 스킵 (이미 다운됨): {query[:40]}", pct)
                        continue
                    self.after(0, row.set_status, f"[{i+1}/{count}] {query[:50]}", pct)
                    _run_ydl(opts, f"ytsearch1:{query}", timeout=180)
                    _mark_done(query)

            else:
                self.after(0, row.set_status, "정보 가져오는 중...", 0.05)
                _run_ydl(opts, url, timeout=600)

            if source == "spotify" and skipped:
                self.after(0, row.done, True)
                self.after(0, row.set_status,
                    f"완료 ({count - skipped}곡 다운 / {skipped}곡 스킵)", 1.0)
                self.after(0, row.status_lbl.configure, {"text_color": "#4CAF50"})
            else:
                self.after(0, row.done, True)

        except Exception as e:
            err = str(e)
            short = err[:100] if err else "알 수 없는 오류"
            self.after(0, row.done, False, short)
            if source == "spotify" and len(err) > 50:
                self.after(0, messagebox.showerror, "Spotify 오류", err)


if __name__ == "__main__":
    app = App()
    app.mainloop()
