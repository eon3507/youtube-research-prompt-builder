"""Streamlit interface for the YouTube-to-ChatGPT prompt builder."""

from __future__ import annotations

import csv
import io
import os
import time

import streamlit as st
from dotenv import load_dotenv

from prompt_builder import PromptOptions, build_prompt, format_duration, format_views
from transcripts import TranscriptResult, build_transcript_pack, fetch_transcript, normalized_languages
from youtube_api import (
    YouTubeClient,
    YouTubeError,
    filter_videos,
    is_direct_channel_reference,
    sort_videos,
)


load_dotenv()

SCAN_WINDOW_SECONDS = 15 * 60
MAX_SCANS_PER_WINDOW = 10
MAX_TRANSCRIPT_PREPARATIONS_PER_WINDOW = 5

st.set_page_config(page_title="YouTube Research Prompt Builder", page_icon="▶️", layout="wide")


def videos_to_csv(videos: list, transcripts: dict[str, TranscriptResult] | None = None) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "rank",
            "title",
            "url",
            "views",
            "published",
            "duration",
            "transcript_source",
            "transcript_language",
        ]
    )
    for rank, video in enumerate(videos, start=1):
        transcript = (transcripts or {}).get(video.video_id)
        writer.writerow(
            [
                rank,
                video.title,
                video.url,
                video.views,
                video.published_at[:10],
                format_duration(video.duration_seconds),
                transcript.source_label if transcript else "",
                transcript.language if transcript else "",
            ]
        )
    return stream.getvalue()


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def videos_to_markdown(videos: list) -> str:
    lines = [
        "| # | Title | Views | Published | Duration | Link |",
        "|---:|---|---:|---|---:|---|",
    ]
    for rank, video in enumerate(videos, start=1):
        lines.append(
            "| {rank} | {title} | {views} | {published} | {duration} | [Open video]({url}) |".format(
                rank=rank,
                title=markdown_cell(video.title),
                views=format_views(video.views),
                published=video.published_at[:10],
                duration=format_duration(video.duration_seconds),
                url=video.url,
            )
        )
    return "\n".join(lines)


def failures_to_markdown(failures: list[dict[str, str]]) -> str:
    lines = ["| Title | Reason | Link |", "|---|---|---|"]
    for failure in failures:
        lines.append(
            f"| {markdown_cell(failure['Title'])} | {markdown_cell(failure['Reason'])} | "
            f"[Open video]({failure['URL']}) |"
        )
    return "\n".join(lines)


def clear_scan() -> None:
    for key in (
        "channel",
        "all_videos",
        "scan_reference",
        "transcript_fingerprint",
        "transcript_videos",
        "transcript_results",
        "transcript_failures",
    ):
        st.session_state.pop(key, None)


@st.cache_data(ttl=6 * 60 * 60, max_entries=250, show_spinner=False)
def scan_channel_cached(reference: str, _api_key: str):
    """Share recent channel scans across visitors to protect API quota."""

    return YouTubeClient(_api_key).scan_channel(reference)


@st.cache_data(ttl=6 * 60 * 60, max_entries=300, show_spinner=False)
def fetch_transcript_cached(video_id: str, languages: tuple[str, ...]) -> TranscriptResult:
    """Reuse transcript results across visitors and repeated channel scans."""

    return fetch_transcript(video_id, languages)


def register_scan_attempt() -> bool:
    """Apply a small per-session limit for accidental or automated repeat scans."""

    now = time.time()
    recent = [
        timestamp
        for timestamp in st.session_state.get("scan_times", [])
        if now - timestamp < SCAN_WINDOW_SECONDS
    ]
    if len(recent) >= MAX_SCANS_PER_WINDOW:
        st.session_state.scan_times = recent
        return False
    st.session_state.scan_times = [*recent, now]
    return True


def register_transcript_attempt() -> bool:
    """Limit expensive transcript preparation runs in each browser session."""

    now = time.time()
    recent = [
        timestamp
        for timestamp in st.session_state.get("transcript_times", [])
        if now - timestamp < SCAN_WINDOW_SECONDS
    ]
    if len(recent) >= MAX_TRANSCRIPT_PREPARATIONS_PER_WINDOW:
        st.session_state.transcript_times = recent
        return False
    st.session_state.transcript_times = [*recent, now]
    return True


st.title("YouTube → GPT Research Prompt")
st.caption(
    "Find a channel's strongest or newest videos, retrieve timestamped YouTube transcripts, "
    "and create a transcript-only research package for ChatGPT. No language-model API is used."
)
st.caption("Video metadata and transcript results are cached, and each browser session is rate limited.")

with st.sidebar:
    st.header("Selection")
    order_label = st.radio("Order videos by", ["Most viewed", "Newest"], index=0)
    content_label = st.radio("Include", ["Long-form", "Shorts", "All videos"], index=0)
    count = st.number_input("Number of videos", min_value=1, max_value=25, value=15, step=1)
    report_language = st.text_input("Report language", value="English")
    transcript_languages_text = st.text_input(
        "Preferred transcript languages",
        value="en, tr",
        help="Use comma-separated YouTube language codes. Human-created captions are preferred.",
    )
    focus = st.text_area(
        "Optional research focus",
        placeholder="Example: business strategy, persuasion techniques, and practical experiments",
        height=100,
    )
    st.divider()
    st.caption("Long-form means over 3 minutes; Shorts means 3 minutes or less.")

reference = st.text_input(
    "YouTube channel URL, @handle, or channel ID",
    placeholder="https://www.youtube.com/@channel or @channel",
)

scan_col, reset_col = st.columns([1, 5])
with scan_col:
    scan_clicked = st.button("Scan channel", type="primary", width="stretch")
with reset_col:
    st.button("Clear", on_click=clear_scan)

if scan_clicked:
    if not reference.strip():
        st.warning("Paste a YouTube channel URL or @handle first.")
    elif not is_direct_channel_reference(reference):
        st.warning(
            "For public quota protection, use the channel's URL, @handle, or UC… channel ID "
            "instead of a channel name."
        )
    elif not register_scan_attempt():
        st.warning("This browser has reached the temporary scan limit. Please try again in 15 minutes.")
    else:
        try:
            with st.spinner("Scanning the channel and collecting video statistics…"):
                channel, videos = scan_channel_cached(
                    reference.strip(), os.getenv("YOUTUBE_API_KEY", "")
                )
            st.session_state.channel = channel
            st.session_state.all_videos = videos
            st.session_state.scan_reference = reference
            for key in (
                "transcript_fingerprint",
                "transcript_videos",
                "transcript_results",
                "transcript_failures",
            ):
                st.session_state.pop(key, None)
        except YouTubeError as exc:
            st.error(str(exc))
        except Exception:
            st.error("The channel scan failed unexpectedly. Check the channel URL and try again.")

if "channel" in st.session_state and "all_videos" in st.session_state:
    channel = st.session_state.channel
    all_videos = st.session_state.all_videos
    order = "newest" if order_label == "Newest" else "views"
    content_type = {"Long-form": "long", "Shorts": "shorts", "All videos": "all"}[content_label]
    eligible = sort_videos(filter_videos(all_videos, content_type), order)
    requested_count = int(count)
    preview = eligible[:requested_count]
    transcript_languages = tuple(
        normalized_languages(transcript_languages_text.split(","))
    )
    fingerprint = (
        channel.channel_id,
        order,
        content_type,
        requested_count,
        transcript_languages,
    )

    st.subheader(channel.title)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Public uploads found", format_views(len(all_videos)))
    metric_cols[1].metric(f"Matching {content_label.lower()}", format_views(len(eligible)))
    metric_cols[2].metric("Requested transcripts", format_views(min(requested_count, len(eligible))))

    if not preview:
        st.warning("No videos match this content filter. Try All videos.")
    else:
        st.markdown(videos_to_markdown(preview))

        st.caption(
            "The app will try additional videos in the selected order when an earlier video has no accessible transcript."
        )
        prepare_clicked = st.button(
            "Fetch YouTube transcripts and prepare files",
            type="primary",
            width="stretch",
        )

        if prepare_clicked:
            if not register_transcript_attempt():
                st.warning(
                    "This browser has reached the temporary transcript preparation limit. "
                    "Please try again in 15 minutes."
                )
            else:
                max_candidates = min(
                    len(eligible),
                    max(requested_count * 2, requested_count + 10),
                    50,
                )
                transcript_videos: list = []
                transcript_results: dict[str, TranscriptResult] = {}
                transcript_failures: list[dict[str, str]] = []
                progress = st.progress(0, text="Checking YouTube transcripts…")

                for index, video in enumerate(eligible[:max_candidates]):
                    result = fetch_transcript_cached(video.video_id, transcript_languages)
                    if result.available:
                        transcript_videos.append(video)
                        transcript_results[video.video_id] = result
                    else:
                        transcript_failures.append(
                            {
                                "Title": video.title,
                                "URL": video.url,
                                "Reason": result.reason or "Transcript unavailable",
                            }
                        )
                    progress.progress(
                        min((index + 1) / max_candidates, 1.0),
                        text=f"Checked {index + 1} video(s); found {len(transcript_videos)} transcript(s)…",
                    )
                    if len(transcript_videos) >= requested_count:
                        break

                progress.empty()
                st.session_state.transcript_fingerprint = fingerprint
                st.session_state.transcript_videos = transcript_videos
                st.session_state.transcript_results = transcript_results
                st.session_state.transcript_failures = transcript_failures

        results_are_current = (
            st.session_state.get("transcript_fingerprint") == fingerprint
            and "transcript_videos" in st.session_state
        )
        if results_are_current:
            transcript_videos = st.session_state.transcript_videos
            transcript_results = st.session_state.transcript_results
            transcript_failures = st.session_state.transcript_failures

            result_metrics = st.columns(3)
            result_metrics[0].metric("Transcript-ready videos", len(transcript_videos))
            result_metrics[1].metric("Unavailable candidates", len(transcript_failures))
            result_metrics[2].metric(
                "Auto-generated transcripts",
                sum(
                    result.source == "youtube-auto"
                    for result in transcript_results.values()
                ),
            )

            if transcript_failures:
                with st.expander("Videos skipped because a transcript was unavailable"):
                    st.markdown(failures_to_markdown(transcript_failures))

            if not transcript_videos:
                st.error(
                    "No accessible YouTube transcripts were retrieved. YouTube may have disabled captions "
                    "or blocked transcript requests from this hosting server."
                )
            else:
                if len(transcript_videos) < requested_count:
                    st.warning(
                        f"Only {len(transcript_videos)} transcript-ready videos were found after checking "
                        f"{len(transcript_videos) + len(transcript_failures)} candidates."
                    )

                options = PromptOptions(
                    channel_title=channel.title,
                    sort_label=order_label.lower(),
                    content_label=content_label.lower(),
                    report_language=report_language.strip() or "English",
                    focus=focus,
                )
                transcript_pack = build_transcript_pack(transcript_videos, transcript_results)
                prompt = build_prompt(transcript_videos, options, transcript_results)

                st.subheader("Transcript-only ChatGPT package")
                st.success(
                    "Every video in this package has a timestamped YouTube transcript. "
                    "The prompt prohibits Instagram, blogs, summaries, and other external sources."
                )
                st.markdown(
                    "**How to use it:** Download `youtube_transcripts.md`. In a new ChatGPT Deep Research "
                    "conversation, attach that file, restrict research sources to uploaded files when the option "
                    "is available, paste the prompt below directly into the message box, and send it. "
                    "Do not upload the prompt itself as a file."
                )

                download_col1, download_col2, download_col3 = st.columns(3)
                download_col1.download_button(
                    "1. Download transcript pack",
                    data=transcript_pack,
                    file_name="youtube_transcripts.md",
                    mime="text/markdown",
                    width="stretch",
                )
                download_col2.download_button(
                    "Download prompt (.txt)",
                    data=prompt,
                    file_name="youtube_research_prompt.txt",
                    mime="text/plain",
                    width="stretch",
                )
                download_col3.download_button(
                    "Download video list (.csv)",
                    data=videos_to_csv(transcript_videos, transcript_results),
                    file_name="selected_youtube_videos.csv",
                    mime="text/csv",
                    width="stretch",
                )

                st.subheader("2. Copy this prompt into ChatGPT")
                st.info(
                    "The requested report can be extremely long. If ChatGPT reaches its output limit, "
                    "ask it to continue with the next unfinished video without shortening later videos."
                )
                st.code(prompt, language=None, line_numbers=False)
