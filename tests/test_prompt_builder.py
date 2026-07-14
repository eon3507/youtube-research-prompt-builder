import pytest

from prompt_builder import PromptOptions, build_prompt
from transcripts import (
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
    skeleton = prompt.split("## Complete video-by-video answer skeleton", 1)[1]
    assert skeleton.index("## Key takeaways") < skeleton.index("## Best nuggets") < skeleton.index("## Best quotes")
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
