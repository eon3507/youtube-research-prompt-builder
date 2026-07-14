import pytest
import transcripts as transcripts_module

from prompt_builder import PromptOptions, build_prompt
from transcripts import (
    TranscriptResult,
    build_transcript_pack,
    format_timestamp,
    normalize_segments,
    normalize_supadata_segments,
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
            "supadata-native",
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
    assert "Caption wording — verify against audio" in prompt
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


def test_supadata_segments_convert_milliseconds_and_preserve_text() -> None:
    segments = normalize_supadata_segments(
        [{"text": "A &amp; B", "offset": 65400, "duration": 2100, "lang": "en"}]
    )

    assert segments == ({"text": "A & B", "start": 65.4, "duration": 2.1},)


def test_fetch_transcript_uses_supadata_native_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {"text": "Exact line", "offset": 5000, "duration": 1000, "lang": "en"}
                ],
                "lang": "en",
                "availableLangs": ["en"],
            }

    def fake_supadata_get(api_key, params):
        captured["api_key"] = api_key
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr(transcripts_module, "_supadata_get", fake_supadata_get)

    result = transcripts_module.fetch_transcript(
        "abcdefghijk",
        ["en"],
        api_key="free-api-key",
    )

    assert captured["api_key"] == "free-api-key"
    assert captured["params"]["mode"] == "native"
    assert captured["params"]["text"] == "false"
    assert result.available
    assert result.source == "supadata-native"
    assert result.timestamped_text == "[00:05] Exact line"


def test_fetch_transcript_requires_supadata_api_key() -> None:
    result = transcripts_module.fetch_transcript("abcdefghijk", ["en"])

    assert not result.available
    assert result.reason == "Supadata API key is not configured"


def test_fetch_transcript_reports_free_limit(monkeypatch) -> None:
    class FakeResponse:
        status_code = 429

    monkeypatch.setattr(
        transcripts_module,
        "_supadata_get",
        lambda api_key, params: FakeResponse(),
    )

    result = transcripts_module.fetch_transcript(
        "abcdefghijk",
        ["en"],
        api_key="free-api-key",
    )

    assert not result.available
    assert "free transcript allowance" in result.reason
