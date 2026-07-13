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

    video_blocks: list[str] = []
    for rank, video in enumerate(videos, start=1):
        published = video.published_at[:10] if video.published_at else "Unknown"
        video_blocks.append(
            f"""# Video {rank} — {video.title}

**URL:** {video.url}
**Published:** {published}
**Views at scan time:** {format_views(video.views)}
**Duration:** {format_duration(video.duration_seconds)}

## Key takeaways

[Write all important actionable lessons from Video {rank}. Aim for at least 8 when the source supports them. Explain what each takeaway means, why it matters, who it is useful for, and how to apply it. Keep every takeaway specific to this video.]

## Best nuggets

[Extract the strongest ideas, frameworks, tactics, stories, examples, mental models, and surprising observations from Video {rank}. Aim for at least 10 when the source supports them. Give each nugget a descriptive headline, a substantial explanation, the supporting reasoning or example, why it matters, and a practical use. Include a timestamp or timestamped link when available.]

## Best quotes

[Include the strongest exact transcript-supported quotes from Video {rank}. For every quote, give the speaker, timestamp or timestamped link when available, context, and why it is valuable. Never invent or reconstruct a quote. If no exact transcript-supported quote is accessible, write: **No transcript-verified quotes were available for this video.** Do not put paraphrases inside quotation marks.]"""
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
## Mandatory output structure

The complete structure is expanded below for all {len(videos)} videos. Research and replace every bracketed instruction with the requested analysis. Do not leave placeholders in the answer. Do not omit, merge, rename, or reorder any block.

## Non-negotiable rules

1. The first heading in the answer must be `# Video 1 — {videos[0].title}`. Do not place anything before it.
2. After `## Best quotes` for one video, the next top-level heading must be the next numbered video. Do not insert any other report sections between videos.
3. Every video must contain exactly these section headings in exactly this order: `## Key takeaways`, `## Best nuggets`, `## Best quotes`.
4. Do not add separate summary, overview, detailed-summary, frameworks, critical-analysis, evidence, or verification sections. Put useful explanatory material inside Key takeaways or Best nuggets.
5. Use the actual video transcript/captions as the primary source. Do not infer content from the title alone.
6. If the transcript is inaccessible, use the best reliable episode-specific sources available, but do not pretend they are the transcript. Mention the limitation briefly inside Best quotes only when it affects quotation verification.
7. Never merge, skip, or reorder videos. The answer must contain exactly {len(videos)} top-level `# Video` headings.
8. Treat every video independently, even when ideas repeat across videos.
9. Do not optimize for brevity. Preserve useful details, examples, stories, and applications.
10. If a single document cannot contain the full result, continue in numbered parts without changing the template or shortening later videos. Resume with the next unfinished video and do not repeat completed videos.

## Complete video-by-video answer skeleton

{f'{chr(10)}{chr(10)}---{chr(10)}{chr(10)}'.join(video_blocks)}
"""
