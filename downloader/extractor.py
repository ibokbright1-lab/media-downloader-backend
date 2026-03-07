# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional

from yt_dlp import YoutubeDL
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ----------------------------
# API RESPONSE MODEL
# ----------------------------
class ExtractResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    video_formats: Optional[List[Dict[str, Any]]] = None
    audio_formats: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


# ----------------------------
# REQUEST MODEL
# ----------------------------
class ExtractRequest(BaseModel):
    url: str


# ----------------------------
# yt-dlp options
# ----------------------------
def get_ydl_options(download: bool = False) -> dict:
    ydl_opts = {
        "ignoreerrors": True,
        "extract_flat": False,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "dump_single_json": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    cookie_path = os.path.join(os.getcwd(), "cookies.txt")
    if os.path.exists(cookie_path):
        ydl_opts["cookiefile"] = cookie_path

    if download:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts["outtmpl"] = "downloads/%(title)s.%(ext)s"

    return ydl_opts


# ----------------------------
# Extract video information
# ----------------------------
def extract_info(url: str) -> Dict[str, Any]:
    try:
        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {
                "success": False,
                "title": "",
                "thumbnail": "",
                "duration": 0,
                "video_formats": [],
                "audio_formats": [],
                "error": "Unable to extract video information",
            }

        title = info.get("title", "")
        thumbnail = info.get("thumbnail", "")
        duration = float(info.get("duration") or 0)

        video_formats = []
        audio_formats = []

        for f in info.get("formats", []):
            format_id = f.get("format_id")
            if not format_id:
                continue

            # Video formats
            if f.get("vcodec") != "none":
                video_formats.append({
                    "format_id": format_id,
                    "ext": f.get("ext", ""),
                    "resolution": f.get("height") or 0,
                    "height": f.get("height") or 0,
                    "fps": f.get("fps") or 0,
                    "filesize": f.get("filesize") or 0,
                    "vcodec": f.get("vcodec", ""),
                    "acodec": f.get("acodec", ""),
                })

            # Audio formats
            if f.get("acodec") != "none":
                audio_formats.append({
                    "format_id": format_id,
                    "ext": f.get("ext", ""),
                    "audio_bitrate": f.get("abr") or 0,
                    "filesize": f.get("filesize") or 0,
                    "vcodec": f.get("vcodec", ""),
                    "acodec": f.get("acodec", ""),
                })

        return {
            "success": True,
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "video_formats": video_formats or [],
            "audio_formats": audio_formats or [],
        }

    except Exception as e:
        return {
            "success": False,
            "title": "",
            "thumbnail": "",
            "duration": 0,
            "video_formats": [],
            "audio_formats": [],
            "error": str(e) or "Unexpected error",
        }


# ----------------------------
# API ENDPOINT
# ----------------------------
@router.post("/extract", response_model=ExtractResponse)
def api_extract(payload: ExtractRequest):
    if not payload.url:
        raise HTTPException(status_code=400, detail="Missing url")

    info = extract_info(payload.url)

    return ExtractResponse(
        success=info.get("success", False),
        title=info.get("title"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        video_formats=info.get("video_formats") or [],
        audio_formats=info.get("audio_formats") or [],
        error=info.get("error"),
    )
