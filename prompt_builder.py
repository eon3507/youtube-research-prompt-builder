"""Turn selected YouTube metadata into a single ChatGPT-ready research prompt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PromptOptions:
    channel_title: str
    sort_label: str
    content_label: str
    report_language: str = "English"
    focus: str = ""


def format_views(value: int) -> str:
    return f"{value:,}"


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def build_prompt(videos: list, options: PromptOptions) -> str:
    """Build a self-contained prompt that asks ChatGPT to inspect every video."""

    if not videos:
        raise ValueError("At least one video is required to build a prompt.")

    video_lines: list[str] = []
    for rank, video in enumerate(videos, start=1):
        published = video.published_at[:10] if video.published_at else "Unknown"
        video_lines.extend(
            [
                f"### {rank}. {video.title}",
                f"- URL: {video.url}",
                f"- Views at scan time: {format_views(video.views)}",
                f"- Published: {published}",
                f"- Duration: {format_duration(video.duration_seconds)}",
                "",
            ]
        )

    focus = options.focus.strip()
    focus_instruction = (
        f"\nMy special research focus is: {focus}\n"
        if focus
        else ""
    )

    return f"""# Video-by-video YouTube analysis

Analyze all {len(videos)} YouTube videos listed below from **{options.channel_title}** in **{options.report_language}**.

Your output must consist only of a repeated video-by-video sequence. Do not write a report introduction, executive synthesis, methodology section, channel-wide analysis, global takeaways, global nuggets, global quotes, verification ledger, conclusion, or appendix.

For each video, complete all three requested sections and then immediately move to the next video. Use the videos in the exact order listed. Do not group videos together.

The result is expected to be very long. Do not shorten later videos, reduce the number of insights, or compress the analysis because many videos are included. Give Video {len(videos)} the same care and depth as Video 1.

These videos were selected as: **{options.sort_label}**, content type **{options.content_label}**. The list was generated on {datetime.now().strftime('%Y-%m-%d')}.
{focus_instruction}
## Mandatory output template

Repeat this exact template for every video:

# Video 1 — [full video title]

**URL:** [clickable YouTube URL]

## Key takeaways

- Give all important actionable lessons from this video.
- Aim for at least 8 takeaways when the available source supports them.
- Explain every takeaway in detail: what it means, why it matters, who it is useful for, and how to apply it.
- Keep every takeaway specific to this video. Do not give generic one-line advice.

## Best nuggets

- Extract all high-value ideas, frameworks, tactics, stories, examples, mental models, and surprising observations from this video.
- Aim for at least 10 strong nuggets when the available source supports them.
- Give each nugget a short descriptive headline followed by a substantial explanation.
- Explain the supporting reasoning or example, why the nugget matters, and a practical use for it.
- Include a timestamp or timestamped link when available.

## Best quotes

- Include the strongest exact quotes supported by the video's transcript or captions.
- For every quote, give the speaker, timestamp or timestamped link when available, the context, and why the quote is valuable.
- Never invent or reconstruct a quote. If no exact transcript-supported quote is accessible, write: **No transcript-verified quotes were available for this video.**
- Do not put paraphrases inside quotation marks.

---

# Video 2 — [full video title]

**URL:** [clickable YouTube URL]

## Key takeaways

[Full takeaways for Video 2]

## Best nuggets

[Full nuggets for Video 2]

## Best quotes

[Verified quotes for Video 2]

---

Continue this identical sequence for Video 3, Video 4, and every remaining video through Video {len(videos)}.

## Non-negotiable rules

1. The first heading in the answer must be `# Video 1 — [title]`. Do not place anything before it.
2. After `## Best quotes` for one video, the next top-level heading must be the next numbered video. Do not insert any other report sections between videos.
3. Every video must contain exactly these section headings in exactly this order: `## Key takeaways`, `## Best nuggets`, `## Best quotes`.
4. Do not add separate summary, overview, detailed-summary, frameworks, critical-analysis, evidence, or verification sections. Put useful explanatory material inside Key takeaways or Best nuggets.
5. Use the actual video transcript/captions as the primary source. Do not infer content from the title alone.
6. If the transcript is inaccessible, use the best reliable episode-specific sources available, but do not pretend they are the transcript. Mention the limitation briefly inside Best quotes only when it affects quotation verification.
7. Never merge, skip, or reorder videos. The answer must contain exactly {len(videos)} top-level `# Video` headings.
8. Treat every video independently, even when ideas repeat across videos.
9. Do not optimize for brevity. Preserve useful details, examples, stories, and applications.
10. If a single document cannot contain the full result, continue in numbered parts without changing the template or shortening later videos. Resume with the next unfinished video and do not repeat completed videos.

## Videos

{chr(10).join(video_lines).rstrip()}
"""
