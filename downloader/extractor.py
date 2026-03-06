# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# -------------------------------
# Router
# -------------------------------
router = APIRouter()

# -------------------------------
# Response Model
# -------------------------------
class ExtractResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    formats: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


# -------------------------------
# YTDL Configuration (Forgiving)
# -------------------------------
def get_ydl_options(download: bool = False) -> dict:
    """
    Returns yt-dlp options. If download=True, will set output template.
    Aggressive and forgiving extraction to avoid 'No video information found'.
    """
    ydl_opts = {
        "format": "best",             # Try to get the best quality available
        "ignoreerrors": True,          # Ignore missing formats
        "extract_flat": False,         # Ensure yt-dlp fully inspects the URL
        "dump_single_json": True,      # Force JSON metadata output
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "nocheckcertificate": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # Use cookies if available
    cookie_path = os.path.join(os.getcwd(), "cookies.txt")
    if os.path.exists(cookie_path):
        ydl_opts["cookiefile"] = cookie_path

    if download:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts["outtmpl"] = "downloads/%(title)s.%(ext)s"

    return ydl_opts


# -------------------------------
# Metadata Extraction
# -------------------------------
def extract_info(url: str) -> Dict[str, Any]:
    """
    Extract metadata without downloading.
    Supports YouTube, Facebook, Instagram, TikTok.
    """
    try:
        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {"success": False, "error": "No video information found"}

        duration = info.get("duration")
        if duration is not None:
            duration = float(duration)

        formats = [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution"),
                "fps": f.get("fps"),
                "abr": f.get("abr"),      # audio bitrate
                "filesize": f.get("filesize"),
            }
            for f in info.get("formats", [])
            if f.get("format_id")
        ]

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration,
            "formats": formats,
        }

    except DownloadError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# -------------------------------
# API Endpoint
# -------------------------------
class ExtractRequest(BaseModel):
    url: str


@router.post("/extract", response_model=ExtractResponse)
def api_extract(payload: ExtractRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="Missing url")

    info = extract_info(payload.url)

    if not info.get("success"):
        return ExtractResponse(success=False, error=info.get("error"))

    return ExtractResponse(
        success=True,
        title=info.get("title"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=info.get("formats"),
    )
