# YouTube MP3 Downloader

깔끔한 GUI를 가진 YouTube 다운로더. yt-dlp 기반.

## 실행 방법 (Windows)

### 1. Python 설치
https://www.python.org/downloads/ 에서 Python 3.10 이상 설치

### 2. 패키지 설치
```
pip install -r requirements.txt
```

> MP3 변환을 위해 FFmpeg도 필요합니다:
> https://ffmpeg.org/download.html 에서 다운받아 PATH에 추가하거나,
> `winget install ffmpeg` 로 설치

### 3. 실행
```
python downloader.py
```

## 기능
- YouTube URL 붙여넣기 → 바로 다운로드
- MP3 / M4A / WAV / MP4 / WebM 포맷 선택
- 음질 선택 (128k ~ 320k)
- 저장 폴더 선택
- 실시간 다운로드 진행률
