from prompt_builder import PromptOptions, build_prompt
from youtube_api import Video


def test_prompt_contains_every_video_and_safety_rules() -> None:
    videos = [
        Video("abcdefghijk", "First video", "https://youtube.com/watch?v=abcdefghijk", "2026-01-02T00:00:00Z", 42, 605),
        Video("lmnopqrstuv", "Second video", "https://youtube.com/watch?v=lmnopqrstuv", "2026-01-03T00:00:00Z", 99, 1200),
    ]
    prompt = build_prompt(
        videos,
        PromptOptions("Example Channel", "most viewed", "long-form", focus="decision making"),
    )
    assert "Example Channel" in prompt
    assert "First video" in prompt and "Second video" in prompt
    assert "decision making" in prompt
    assert "Never invent or reconstruct a quote" in prompt
    assert "# Video 1 — [full video title]" in prompt
    assert "## Key takeaways" in prompt
    assert "## Best nuggets" in prompt
    assert "## Best quotes" in prompt
    assert prompt.index("## Key takeaways") < prompt.index("## Best nuggets") < prompt.index("## Best quotes")
    assert "Do not write a report introduction, executive synthesis" in prompt
    assert "exactly 2 top-level `# Video` headings" in prompt
    assert "No transcript-verified quotes were available for this video" in prompt
    assert "verification ledger" in prompt
    assert "42" in prompt and "99" in prompt
