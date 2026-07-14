import pytest
import transcripts as transcripts_module

from prompt_builder import PromptOptions, build_prompt
from transcripts import (
    _CaptionHTMLParser,
    TranscriptResult,
    build_transcript_pack,
    format_timestamp,
    normalize_segments,
    segments_to_timestamped_text,
)
from youtube_api import Video


def test_prompt_contains_every_video_and_safety_rules() -> None:
    videos = [
        Video("abcdefghijk", "First video", "https://youtube.com/watch?v=abcdefghijk", "2026-01-02T00:00:00Z", 42, 605),
        Video("lmnopqrstuv", "Second video", "https://youtube.com/watch?v=lmnopqrstuv", "2026-01-03T00:00:00Z", 99, 1200),
    ]
    transcripts = {
        "abcdefghijk": TranscriptResult(
            "abcdefghijk",
            "available",
            "en",
            "youtube-manual",
            "[00:05] First exact line",
            1,
        ),
        "lmnopqrstuv": TranscriptResult(
            "lmnopqrstuv",
            "available",
            "en",
            "youtube-auto",
            "[01:05] Second exact line",
            1,
        ),
    }
    prompt = build_prompt(
        videos,
        PromptOptions("Example Channel", "most viewed", "long-form", focus="decision making"),
        transcripts,
    )
    assert "Example Channel" in prompt
    assert "First video" in prompt and "Second video" in prompt
    assert "decision making" in prompt
    assert "Never invent, reconstruct, polish" in prompt
    assert "# Video 1 — First video" in prompt
    assert "# Video 2 — Second video" in prompt
    assert "Continue this identical sequence" not in prompt
    assert "Do not leave placeholders in the answer" in prompt
    assert prompt.splitlines().count("## Key takeaways") == 2
    assert prompt.splitlines().count("## Best nuggets") == 2
    assert prompt.splitlines().count("## Best quotes") == 2
    assert "## Key takeaways" in prompt
    assert "## Best nuggets" in prompt
    assert "## Best quotes" in prompt
    assert "extract 6 to 10" in prompt
    assert "write 3 to 7" in prompt
    assert "Every nugget must be supported by the transcript" in prompt
    assert "Every takeaway must be supported by the transcript" in prompt
    skeleton = prompt.split("## Complete video-by-video answer skeleton", 1)[1]
    assert skeleton.index("## Best nuggets") < skeleton.index("## Best quotes") < skeleton.index("## Key takeaways")
    assert "label it" not in prompt
    assert "Do not write a report introduction, executive synthesis" in prompt
    assert "exactly 2 top-level `# Video` headings" in prompt
    assert "youtube_transcripts.md" in prompt
    assert "External web sources are prohibited" in prompt
    assert "Instagram" in prompt
    assert "Auto-generated caption — verify against audio" in prompt
    assert "verification ledger" in prompt
    assert "42" in prompt and "99" in prompt


def test_transcript_pack_preserves_source_text_and_timestamps() -> None:
    videos = [
        Video("abcdefghijk", "First video", "https://youtube.com/watch?v=abcdefghijk", "", 42, 605)
    ]
    segments = normalize_segments([{"text": "A &amp; B", "start": 65.4, "duration": 2}])
    transcript = TranscriptResult(
        "abcdefghijk",
        "available",
        "en",
        "youtube-manual",
        segments_to_timestamped_text(segments),
        len(segments),
    )
    pack = build_transcript_pack(videos, {"abcdefghijk": transcript})
    assert "YouTube human-created captions" in pack
    assert "[01:05] A & B" in pack
    assert format_timestamp(3661) == "01:01:01"


def test_prompt_rejects_videos_without_transcripts() -> None:
    videos = [Video("abcdefghijk", "Missing", "https://youtu.be/abcdefghijk", "", 1, 60)]
    with pytest.raises(ValueError, match="available transcript"):
        build_prompt(videos, PromptOptions("Channel", "newest", "all"), {})


def test_caption_parser_avoids_native_xml_and_preserves_text() -> None:
    parser = _CaptionHTMLParser()
    parser.feed(
        '<transcript><text start="65.4" dur="2.1">A &amp; <i>B</i></text></transcript>'
    )
    parser.close()
    assert parser.segments == [
        {"text": "A & B", "start": 65.4, "duration": 2.1}
    ]


def test_fetch_transcript_uses_webshare_residential_proxy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeTranscript:
        language_code = "en"

    class FakeTranscriptList:
        def find_manually_created_transcript(self, languages):
            assert languages == ["en"]
            return FakeTranscript()

    class FakeYouTubeTranscriptApi:
        def __init__(self, proxy_config=None):
            captured["proxy_config"] = proxy_config

        def list(self, video_id):
            assert video_id == "abcdefghijk"
            return FakeTranscriptList()

    monkeypatch.setattr(
        transcripts_module,
        "YouTubeTranscriptApi",
        FakeYouTubeTranscriptApi,
    )
    monkeypatch.setattr(
        transcripts_module,
        "fetch_caption_segments_without_elementtree",
        lambda transcript: ({"text": "Exact line", "start": 5.0, "duration": 1.0},),
    )

    result = transcripts_module.fetch_transcript(
        "abcdefghijk",
        ["en"],
        proxy_username="proxy-user",
        proxy_password="proxy-password",
    )

    proxy_config = captured["proxy_config"]
    assert proxy_config.__class__.__name__ == "WebshareProxyConfig"
    assert "proxy-user-rotate" in proxy_config.to_requests_dict()["https"]
    assert result.available
    assert result.timestamped_text == "[00:05] Exact line"


def test_fetch_transcript_rejects_incomplete_proxy_credentials() -> None:
    result = transcripts_module.fetch_transcript(
        "abcdefghijk",
        ["en"],
        proxy_username="proxy-user",
    )

    assert not result.available
    assert result.reason == "Residential proxy credentials are incomplete"
