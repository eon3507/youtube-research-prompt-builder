"""Streamlit interface for the YouTube-to-ChatGPT prompt builder."""

from __future__ import annotations

import csv
import io
import os
import time

import streamlit as st
from dotenv import load_dotenv

from prompt_builder import PromptOptions, build_prompt, format_duration, format_views
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

st.set_page_config(page_title="YouTube Research Prompt Builder", page_icon="▶️", layout="wide")


def videos_to_csv(videos: list) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["rank", "title", "url", "views", "published", "duration"])
    for rank, video in enumerate(videos, start=1):
        writer.writerow(
            [
                rank,
                video.title,
                video.url,
                video.views,
                video.published_at[:10],
                format_duration(video.duration_seconds),
            ]
        )
    return stream.getvalue()


def clear_scan() -> None:
    for key in ("channel", "all_videos", "scan_reference"):
        st.session_state.pop(key, None)


@st.cache_data(ttl=6 * 60 * 60, max_entries=250, show_spinner=False)
def scan_channel_cached(reference: str, _api_key: str):
    """Share recent channel scans across visitors to protect API quota."""

    return YouTubeClient(_api_key).scan_channel(reference)


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


st.title("YouTube → GPT Research Prompt")
st.caption(
    "Find a channel's strongest or newest videos and create one exhaustive, video-by-video "
    "research prompt to paste into ChatGPT. No language-model API is used."
)
st.caption("Public-use protection: recent scans are cached and each browser session is rate limited.")

with st.sidebar:
    st.header("Selection")
    order_label = st.radio("Order videos by", ["Most viewed", "Newest"], index=0)
    content_label = st.radio("Include", ["Long-form", "Shorts", "All videos"], index=0)
    count = st.number_input("Number of videos", min_value=1, max_value=100, value=15, step=1)
    report_language = st.text_input("Report language", value="English")
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
    scan_clicked = st.button("Scan channel", type="primary", use_container_width=True)
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
    selected = eligible[: int(count)]

    st.subheader(channel.title)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Public uploads found", format_views(len(all_videos)))
    metric_cols[1].metric(f"Matching {content_label.lower()}", format_views(len(eligible)))
    metric_cols[2].metric("Selected for prompt", format_views(len(selected)))

    if not selected:
        st.warning("No videos match this content filter. Try All videos.")
    else:
        rows = [
            {
                "#": rank,
                "Title": video.title,
                "Views": format_views(video.views),
                "Published": video.published_at[:10],
                "Duration": format_duration(video.duration_seconds),
                "URL": video.url,
            }
            for rank, video in enumerate(selected, start=1)
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)

        options = PromptOptions(
            channel_title=channel.title,
            sort_label=order_label.lower(),
            content_label=content_label.lower(),
            report_language=report_language.strip() or "English",
            focus=focus,
        )
        prompt = build_prompt(selected, options)

        st.subheader("Your copy-and-paste prompt")
        st.info(
            "This prompt requests a full chapter for every video, so the result may be extremely long. "
            "Use ChatGPT's Deep research mode when available and confirm that every numbered video was completed."
        )
        st.code(prompt, language=None, line_numbers=False)

        download_col1, download_col2 = st.columns(2)
        download_col1.download_button(
            "Download prompt (.txt)",
            data=prompt,
            file_name="youtube_research_prompt.txt",
            mime="text/plain",
            use_container_width=True,
        )
        download_col2.download_button(
            "Download selected videos (.csv)",
            data=videos_to_csv(selected),
            file_name="selected_youtube_videos.csv",
            mime="text/csv",
            use_container_width=True,
        )
