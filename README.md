# YouTube Research Prompt Builder

This is a separate companion to the original **YouTube Channel Nuggets** project. It scans a YouTube channel, selects the most-viewed or newest videos, retrieves their timestamped YouTube captions, and builds a transcript-only research package for ChatGPT.

It does **not** call Gemini, OpenAI, or any other language-model API. It uses YouTube Data API v3 for channel/video metadata and `youtube-transcript-api` for publicly accessible YouTube captions.

## Recommended workflow

1. Double-click `start_app.bat`.
2. On first launch, the app creates `.env` and opens it in Notepad.
3. Paste your YouTube Data API v3 key after `YOUTUBE_API_KEY=` and save.
4. Double-click `start_app.bat` again.
5. Paste a channel URL or `@handle`.
6. Choose **Most viewed** or **Newest**, the content type, and the number of videos.
7. Scan the channel and click **Fetch YouTube transcripts and prepare files**.
8. Download `youtube_transcripts.md`.
9. Start a new ChatGPT Deep Research conversation and attach the transcript file.
10. Restrict research sources to uploaded files when that option is available.
11. Paste the generated prompt directly into the message box and send it. Do not upload the prompt itself as a file.

The prompt asks ChatGPT to process the videos one by one in a strict repeating sequence: **Video → Key takeaways → Best nuggets → Best quotes**, followed immediately by the next video. It prohibits Instagram, blogs, summaries, and other external sources. Video-specific claims and quotes must come only from the timestamped transcript pack.

For public deployments, the app accepts direct channel URLs, `@handles`, usernames, and channel IDs instead of free-text channel-name searches. Metadata scans and compact transcript text are cached for six hours, and each browser session is rate limited. If a selected video has no accessible transcript, the app checks later videos in the chosen order until it reaches the requested count or its safety limit.

## Why use the YouTube API instead of a cheap LLM?

Channel discovery, view counts, publish dates, and durations are structured data. A language model adds cost and uncertainty without improving this step. YouTube Data API v3 is the most reliable source for the selection stage.

The app obtains the upload playlist and requests metadata in groups of 50, so even channels with many uploads are relatively quota-efficient. Resolving a plain channel name can cost more quota than using a channel URL or `@handle`, so a URL or handle is recommended.

## Transcript accuracy and limitations

The transcript library retrieves caption data from YouTube but is not YouTube's official caption-download API. YouTube can change or block this access, particularly from shared cloud-hosting IP addresses. Videos with disabled, restricted, or unavailable captions are skipped rather than replaced with third-party websites.

Human-created captions are preferred. YouTube auto-generated captions are used when necessary and are clearly labelled because speech-recognition errors are possible. Quotes from auto-generated captions should be checked against the linked video at the supplied timestamp before publication or other high-stakes use.

Large transcript packs and detailed reports can exceed practical model context or output limits. When that occurs, request fewer videos per package or ask ChatGPT to continue from the next unfinished video without shortening later entries.

## Manual setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

## Project files

- `app.py` — the interface
- `youtube_api.py` — channel scanning and video selection metadata
- `transcripts.py` — YouTube caption retrieval and timestamped transcript-pack generation
- `prompt_builder.py` — the consolidated research prompt
- `start_app.bat` — first-time setup and launcher
