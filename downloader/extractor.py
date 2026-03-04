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

def extract_info(url: str) -> Dict[str, Any]:
    """
    Extract metadata from a media URL without downloading.
    Ensures duration is a float to avoid FastAPI validation errors.
    """

    try:
        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        # Ensure duration is float (or None)
        duration = info.get("duration")
        if duration is not None:
            try:
                duration = float(duration)
            except Exception:
                duration = None

        # Prepare formats
        formats: List[Dict[str, Any]] = []
        for f in info.get("formats", []):
            if f.get("ext") in ["mp4", "webm", "m4a", "mp3"]:  # allow common media
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "tbr": f.get("tbr"),
                })

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration,
            "uploader": info.get("uploader"),
            "webpage_url": info.get("webpage_url"),
            "formats": formats,
        }

    except DownloadError as e:
        return {"success": False, "error": str(e)}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


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
