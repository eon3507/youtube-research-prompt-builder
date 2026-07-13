"""Small YouTube Data API client for channel discovery and video metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SHORTS_MAX_SECONDS = 180


class YouTubeError(RuntimeError):
    """A user-facing YouTube lookup failure."""


@dataclass(frozen=True)
class Channel:
    channel_id: str
    title: str
    uploads_playlist_id: str


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    url: str
    published_at: str
    views: int
    duration_seconds: int


def parse_duration(value: str) -> int:
    """Parse the subset of ISO 8601 durations returned by YouTube."""

    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value or "",
    )
    if not match:
        return 0
    return (
        int(match.group("days") or 0) * 86400
        + int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def parse_channel_reference(reference: str) -> dict[str, str]:
    value = reference.strip()
    if re.fullmatch(r"UC[A-Za-z0-9_-]{20,}", value):
        return {"channel_id": value}
    if value.startswith("@"):
        return {"handle": value[1:]}

    parsed = urlparse(value if "://" in value else f"https://{value}")
    parts = [part for part in parsed.path.split("/") if part]
    if parts[:1] == ["channel"] and len(parts) >= 2:
        return {"channel_id": parts[1]}
    if parts and parts[0].startswith("@"):
        return {"handle": parts[0][1:]}
    if parts[:1] == ["user"] and len(parts) >= 2:
        return {"username": parts[1]}
    if parts[:1] in (["c"], ["custom"]) and len(parts) >= 2:
        return {"query": parts[1]}
    if parsed.netloc and "youtube" in parsed.netloc.lower() and parts:
        return {"query": parts[-1]}
    return {"query": value}


def is_direct_channel_reference(reference: str) -> bool:
    """Return True when lookup can avoid YouTube's limited search endpoint."""

    parsed = parse_channel_reference(reference)
    return any(key in parsed for key in ("channel_id", "handle", "username"))


class YouTubeClient:
    def __init__(self, api_key: str) -> None:
        if not api_key.strip():
            raise YouTubeError("Add YOUTUBE_API_KEY to the .env file, then restart the app.")
        self.api = build("youtube", "v3", developerKey=api_key.strip(), cache_discovery=False)

    def _execute(self, request) -> dict:
        try:
            return request.execute()
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 403:
                raise YouTubeError(
                    "YouTube rejected the request. Check that the key is valid, YouTube Data API v3 is enabled, and its quota is available."
                ) from exc
            raise YouTubeError(f"YouTube request failed (HTTP {status or 'unknown'}).") from exc

    def resolve_channel(self, reference: str) -> Channel:
        parsed = parse_channel_reference(reference)
        if "channel_id" in parsed:
            channel_id = parsed["channel_id"]
        elif "handle" in parsed:
            response = self._execute(
                self.api.channels().list(part="id", forHandle=parsed["handle"], maxResults=1)
            )
            items = response.get("items", [])
            if not items:
                raise YouTubeError(f"No channel found for @{parsed['handle']}.")
            channel_id = items[0]["id"]
        elif "username" in parsed:
            response = self._execute(
                self.api.channels().list(part="id", forUsername=parsed["username"], maxResults=1)
            )
            items = response.get("items", [])
            if not items:
                raise YouTubeError(f"No channel found for {parsed['username']}.")
            channel_id = items[0]["id"]
        else:
            response = self._execute(
                self.api.search().list(
                    part="snippet", q=parsed["query"], type="channel", maxResults=1
                )
            )
            items = response.get("items", [])
            if not items:
                raise YouTubeError(f"No channel found for {parsed['query']}.")
            channel_id = items[0]["snippet"]["channelId"]

        response = self._execute(
            self.api.channels().list(
                part="snippet,contentDetails", id=channel_id, maxResults=1
            )
        )
        items = response.get("items", [])
        if not items:
            raise YouTubeError("The channel could not be opened.")
        item = items[0]
        return Channel(
            channel_id=channel_id,
            title=item.get("snippet", {}).get("title", "Untitled channel"),
            uploads_playlist_id=item["contentDetails"]["relatedPlaylists"]["uploads"],
        )

    def get_upload_ids(self, playlist_id: str) -> list[str]:
        ids: list[str] = []
        token: str | None = None
        while True:
            response = self._execute(
                self.api.playlistItems().list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=token,
                )
            )
            ids.extend(
                item["contentDetails"]["videoId"]
                for item in response.get("items", [])
                if item.get("contentDetails", {}).get("videoId")
            )
            token = response.get("nextPageToken")
            if not token:
                return ids

    def get_videos(self, video_ids: Iterable[str]) -> list[Video]:
        unique_ids = list(dict.fromkeys(video_ids))
        videos: list[Video] = []
        for start in range(0, len(unique_ids), 50):
            chunk = unique_ids[start : start + 50]
            response = self._execute(
                self.api.videos().list(
                    part="snippet,statistics,contentDetails,status",
                    id=",".join(chunk),
                    maxResults=50,
                )
            )
            for item in response.get("items", []):
                if item.get("status", {}).get("privacyStatus") != "public":
                    continue
                video_id = item["id"]
                snippet = item.get("snippet", {})
                videos.append(
                    Video(
                        video_id=video_id,
                        title=snippet.get("title", "Untitled video"),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        published_at=snippet.get("publishedAt", ""),
                        views=int(item.get("statistics", {}).get("viewCount", 0)),
                        duration_seconds=parse_duration(
                            item.get("contentDetails", {}).get("duration", "")
                        ),
                    )
                )
        return videos

    def scan_channel(self, reference: str) -> tuple[Channel, list[Video]]:
        channel = self.resolve_channel(reference)
        upload_ids = self.get_upload_ids(channel.uploads_playlist_id)
        return channel, self.get_videos(upload_ids)


def filter_videos(videos: list[Video], content_type: str) -> list[Video]:
    if content_type == "long":
        return [video for video in videos if video.duration_seconds > SHORTS_MAX_SECONDS]
    if content_type == "shorts":
        return [video for video in videos if 0 < video.duration_seconds <= SHORTS_MAX_SECONDS]
    return list(videos)


def sort_videos(videos: list[Video], order: str) -> list[Video]:
    if order == "newest":
        return sorted(videos, key=lambda video: video.published_at, reverse=True)
    return sorted(videos, key=lambda video: video.views, reverse=True)
