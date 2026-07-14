"""Turn selected YouTube metadata into a single ChatGPT-ready research prompt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from transcripts import TranscriptResult


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


def build_prompt(
    videos: list,
    options: PromptOptions,
    transcripts: dict[str, TranscriptResult],
    transcript_filename: str = "youtube_transcripts.md",
) -> str:
    """Build a transcript-only prompt for every selected video."""

    if not videos:
        raise ValueError("At least one video is required to build a prompt.")
    missing = [video.video_id for video in videos if not transcripts.get(video.video_id, None)]
    unavailable = [
        video.video_id
        for video in videos
        if video.video_id in transcripts and not transcripts[video.video_id].available
    ]
    if missing or unavailable:
        raise ValueError("Every video must have an available transcript before building the prompt.")

    video_blocks: list[str] = []
    for rank, video in enumerate(videos, start=1):
        published = video.published_at[:10] if video.published_at else "Unknown"
        transcript = transcripts[video.video_id]
        auto_caption_note = (
            " This source is automatically generated, so mark each quotation as "
            "`Auto-generated caption — verify against audio`."
            if transcript.source == "youtube-auto"
            else ""
        )
        video_blocks.append(
            f"""# Video {rank} — {video.title}

**URL:** {video.url}
**Published:** {published}
**Views at scan time:** {format_views(video.views)}
**Duration:** {format_duration(video.duration_seconds)}
**Transcript source:** {transcript.source_label}
**Transcript language:** {transcript.language or "Unknown"}

## Key takeaways

[Using only the Video {rank} transcript in `{transcript_filename}`, write all important actionable lessons. Aim for at least 8 when the transcript supports them. Explain what each takeaway means, why it matters, who it is useful for, and how to apply it. Keep every takeaway specific to this video.]

## Best nuggets

[Using only the Video {rank} transcript, extract the strongest ideas, frameworks, tactics, stories, examples, mental models, and surprising observations. Aim for at least 10 when the transcript supports them. Give each nugget a descriptive headline, substantial explanation, supporting reasoning or example, why it matters, and a practical use. Include the transcript timestamp.]

## Best quotes

[Quote only exact wording present in the Video {rank} transcript. For every quote, give the timestamp, context, and why it is valuable. Never invent, reconstruct, polish, or silently correct transcript wording. Do not place paraphrases inside quotation marks.{auto_caption_note}]"""
        )

    focus = options.focus.strip()
    focus_instruction = (
        f"\nMy special research focus is: {focus}\n"
        if focus
        else ""
    )

    return f"""# Video-by-video YouTube analysis

Analyze all {len(videos)} YouTube videos listed below from **{options.channel_title}** in **{options.report_language}** using the attached file **`{transcript_filename}`**.

The attached transcript pack is the required and exclusive evidence source for video content. It already contains a timestamped YouTube transcript for every listed video. Read the entire transcript section for each video before writing that video's analysis.

Do not search for, cite, or rely on Instagram, TikTok, X, Facebook, blogs, news articles, podcast directories, summaries, or any other external website. Do not infer content from titles, thumbnails, descriptions, or search snippets. You may use the YouTube URLs only as identifiers; all analytical claims and quotations must be supported by the attached transcripts.

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
5. Use only the timestamped transcript text in `{transcript_filename}` as evidence. External web sources are prohibited.
6. A transcript is supplied for every listed video. Do not claim that transcripts are unavailable and do not replace transcript evidence with third-party material.
7. Never merge, skip, or reorder videos. The answer must contain exactly {len(videos)} top-level `# Video` headings.
8. Treat every video independently, even when ideas repeat across videos.
9. Do not optimize for brevity. Preserve useful details, examples, stories, and applications.
10. If a single document cannot contain the full result, continue in numbered parts without changing the template or shortening later videos. Resume with the next unfinished video and do not repeat completed videos.
11. Treat wording from auto-generated captions as potentially imperfect. Preserve it exactly when quoting, show its timestamp, and label it `Auto-generated caption — verify against audio`.

## Complete video-by-video answer skeleton

{f'{chr(10)}{chr(10)}---{chr(10)}{chr(10)}'.join(video_blocks)}
"""
