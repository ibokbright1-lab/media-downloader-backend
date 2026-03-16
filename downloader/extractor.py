# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional

from yt_dlp import YoutubeDL
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Standard resolutions we always expose to frontend
STANDARD_RESOLUTIONS = [144, 240, 360, 480, 720, 1080]


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
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "simulate": True,
        "extract_flat": False,
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
            raise Exception("Extraction failed")

        title = info.get("title", "")
        thumbnail = info.get("thumbnail", "")
        duration = float(info.get("duration") or 0)

        yt_formats = info.get("formats", [])

        # --------------------------------
        # Collect all available formats by resolution
        # --------------------------------
        available_resolutions = {}

        for f in yt_formats:

            height = f.get("height")

            # Skip invalid entries
            if not height:
                continue

            if f.get("vcodec") == "none":
                continue

            if height not in available_resolutions:
                available_resolutions[height] = []

            available_resolutions[height].append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "filesize": f.get("filesize") or 0,
                "fps": f.get("fps") or 0
            })

        # --------------------------------
        # Normalize to standard resolutions
        # --------------------------------
        video_formats = []

        sorted_heights = sorted(available_resolutions.keys())

        for res in STANDARD_RESOLUTIONS:

            selected_format_id = None

            for h in sorted_heights:
                if h >= res:
                    selected_format_id = available_resolutions[h][0]["format_id"]
                    break

            video_formats.append({
                "resolution": f"{res}p",
                "height": res,
                "format_id": selected_format_id,
                "generated": selected_format_id is None
            })

        # --------------------------------
        # Audio formats
        # --------------------------------
        audio_formats = []

        for f in yt_formats:

            if f.get("acodec") != "none" and f.get("vcodec") == "none":

                audio_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "audio_bitrate": f.get("abr") or 0
                })

        # --------------------------------
        # FORCE fallback if formats missing
        # --------------------------------
        if not video_formats:

            video_formats = []

            for res in STANDARD_RESOLUTIONS:
                video_formats.append({
                    "resolution": f"{res}p",
                    "height": res,
                    "format_id": None,
                    "generated": True
                })

        return {
            "success": True,
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "video_formats": video_formats,
            "audio_formats": audio_formats
        }

    except Exception as e:

        return {
            "success": False,
            "title": "",
            "thumbnail": "",
            "duration": 0,
            "video_formats": [],
            "audio_formats": [],
            "error": str(e)
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
