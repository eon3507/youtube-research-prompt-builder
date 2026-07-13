# YouTube Research Prompt Builder

This is a separate companion to the original **YouTube Channel Nuggets** project. It scans a YouTube channel, selects any number of the most-viewed or newest videos, and builds one high-quality prompt to paste into ChatGPT.

It does **not** call Gemini, OpenAI, or any other language-model API. The only API call is to YouTube for public channel/video metadata.

## Recommended workflow

1. Double-click `start_app.bat`.
2. On first launch, the app creates `.env` and opens it in Notepad.
3. Paste your YouTube Data API v3 key after `YOUTUBE_API_KEY=` and save.
4. Double-click `start_app.bat` again.
5. Paste a channel URL or `@handle`.
6. Choose **Most viewed** or **Newest**, the content type, and the number of videos.
7. Scan the channel, review the selected list, and copy the generated prompt.
8. Paste it into ChatGPT. For 10-15 videos, use **Deep research** when it is available because this is a multi-source research task.

The prompt asks ChatGPT to process the videos one by one in a strict repeating sequence: **Video → Key takeaways → Best nuggets → Best quotes**, followed immediately by the next video. It forbids executive summaries, channel-wide sections, verification ledgers, and other material that would take space away from the per-video analysis. It explicitly allows a very long, multi-part result and forbids progressively shortening later videos.

For public deployments, the app accepts direct channel URLs, `@handles`, usernames, and channel IDs instead of free-text channel-name searches. Recent results are cached for six hours and each browser session is limited to ten scans per fifteen minutes to protect the shared YouTube API quota.

## Why use the YouTube API instead of a cheap LLM?

Channel discovery, view counts, publish dates, and durations are structured data. A language model adds cost and uncertainty without improving this step. YouTube Data API v3 is the most reliable source for the selection stage.

The app obtains the upload playlist and requests metadata in groups of 50, so even channels with many uploads are relatively quota-efficient. Resolving a plain channel name can cost more quota than using a channel URL or `@handle`, so a URL or handle is recommended.

## Important limitation

The app hands ChatGPT links, not transcript text. Whether ChatGPT can open every video/transcript depends on web access, YouTube availability, account features, region restrictions, and the size of the task. The prompt therefore includes a verification ledger.

If one-prompt accuracy is not good enough for a particular channel, the stronger fallback is to export transcripts from the old project and upload those transcript files to ChatGPT. That gives the model the source material directly while still avoiding low-quality API summarization.

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
- `prompt_builder.py` — the consolidated research prompt
- `start_app.bat` — first-time setup and launcher
