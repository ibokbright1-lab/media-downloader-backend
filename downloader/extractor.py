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
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

COOKIES_PATH = os.path.join(PROJECT_ROOT, "cookies.txt")
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, "downloads")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

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
        None, description="Video duration in seconds"
    )
    formats: Optional[List[FormatModel]]


# -----------------------------------
# YTDL Configuration
# -----------------------------------
def get_ydl_options(download: bool = False) -> Dict[str, Any]:

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "best",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        ),
    }

    # --------------------------
    # LOAD COOKIES (IMPORTANT)
    # --------------------------
    if os.path.exists(COOKIES_PATH):
        ydl_opts["cookiefile"] = COOKIES_PATH

    # --------------------------
    # DOWNLOAD SETTINGS
    # --------------------------
    if download:
        ydl_opts.update(
            {
                "outtmpl": os.path.join(DOWNLOADS_DIR, "%(title)s.%(ext)s"),
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "concurrent_fragment_downloads": 5,
            }
        )

    return ydl_opts


# -----------------------------------
# Metadata Extraction
# -----------------------------------
def extract_info(url: str) -> Dict[str, Any]:

    try:

        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {"success": False, "error": "No video information found"}

        # --------------------------
        # Fix duration type
        # --------------------------
        duration = info.get("duration")
        duration_float = float(duration) if duration else None

        formats_list = []

        # --------------------------
        # Filter usable formats
        # --------------------------
        for f in info.get("formats", []):

            if not f.get("format_id"):
                continue

            if not f.get("ext"):
                continue

            filesize = f.get("filesize") or f.get("filesize_approx")

            formats_list.append(
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution")
                    or f"{f.get('height')}p"
                    if f.get("height")
                    else None,
                    "filesize": filesize,
                }
            )

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration_float,
            "formats": formats_list,
        }

    except DownloadError as e:
        return {"success": False, "error": f"yt-dlp error: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# -----------------------------------
# Download Function
# -----------------------------------
def download_video(url: str) -> Dict[str, Any]:

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
        return {"success": False, "error": f"yt-dlp error: {str(e)}"}

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
