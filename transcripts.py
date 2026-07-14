"""Retrieve public YouTube transcripts and build a timestamped transcript pack."""

from __future__ import annotations

import html
import threading
import time
from dataclasses import dataclass
from typing import Iterable

import requests


SUPADATA_TRANSCRIPT_URL = "https://api.supadata.ai/v1/transcript"
SUPADATA_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_supadata_request_lock = threading.Lock()
_last_supadata_request_started = 0.0


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
        if self.source == "supadata-native":
            return "Existing YouTube captions via Supadata (manual/auto not identified)"
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


def normalize_supadata_segments(raw_segments: object) -> tuple[dict, ...]:
    """Convert Supadata's millisecond caption chunks to local second-based segments."""

    if not isinstance(raw_segments, list):
        return ()
    segments: list[dict] = []
    for segment in raw_segments:
        if not isinstance(segment, dict):
            continue
        text = html.unescape(str(segment.get("text", ""))).replace("\n", " ").strip()
        if text:
            segments.append(
                {
                    "text": text,
                    "start": float(segment.get("offset", 0) or 0) / 1000,
                    "duration": float(segment.get("duration", 0) or 0) / 1000,
                }
            )
    return tuple(segments)


def _supadata_get(api_key: str, params: dict[str, str]):
    """Serialize free-tier requests and keep them below Supadata's one-per-second limit."""

    global _last_supadata_request_started
    with _supadata_request_lock:
        wait_seconds = SUPADATA_MIN_REQUEST_INTERVAL_SECONDS - (
            time.monotonic() - _last_supadata_request_started
        )
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _last_supadata_request_started = time.monotonic()
        return requests.get(
            SUPADATA_TRANSCRIPT_URL,
            headers={"x-api-key": api_key},
            params=params,
            timeout=45,
        )


def fetch_transcript(
    video_id: str,
    languages: Iterable[str],
    *,
    api_key: str = "",
) -> TranscriptResult:
    """Fetch one existing YouTube caption track through Supadata native mode."""

    preferred = normalized_languages(languages)
    key = api_key.strip()
    if not key:
        return TranscriptResult(
            video_id,
            "unavailable",
            None,
            None,
            "",
            reason="Supadata API key is not configured",
        )

    try:
        response = _supadata_get(
            key,
            {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "lang": preferred[0],
                "text": "false",
                "mode": "native",
            },
        )
        error_reasons = {
            206: "No existing transcript is available",
            401: "Supadata API key is invalid",
            402: "Supadata free transcript allowance has been exhausted",
            403: "Video requires authentication or is restricted",
            404: "Video or transcript was not found",
            429: "Supadata free transcript allowance or rate limit has been reached",
        }
        if response.status_code == 202:
            return TranscriptResult(
                video_id,
                "unavailable",
                None,
                None,
                "",
                reason="Supadata queued the transcript unexpectedly; try again later",
            )
        if response.status_code != 200:
            return TranscriptResult(
                video_id,
                "unavailable",
                None,
                None,
                "",
                reason=error_reasons.get(
                    response.status_code,
                    f"Supadata transcript request failed (HTTP {response.status_code})",
                ),
            )

        payload = response.json()
        if payload.get("jobId"):
            return TranscriptResult(
                video_id,
                "unavailable",
                None,
                None,
                "",
                reason="Supadata queued the transcript unexpectedly; try again later",
            )
        segments = normalize_supadata_segments(payload.get("content"))
        if not segments:
            return TranscriptResult(
                video_id, "unavailable", None, None, "", reason="Transcript was empty"
            )

        timestamped_text = segments_to_timestamped_text(segments)

        return TranscriptResult(
            video_id=video_id,
            status="available",
            language=str(payload.get("lang") or preferred[0]),
            source="supadata-native",
            timestamped_text=timestamped_text,
            segment_count=len(segments),
        )
    except requests.Timeout:
        reason = "Supadata transcript request timed out"
    except requests.RequestException:
        reason = "Supadata transcript request failed"
    except (AttributeError, TypeError, ValueError):
        reason = "Supadata returned invalid transcript data"
    except Exception:
        reason = "Unexpected Supadata transcript error"

    return TranscriptResult(
        video_id=video_id,
        status="unavailable",
        language=None,
        source=None,
        timestamped_text="",
        reason=reason,
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
        "This file contains existing YouTube caption text retrieved through Supadata native mode.",
        "No AI transcript was generated. The caption track may be human-created or auto-generated.",
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
