# downloader/extractor.py
from downloader.cache import get_cache, set_cache
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

        # ❌ REMOVE THESE
        # "skip_download": True,
        # "simulate": True,

        "extract_flat": False,  # IMPORTANT: full extraction

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
STANDARD_RESOLUTIONS = [144, 240, 360, 480, 720, 1080]

def extract_info(url: str) -> Dict[str, Any]:
    try:
        with YoutubeDL(get_ydl_options()) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("Extraction failed")

        title = info.get("title", "")
        thumbnail = info.get("thumbnail", "")
        duration = float(info.get("duration") or 0)

        yt_formats = info.get("formats", [])

        # --------------------------------
        # Map available formats
        # --------------------------------
        available = {}

        for f in yt_formats:
            h = f.get("height")
            if h and f.get("vcodec") != "none":
                available.setdefault(h, []).append(f.get("format_id"))

        # --------------------------------
        # FORCE GENERATE FORMATS
        # --------------------------------
        video_formats = []

        for res in STANDARD_RESOLUTIONS:

            format_id = None

            # Find best match ≥ requested
            for h in sorted(available.keys()):
                if h >= res:
                    format_id = available[h][0]
                    break

            video_formats.append({
                "resolution": f"{res}p",
                "height": res,
                "format_id": format_id,
                "generated": format_id is None,

                # VERY IMPORTANT (frontend uses this)
                "fallback": f"bestvideo[height<={res}]+bestaudio/best[height<={res}]/best"
            })

        # --------------------------------
        # AUDIO FORMATS
        # --------------------------------
        audio_formats = []

        for f in yt_formats:
            if f.get("acodec") != "none" and f.get("vcodec") == "none":
                audio_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "audio_bitrate": f.get("abr") or 0,
                    "fallback": "bestaudio/best"
                })

        # fallback audio if empty
        if not audio_formats:
            audio_formats.append({
                "format_id": None,
                "ext": "mp3",
                "audio_bitrate": 128,
                "fallback": "bestaudio/best",
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
