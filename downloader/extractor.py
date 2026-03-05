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
# Paths
# -----------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

COOKIES_PATH = os.path.join(ROOT_DIR, "cookies.txt")
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")


# -----------------------------------
# Response Models
# -----------------------------------
class FormatModel(BaseModel):
    format_id: Optional[str]
    ext: Optional[str]
    resolution: Optional[str]
    filesize: Optional[int]


class ExtractResponse(BaseModel):
    title: Optional[str]
    thumbnail: Optional[str]
    duration: Optional[float] = Field(
        None,
        description="Video duration in seconds"
    )
    formats: Optional[List[FormatModel]]


# -----------------------------------
# YTDLP Options
# -----------------------------------
def get_ydl_options(download: bool = False) -> Dict[str, Any]:

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "skip_download": not download,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # Use cookies if present (important for YouTube)
    if os.path.exists(COOKIES_PATH):
        ydl_opts["cookiefile"] = COOKIES_PATH

    # Download settings
    if download:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)

        ydl_opts.update({
            "outtmpl": os.path.join(
                DOWNLOADS_DIR,
                "%(title).150s.%(ext)s"
            ),
            "merge_output_format": "mp4"
        })

    return ydl_opts


# -----------------------------------
# Metadata Extraction
# -----------------------------------
def extract_info(url: str) -> Dict[str, Any]:
    """
    Extract video metadata without downloading.
    """

    try:

        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {
                "success": False,
                "error": "No media information found"
            }

        # Convert duration to float
        duration_value = info.get("duration")
        duration: Optional[float] = None

        if duration_value:
            try:
                duration = float(duration_value)
            except Exception:
                duration = None

        formats: List[Dict[str, Any]] = []

        for f in info.get("formats", []):

            if not f.get("format_id"):
                continue

            ext = f.get("ext")

            # Allow common media formats
            if ext not in [
                "mp4",
                "webm",
                "m4a",
                "mp3",
                "aac",
                "opus"
            ]:
                continue

            formats.append({
                "format_id": f.get("format_id"),
                "ext": ext,
                "resolution": f.get("resolution")
                or f.get("format_note"),
                "filesize": f.get("filesize"),
            })

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration,
            "formats": formats
        }

    except DownloadError as e:

        return {
            "success": False,
            "error": f"DownloadError: {str(e)}"
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


# -----------------------------------
# Download Function
# -----------------------------------
def download_video(url: str) -> Dict[str, Any]:
    """
    Direct download helper (used only if needed).
    """

    try:

        with YoutubeDL(get_ydl_options(download=True)) as ydl:
            info = ydl.extract_info(url, download=True)

            file_path = ydl.prepare_filename(info)

        return {
            "success": True,
            "title": info.get("title"),
            "file_path": file_path
        }

    except DownloadError as e:

        return {
            "success": False,
            "error": f"DownloadError: {str(e)}"
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


# -----------------------------------
# API Endpoint
# -----------------------------------
@router.post("/extract", response_model=ExtractResponse)
def api_extract(payload: Dict[str, Any]):

    url = payload.get("url")

    if not url:
        raise HTTPException(
            status_code=400,
            detail="Missing url"
        )

    info = extract_info(url)

    if not info.get("success"):

        raise HTTPException(
            status_code=400,
            detail=info.get("error", "Extraction failed")
        )

    return ExtractResponse(
        title=info.get("title"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=info.get("formats")
    )
