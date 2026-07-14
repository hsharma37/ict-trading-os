"""
YouTube Service — Modern, robust video/channel metadata extraction and transcription.

Replaces broken pytube with yt-dlp (actively maintained, supports thousands of sites).
Uses youtube-transcript-api>=1.0.0 with the new API syntax.
Optional faster-whisper fallback when captions are disabled.

Inspired by modern agent-based video analysis pipelines:
- yt-dlp: https://github.com/yt-dlp/yt-dlp (50k+ stars, industry standard)
- youtube-transcript-api: https://github.com/jdepoix/youtube-transcript-api
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
"""
import re
import os
import json
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx

# ────────────────────────────────────────────────
# yt-dlp (modern replacement for pytube)
# ────────────────────────────────────────────────
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ────────────────────────────────────────────────
# youtube-transcript-api (latest API)
# ────────────────────────────────────────────────
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

# ────────────────────────────────────────────────
# faster-whisper (optional audio transcription fallback)
# ────────────────────────────────────────────────
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


@dataclass
class VideoMetadata:
    """Rich metadata for a YouTube video."""
    video_id: str
    title: str
    description: str = ""
    channel: str = ""
    channel_id: str = ""
    duration: int = 0
    view_count: int = 0
    like_count: int = 0
    upload_date: str = ""
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    thumbnail: str = ""
    url: str = ""
    language: str = "en"
    has_captions: bool = False


@dataclass
class VideoTranscript:
    """Transcript with timing and metadata."""
    video_id: str
    text: str
    segments: List[Dict[str, Any]] = field(default_factory=list)
    language: str = "en"
    is_generated: bool = False
    source: str = "caption"  # caption | whisper | fallback


@dataclass
class VideoAnalysis:
    """Structured AI analysis of a video."""
    video_id: str
    title: str
    summary: str = ""
    key_concepts: List[str] = field(default_factory=list)
    timestamps: List[Dict[str, str]] = field(default_factory=list)
    ict_relevance: str = ""
    trading_insights: str = ""
    sentiment: str = "neutral"
    word_count: int = 0


class YouTubeService:
    """
    Modern YouTube service using yt-dlp for metadata and youtube-transcript-api
    for captions, with optional faster-whisper audio fallback.
    """

    VIDEO_PATTERNS = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([\w-]{11})",
    ]
    PLAYLIST_PATTERNS = [
        r"[?&]list=([\w-]+)",
    ]
    CHANNEL_PATTERNS = [
        r"youtube\.com/(?:c/|channel/|@)([^/?&]+)",
        r"youtube\.com/user/([^/?&]+)",
    ]

    def __init__(self):
        self._http_client = httpx.Client(timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self._whisper_model = None

    # ────────────────────────────────────────────────
    # URL Parsing
    # ────────────────────────────────────────────────

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

    def extract_channel_handle(self, url: str) -> Optional[str]:
        if not url:
            return None
        for pattern in self.CHANNEL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    # ────────────────────────────────────────────────
    # Metadata Extraction (yt-dlp)
    # ────────────────────────────────────────────────

    def _ytdlp_extract(self, url: str, extract_flat: bool = False) -> Optional[Dict]:
        """Extract video/playlist/channel metadata using yt-dlp."""
        if yt_dlp is None:
            return None
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': extract_flat,
                'ignoreerrors': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            print(f"[yt-dlp] Extraction failed: {e}")
            return None

    def fetch_video_metadata(self, url: str) -> Optional[VideoMetadata]:
        """Fetch rich metadata for a single video."""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None

        info = self._ytdlp_extract(url)
        if not info:
            # Bridge (residential IP) first — YouTube blocks title/oembed from
            # cloud IPs just like captions.
            bmeta = self._fetch_meta_via_bridge(video_id)
            if bmeta and bmeta.get("title"):
                return VideoMetadata(
                    video_id=video_id,
                    title=bmeta["title"],
                    channel=bmeta.get("author", "") or "",
                    thumbnail=bmeta.get("thumbnail", "") or "",
                    url=url,
                )
            # Fallback: direct oEmbed (works from a local/residential runtime).
            title = self._fetch_oembed_title(url) or f"YouTube video {video_id}"
            return VideoMetadata(
                video_id=video_id,
                title=title,
                url=url,
            )

        # Parse duration (ISO 8601 or seconds)
        duration = info.get('duration') or 0
        if isinstance(duration, str):
            # Try to parse PT#M#S format
            duration = self._parse_iso8601_duration(duration)

        upload_date = info.get('upload_date') or ''
        if upload_date and len(upload_date) == 8:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

        return VideoMetadata(
            video_id=video_id,
            title=info.get('title', 'Unknown'),
            description=info.get('description', ''),
            channel=info.get('uploader', ''),
            channel_id=info.get('channel_id', ''),
            duration=duration,
            view_count=info.get('view_count') or 0,
            like_count=info.get('like_count') or 0,
            upload_date=upload_date,
            tags=info.get('tags', []) or [],
            categories=info.get('categories', []) or [],
            thumbnail=info.get('thumbnail', ''),
            url=url,
            language=info.get('language', 'en'),
            has_captions=bool(info.get('subtitles') or info.get('automatic_captions')),
        )

    def fetch_playlist_items(self, playlist_url: str) -> List[Dict[str, str]]:
        """Fetch all video IDs and titles from a playlist."""
        info = self._ytdlp_extract(playlist_url, extract_flat=False)
        if not info:
            return []

        items = []
        entries = info.get('entries') or []
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get('id') or self.extract_video_id(entry.get('url', ''))
            if not video_id:
                continue
            items.append({
                'id': video_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'title': entry.get('title', 'Unknown'),
            })
        return items

    def fetch_channel_videos(self, channel_url: str, max_videos: int = 50) -> List[Dict[str, str]]:
        """Fetch recent videos from a channel."""
        # Convert channel URL to videos tab URL if needed
        if '/videos' not in channel_url:
            if channel_url.endswith('/'):
                channel_url = channel_url + 'videos'
            else:
                channel_url = channel_url + '/videos'

        info = self._ytdlp_extract(channel_url, extract_flat=True)
        if not info:
            return []

        items = []
        entries = info.get('entries') or []
        for entry in entries[:max_videos]:
            if not entry:
                continue
            video_id = entry.get('id') or self.extract_video_id(entry.get('url', ''))
            if not video_id:
                continue
            items.append({
                'id': video_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'title': entry.get('title', 'Unknown'),
            })
        return items

    # ────────────────────────────────────────────────
    # Transcript Extraction
    # ────────────────────────────────────────────────

    def fetch_video_transcript(
        self,
        video_id: str,
        languages: List[str] = None,
        allow_whisper: bool = True,
    ) -> VideoTranscript:
        """
        Fetch transcript using youtube-transcript-api (latest API syntax).
        Falls back to faster-whisper audio transcription if captions are disabled.
        """
        languages = languages or ["en", "en-US", "en-GB"]

        # Preferred path: fetch via the MT5 bridge's residential IP. YouTube
        # blocks caption requests from cloud/serverless IPs, so a *direct*
        # attempt from Vercel always fails — the bridge (on the user's own
        # machine) is not blocked.
        bridge_t = self._fetch_transcript_via_bridge(video_id, languages)
        if bridge_t and bridge_t.text:
            return bridge_t

        if YouTubeTranscriptApi is None:
            return VideoTranscript(video_id=video_id, text='', segments=[], source='fallback')

        # Try captions directly (works from a residential/local runtime).
        try:
            ytt_api = YouTubeTranscriptApi()
            fetched = ytt_api.fetch(video_id, languages=languages)

            segments = []
            text_parts = []
            for snippet in fetched:
                seg_text = snippet.text
                text_parts.append(seg_text)
                segments.append({
                    'text': seg_text,
                    'start': snippet.start,
                    'duration': getattr(snippet, 'duration', 0),
                })

            return VideoTranscript(
                video_id=video_id,
                text=' '.join(text_parts),
                segments=segments,
                language=fetched.language or languages[0],
                is_generated=getattr(fetched, 'is_generated', False),
                source='caption',
            )
        except (TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable) as e:
            print(f"[Transcript] Captions unavailable for {video_id}: {e}")
            if not allow_whisper:
                return VideoTranscript(video_id=video_id, text='', segments=[], source='fallback')
            # Fallback to whisper audio transcription
            return self._transcribe_with_whisper(video_id, languages)
        except Exception as e:
            print(f"[Transcript] Error fetching captions for {video_id}: {e}")
            if not allow_whisper:
                return VideoTranscript(video_id=video_id, text='', segments=[], source='fallback')
            # Try whisper as last resort
            return self._transcribe_with_whisper(video_id, languages)

    def _fetch_meta_via_bridge(self, video_id: str) -> Optional[Dict]:
        """Fetch video title/author via the MT5 bridge (residential IP)."""
        from app.core.config import settings
        base = getattr(settings, "MT5_BRIDGE_URL", "")
        if not base:
            return None
        headers = {"ngrok-skip-browser-warning": "true"}
        if getattr(settings, "MT5_BRIDGE_API_KEY", ""):
            headers["X-Bridge-Key"] = settings.MT5_BRIDGE_API_KEY
        try:
            resp = self._http_client.get(f"{base}/video-meta/{video_id}", headers=headers, timeout=20)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def _fetch_transcript_via_bridge(self, video_id: str, languages: List[str]) -> Optional[VideoTranscript]:
        """Fetch the transcript through the MT5 bridge (residential IP), when
        configured. Returns None to fall back to a direct attempt."""
        from app.core.config import settings
        base = getattr(settings, "MT5_BRIDGE_URL", "")
        if not base:
            return None
        headers = {"ngrok-skip-browser-warning": "true"}
        if getattr(settings, "MT5_BRIDGE_API_KEY", ""):
            headers["X-Bridge-Key"] = settings.MT5_BRIDGE_API_KEY
        try:
            resp = self._http_client.get(
                f"{base}/transcript/{video_id}",
                params={"languages": ",".join(languages)},
                headers=headers,
                timeout=45,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data.get("text"):
                return None
            return VideoTranscript(
                video_id=video_id,
                text=data["text"],
                segments=data.get("segments", []),
                language=data.get("language", languages[0] if languages else "en"),
                is_generated=bool(data.get("is_generated", False)),
                source="bridge",
            )
        except Exception as e:
            print(f"[Transcript] Bridge fetch failed for {video_id}: {e}")
            return None

    def _transcribe_with_whisper(self, video_id: str, languages: List[str]) -> VideoTranscript:
        """Download audio and transcribe with faster-whisper."""
        if WhisperModel is None:
            print("[Whisper] faster-whisper not installed, skipping audio fallback")
            return VideoTranscript(
                video_id=video_id,
                text='',
                segments=[],
                source='fallback',
            )

        try:
            # Download audio only using yt-dlp subprocess
            url = f"https://www.youtube.com/watch?v={video_id}"
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_path = os.path.join(tmpdir, f"{video_id}.m4a")
                cmd = [
                    'yt-dlp', '-f', 'bestaudio[ext=m4a]/bestaudio',
                    '--extract-audio', '--audio-format', 'm4a',
                    '-o', audio_path, url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0 or not os.path.exists(audio_path):
                    # Try mp3 fallback
                    audio_path = os.path.join(tmpdir, f"{video_id}.mp3")
                    cmd = [
                        'yt-dlp', '-f', 'bestaudio',
                        '--extract-audio', '--audio-format', 'mp3',
                        '-o', audio_path, url
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode != 0 or not os.path.exists(audio_path):
                        return VideoTranscript(video_id=video_id, text='', segments=[], source='fallback')

                # Load model lazily
                if self._whisper_model is None:
                    print("[Whisper] Loading model (first time, may take a moment)...")
                    self._whisper_model = WhisperModel('base', device='cpu', compute_type='int8')

                segments_iter, _ = self._whisper_model.transcribe(audio_path, language=languages[0][:2])
                segments = []
                text_parts = []
                for seg in segments_iter:
                    text_parts.append(seg.text)
                    segments.append({
                        'text': seg.text,
                        'start': seg.start,
                        'duration': seg.end - seg.start,
                    })

                return VideoTranscript(
                    video_id=video_id,
                    text=' '.join(text_parts),
                    segments=segments,
                    language=languages[0],
                    is_generated=True,
                    source='whisper',
                )
        except Exception as e:
            print(f"[Whisper] Audio transcription failed for {video_id}: {e}")
            return VideoTranscript(video_id=video_id, text='', segments=[], source='fallback')

    # ────────────────────────────────────────────────
    # AI Analysis (Agent-style)
    # ────────────────────────────────────────────────

    def analyze_transcript(self, transcript: VideoTranscript, metadata: VideoMetadata) -> VideoAnalysis:
        """
        Generate structured analysis from transcript + metadata.
        Uses simple heuristics + ICT keyword extraction.
        For full LLM-powered analysis, use VideoAnalysisAgent.
        """
        text = transcript.text
        word_count = len(text.split()) if text else 0

        # Extract key concepts from ICT trading methodology
        keywords = {
            'MSS': ['market structure shift', 'mss', 'break of structure', 'bos', 'change of character', 'choch'],
            'FVG': ['fair value gap', 'fvg', 'imbalance', 'inefficiency', 'void'],
            'OB': ['order block', 'orderblock', 'ob', 'breaker block', 'mitigation block'],
            'Liquidity': ['liquidity', 'stop hunt', 'liquidity sweep', 'liquidity pool', 'inducement'],
            'PD Arrays': ['premium', 'discount', 'optimal trade entry', 'ote', 'fibonacci', '50%'],
            'Killzones': ['london open', 'new york open', 'ny session', 'asian session', 'killzone'],
            'Time': ['time-based', 'timeframe', 'daily bias', 'weekly bias', 'monthly bias'],
            'Risk Management': ['risk management', 'lot size', 'position size', 'risk reward', '1:2', '1:3'],
        }

        key_concepts = []
        text_lower = text.lower()
        for concept, terms in keywords.items():
            if any(term in text_lower for term in terms):
                key_concepts.append(concept)

        # Extract timestamps for key concepts
        timestamps = []
        if transcript.segments:
            for concept, terms in keywords.items():
                for seg in transcript.segments:
                    if any(term in seg['text'].lower() for term in terms):
                        start = seg['start']
                        minutes = int(start // 60)
                        seconds = int(start % 60)
                        timestamps.append({
                            'time': f"{minutes}:{seconds:02d}",
                            'concept': concept,
                            'text': seg['text'][:100],
                        })
                        break  # Only first mention per concept

        # Determine sentiment
        bullish = text_lower.count('bullish') + text_lower.count('long') + text_lower.count('buy')
        bearish = text_lower.count('bearish') + text_lower.count('short') + text_lower.count('sell')
        sentiment = 'bullish' if bullish > bearish else 'bearish' if bearish > bullish else 'neutral'

        # Generate summary (first 500 chars + concept list)
        summary = text[:500] + '...' if len(text) > 500 else text
        if not summary:
            summary = f"No transcript available for '{metadata.title}'. Video may have captions disabled."

        ict_relevance = 'high' if len(key_concepts) >= 4 else 'medium' if len(key_concepts) >= 2 else 'low'

        return VideoAnalysis(
            video_id=metadata.video_id,
            title=metadata.title,
            summary=summary,
            key_concepts=key_concepts,
            timestamps=timestamps[:10],  # Cap at 10
            ict_relevance=ict_relevance,
            trading_insights=f"Key concepts covered: {', '.join(key_concepts)}. Overall sentiment: {sentiment}.",
            sentiment=sentiment,
            word_count=word_count,
        )

    # ────────────────────────────────────────────────
    # Channel Analysis
    # ────────────────────────────────────────────────

    def analyze_channel(self, channel_url: str, max_videos: int = 20) -> Dict[str, Any]:
        """
        Analyze a YouTube channel: fetch recent videos, get transcripts,
        and aggregate insights across all content.
        """
        videos = self.fetch_channel_videos(channel_url, max_videos=max_videos)
        if not videos:
            return {'error': 'Could not fetch channel videos'}

        results = []
        total_words = 0
        all_concepts = {}
        all_sentiments = {'bullish': 0, 'bearish': 0, 'neutral': 0}

        for video in videos:
            try:
                meta = self.fetch_video_metadata(video['url'])
                transcript = self.fetch_video_transcript(video['id'])
                analysis = self.analyze_transcript(transcript, meta)

                total_words += analysis.word_count
                for concept in analysis.key_concepts:
                    all_concepts[concept] = all_concepts.get(concept, 0) + 1
                all_sentiments[analysis.sentiment] += 1

                results.append({
                    'video_id': video['id'],
                    'title': video['title'],
                    'url': video['url'],
                    'analysis': {
                        'summary': analysis.summary,
                        'key_concepts': analysis.key_concepts,
                        'timestamps': analysis.timestamps,
                        'ict_relevance': analysis.ict_relevance,
                        'sentiment': analysis.sentiment,
                        'word_count': analysis.word_count,
                        'transcript_source': transcript.source,
                    },
                })
            except Exception as e:
                results.append({
                    'video_id': video['id'],
                    'title': video['title'],
                    'url': video['url'],
                    'error': str(e),
                })

        # Sort concepts by frequency
        top_concepts = sorted(all_concepts.items(), key=lambda x: x[1], reverse=True)
        dominant_sentiment = max(all_sentiments, key=all_sentiments.get)

        return {
            'channel_url': channel_url,
            'videos_analyzed': len(videos),
            'total_words': total_words,
            'top_concepts': top_concepts,
            'sentiment_distribution': all_sentiments,
            'dominant_sentiment': dominant_sentiment,
            'video_results': results,
        }

    # ────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────

    def _fetch_oembed_title(self, video_url: str) -> Optional[str]:
        try:
            endpoint = f"https://www.youtube.com/oembed?url={video_url}&format=json"
            response = self._http_client.get(endpoint, timeout=20)
            response.raise_for_status()
            data = response.json()
            title = data.get("title")
            if title:
                return title.strip()
        except Exception:
            return None
        return None

    @staticmethod
    def _parse_iso8601_duration(duration_str: str) -> int:
        """Parse ISO 8601 duration (PT1H30M15S) to seconds."""
        if not duration_str:
            return 0
        if duration_str.startswith('PT'):
            duration_str = duration_str[2:]
        total = 0
        # Extract hours, minutes, seconds
        h_match = re.search(r'(\d+)H', duration_str)
        m_match = re.search(r'(\d+)M', duration_str)
        s_match = re.search(r'(\d+)S', duration_str)
        if h_match:
            total += int(h_match.group(1)) * 3600
        if m_match:
            total += int(m_match.group(1)) * 60
        if s_match:
            total += int(s_match.group(1))
        return total


youtube_service = YouTubeService()
