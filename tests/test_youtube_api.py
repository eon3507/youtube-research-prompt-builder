from youtube_api import (
    Video,
    filter_videos,
    is_direct_channel_reference,
    parse_channel_reference,
    parse_duration,
    sort_videos,
)


def video(video_id: str, views: int, published: str, seconds: int) -> Video:
    return Video(video_id, video_id, f"https://youtu.be/{video_id}", published, views, seconds)


def test_parse_duration() -> None:
    assert parse_duration("PT1H2M3S") == 3723
    assert parse_duration("PT12M") == 720
    assert parse_duration("P1DT2S") == 86402


def test_parse_common_channel_references() -> None:
    assert parse_channel_reference("@example") == {"handle": "example"}
    assert parse_channel_reference("https://www.youtube.com/@example/videos") == {"handle": "example"}
    assert parse_channel_reference("https://youtube.com/channel/UC1234567890123456789012") == {
        "channel_id": "UC1234567890123456789012"
    }


def test_public_lookups_require_a_direct_channel_reference() -> None:
    assert is_direct_channel_reference("@example")
    assert is_direct_channel_reference("https://www.youtube.com/@example/videos")
    assert is_direct_channel_reference("UC1234567890123456789012")
    assert not is_direct_channel_reference("Example Channel")


def test_filter_and_sort_videos() -> None:
    videos = [
        video("old-long", 200, "2024-01-01T00:00:00Z", 500),
        video("new-long", 100, "2025-01-01T00:00:00Z", 600),
        video("short", 999, "2026-01-01T00:00:00Z", 60),
    ]
    assert [item.video_id for item in filter_videos(videos, "long")] == ["old-long", "new-long"]
    assert [item.video_id for item in filter_videos(videos, "shorts")] == ["short"]
    assert [item.video_id for item in sort_videos(videos, "views")] == ["short", "old-long", "new-long"]
    assert [item.video_id for item in sort_videos(videos, "newest")] == ["short", "new-long", "old-long"]
