# extractor.py

import os
from typing import Dict, Any, List
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# ---------------------------------------------------
# YTDL Configuration
# ---------------------------------------------------

def get_ydl_options(download: bool = False) -> Dict[str, Any]:
    """
    Returns yt-dlp configuration options.
    """
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # Use cookies file if it exists
    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    # Enable download mode
    if download:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts["outtmpl"] = "downloads/%(title)s.%(ext)s"

    return ydl_opts


# ---------------------------------------------------
# Metadata Extraction
# ---------------------------------------------------

@app.post("/extract", response_model=ExtractResponse)
def api_extract(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")

    info = extract_info(url)

    # If extraction failed, return optional fields as None
    if not info.get("success"):
        return ExtractResponse(
            title=None,
            thumbnail=None,
            duration=None,
            formats=None
        )

    return ExtractResponse(
        title=info.get("title"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=info.get("formats")
    )

# ---------------------------------------------------
# Download Function
# ---------------------------------------------------

def download_video(url: str) -> Dict[str, Any]:
    """
    Download video to server.
    """
    try:
        with YoutubeDL(get_ydl_options(download=True)) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        return {
            "success": True,
            "title": info.get("title"),
            "file_path": file_path,
        }

    except DownloadError as e:
        return {"success": False, "error": str(e)}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

