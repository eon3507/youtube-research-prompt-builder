"""Retrieve public YouTube transcripts and build a timestamped transcript pack."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Iterable

from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi


@dataclass(frozen=True)
class TranscriptResult:
    video_id: str
    status: str
    language: str | None
    source: str | None
    timestamped_text: str
    segment_count: int = 0
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "available" and bool(self.timestamped_text.strip())

    @property
    def source_label(self) -> str:
        if self.source == "youtube-manual":
            return "YouTube human-created captions"
        if self.source == "youtube-auto":
            return "YouTube auto-generated captions"
        return self.source or "Unknown transcript source"


def normalized_languages(languages: Iterable[str]) -> list[str]:
    result: list[str] = []
    for language in languages:
        value = str(language).strip().lower().replace("_", "-")
        if value and value not in result:
            result.append(value)
    return result or ["en"]


def normalize_segments(raw_segments: Iterable[object]) -> tuple[dict, ...]:
    segments: list[dict] = []
    for segment in raw_segments:
        if isinstance(segment, dict):
            text_value = segment.get("text", "")
            start_value = segment.get("start", 0.0)
            duration_value = segment.get("duration", 0.0)
        else:
            text_value = getattr(segment, "text", "")
            start_value = getattr(segment, "start", 0.0)
            duration_value = getattr(segment, "duration", 0.0)

        text = html.unescape(str(text_value)).replace("\n", " ").strip()
        if text:
            segments.append(
                {
                    "text": text,
                    "start": float(start_value or 0.0),
                    "duration": float(duration_value or 0.0),
                }
            )
    return tuple(segments)


def segments_to_timestamped_text(segments: Iterable[dict]) -> str:
    return "\n".join(
        f"[{format_timestamp(segment['start'])}] {segment['text']}"
        for segment in segments
    )


def fetch_transcript(video_id: str, languages: Iterable[str]) -> TranscriptResult:
    """Fetch the best public YouTube transcript without translating its wording."""

    preferred = normalized_languages(languages)
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        transcript = None
        source = None

        attempts = [
            ("youtube-manual", lambda: transcript_list.find_manually_created_transcript(preferred)),
            ("youtube-auto", lambda: transcript_list.find_generated_transcript(preferred)),
        ]
        if "en" not in preferred:
            attempts.extend(
                [
                    ("youtube-manual", lambda: transcript_list.find_manually_created_transcript(["en"])),
                    ("youtube-auto", lambda: transcript_list.find_generated_transcript(["en"])),
                ]
            )

        for candidate_source, finder in attempts:
            try:
                transcript = finder()
                source = candidate_source
                break
            except NoTranscriptFound:
                continue

        if transcript is None:
            for candidate in transcript_list:
                transcript = candidate
                source = (
                    "youtube-auto"
                    if bool(getattr(candidate, "is_generated", False))
                    else "youtube-manual"
                )
                break

        if transcript is None:
            return TranscriptResult(
                video_id, "unavailable", None, None, "", reason="No transcript found"
            )

        fetched = transcript.fetch()
        if hasattr(fetched, "to_raw_data"):
            fetched = fetched.to_raw_data()
        segments = normalize_segments(fetched)
        if not segments:
            return TranscriptResult(
                video_id, "unavailable", None, None, "", reason="Transcript was empty"
            )

        timestamped_text = segments_to_timestamped_text(segments)

        return TranscriptResult(
            video_id=video_id,
            status="available",
            language=getattr(transcript, "language_code", None),
            source=source,
            timestamped_text=timestamped_text,
            segment_count=len(segments),
        )
    except Exception as exc:  # YouTube exposes several changing transcript error classes.
        error_name = type(exc).__name__
        friendly_reasons = {
            "TranscriptsDisabled": "Captions are disabled",
            "NoTranscriptFound": "No accessible transcript found",
            "VideoUnavailable": "Video is unavailable",
            "AgeRestricted": "Video is age restricted",
            "RequestBlocked": "YouTube blocked transcript access from this server",
            "IpBlocked": "YouTube blocked transcript access from this server",
            "PoTokenRequired": "YouTube requires additional playback verification",
        }
        return TranscriptResult(
            video_id=video_id,
            status="unavailable",
            language=None,
            source=None,
            timestamped_text="",
            reason=friendly_reasons.get(error_name, f"Transcript retrieval failed ({error_name})"),
        )


def format_timestamp(seconds: float | int | None) -> str:
    total = int(seconds or 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_transcript_pack(videos: list, transcripts: dict[str, TranscriptResult]) -> str:
    """Create one Markdown file containing every selected timestamped transcript."""

    blocks: list[str] = [
        "# YouTube transcript pack",
        "",
        "This file contains transcript text retrieved directly from YouTube captions.",
        "Human-created captions are preferred. Auto-generated captions may contain recognition errors.",
        "",
    ]
    for rank, video in enumerate(videos, start=1):
        transcript = transcripts[video.video_id]
        blocks.extend(
            [
                f"## Video {rank} — {video.title}",
                "",
                f"- Video ID: {video.video_id}",
                f"- URL: {video.url}",
                f"- Transcript source: {transcript.source_label}",
                f"- Transcript language: {transcript.language or 'Unknown'}",
                "",
                "### Timestamped transcript",
                "",
            ]
        )
        blocks.append(transcript.timestamped_text)
        blocks.extend(["", "---", ""])
    return "\n".join(blocks).rstrip() + "\n"
