import re
from typing import Dict, List, Optional

import httpx

try:
    from pytube import Playlist, YouTube
except ImportError:
    Playlist = None
    YouTube = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable
except ImportError:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = NoTranscriptFound = NoTranscriptAvailable = Exception


class YouTubeService:
    VIDEO_PATTERNS = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([\w-]{11})",
    ]
    PLAYLIST_PATTERNS = [
        r"[?&]list=([\w-]+)",
    ]

    def extract_video_id(self, url: str) -> Optional[str]:
        if not url:
            return None
        for pattern in self.VIDEO_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_playlist_id(self, url: str) -> Optional[str]:
        if not url:
            return None
        for pattern in self.PLAYLIST_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_video_title(self, video_url: str) -> str:
        if YouTube is not None:
            yt = YouTube(video_url)
            return yt.title

        response = httpx.get(video_url, timeout=20)
        response.raise_for_status()
        match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).replace(" - YouTube", "").strip()
        raise RuntimeError("Unable to parse video title from YouTube page")

    def fetch_video_transcript(self, video_id: str) -> str:
        if YouTubeTranscriptApi is None:
            raise RuntimeError("youtube-transcript-api is not installed")
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
        return " ".join(segment.get("text", "") for segment in transcript)

    def fetch_playlist_items(self, playlist_url: str) -> List[Dict[str, str]]:
        if Playlist is not None:
            playlist = Playlist(playlist_url)
            items = []
            for video_url in playlist.video_urls:
                video_id = self.extract_video_id(video_url)
                if not video_id:
                    continue
                title = self.fetch_video_title(video_url)
                items.append({"id": video_id, "url": video_url, "title": title})
            return items

        raise RuntimeError("pytube is not installed")


youtube_service = YouTubeService()
