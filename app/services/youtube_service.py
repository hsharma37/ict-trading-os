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
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    try:
        from youtube_transcript_api._errors import NoTranscriptAvailable
    except ImportError:
        NoTranscriptAvailable = NoTranscriptFound
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

    def _http_headers(self) -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def _fetch_oembed_title(self, video_url: str) -> Optional[str]:
        try:
            endpoint = f"https://www.youtube.com/oembed?url={video_url}&format=json"
            response = httpx.get(endpoint, timeout=20, headers=self._http_headers())
            response.raise_for_status()
            data = response.json()
            title = data.get("title")
            if title:
                return title.strip()
        except Exception:
            return None

    def _fetch_html_title(self, video_url: str) -> Optional[str]:
        try:
            response = httpx.get(video_url, timeout=20, headers=self._http_headers())
            response.raise_for_status()
            content = response.text
            match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).replace(" - YouTube", "").strip()

            match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

            match = re.search(r'<meta\s+name="title"\s+content="([^"]+)"', content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception:
            return None
        return None

    def fetch_video_title(self, video_url: str) -> str:
        if YouTube is not None:
            try:
                yt = YouTube(video_url)
                if yt.title:
                    return yt.title
            except Exception:
                pass

        title = self._fetch_oembed_title(video_url)
        if title:
            return title

        title = self._fetch_html_title(video_url)
        if title:
            return title

        video_id = self.extract_video_id(video_url) or "unknown"
        return f"YouTube video {video_id}"

    def fetch_video_transcript(self, video_id: str) -> str:
        if YouTubeTranscriptApi is None:
            raise RuntimeError("youtube-transcript-api is not installed")
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US"])
        return " ".join(getattr(segment, "text", "") for segment in transcript)

    def fetch_playlist_items(self, playlist_url: str) -> List[Dict[str, str]]:
        items = []
        if Playlist is not None:
            try:
                playlist = Playlist(playlist_url)
                for video_url in playlist.video_urls:
                    video_id = self.extract_video_id(video_url)
                    if not video_id:
                        continue
                    title = self.fetch_video_title(video_url)
                    items.append({"id": video_id, "url": video_url, "title": title})
                if items:
                    return items
            except Exception:
                pass

        playlist_id = self.extract_playlist_id(playlist_url)
        if playlist_id:
            try:
                page_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                response = httpx.get(page_url, timeout=20, headers=self._http_headers())
                response.raise_for_status()
                matches = re.findall(r'href="(/watch\?v=[\w-]{11}&list=[\w-]+[^"]*)"', response.text)
                seen = set()
                for match in matches:
                    full_url = f"https://www.youtube.com{match}"
                    video_id = self.extract_video_id(full_url)
                    if not video_id or video_id in seen:
                        continue
                    seen.add(video_id)
                    title = self.fetch_video_title(full_url)
                    items.append({"id": video_id, "url": full_url, "title": title})
                if items:
                    return items
            except Exception:
                pass

        if items:
            return items

        if Playlist is None:
            raise RuntimeError("pytube is not installed and playlist parsing failed")

        raise RuntimeError("Unable to load playlist items")


youtube_service = YouTubeService()
