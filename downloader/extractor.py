# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# -----------------------------------
# Router
# -----------------------------------
router = APIRouter()

# -----------------------------------
# Constants
# -----------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "..", "cookies.txt")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "..", "downloads")

# -----------------------------------
# Response Model
# -----------------------------------
class FormatModel(BaseModel):
    format_id: Optional[str]
    ext: Optional[str]
    resolution: Optional[str]


class ExtractResponse(BaseModel):
    title: Optional[str]
    thumbnail: Optional[str]
    duration: Optional[float] = Field(
        None, description="Video duration in seconds (float)"
    )
    formats: Optional[List[FormatModel]]


# -----------------------------------
# YTDL Configuration
# -----------------------------------
def get_ydl_options(download: bool = False) -> Dict[str, Any]:
    """
    Returns yt-dlp configuration.
    Includes cookies.txt automatically if present.
    """

    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    # Add cookies if available
    if os.path.exists(COOKIES_PATH):
        ydl_opts["cookiefile"] = COOKIES_PATH

    if download:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        ydl_opts["outtmpl"] = os.path.join(
            DOWNLOADS_DIR, "%(title)s.%(ext)s"
        )

    return ydl_opts


# -----------------------------------
# Metadata Extraction
# -----------------------------------
def extract_info(url: str) -> Dict[str, Any]:
    """
    Extract metadata without downloading the video.
    """

    try:
        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {"success": False, "error": "No video information found"}

        # Force duration to float
        duration_value = info.get("duration")
        duration_float: Optional[float] = (
            float(duration_value) if duration_value else None
        )

        formats_list = [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution"),
            }
            for f in info.get("formats", [])
            if f.get("format_id")
        ]

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration_float,
            "formats": formats_list,
        }

    except DownloadError as e:
        return {"success": False, "error": f"DownloadError: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# -----------------------------------
# Download Function
# -----------------------------------
def download_video(url: str) -> Dict[str, Any]:
    """
    Download video to local downloads folder.
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
        return {"success": False, "error": f"DownloadError: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# -----------------------------------
# API Endpoint
# -----------------------------------
@router.post("/extract", response_model=ExtractResponse)
def api_extract(payload: Dict[str, Any]):

    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")

    info = extract_info(url)

    if not info.get("success"):
        raise HTTPException(
            status_code=400,
            detail=info.get("error", "Extraction failed"),
        )

    return ExtractResponse(
        title=info.get("title"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=info.get("formats"),
    )
