# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

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
        "dump_single_json": False,
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
            return {"success": False, "error": "Unable to extract video information"}

        title = info.get("title")
        thumbnail = info.get("thumbnail")
        duration = float(info.get("duration", 0)) if info.get("duration") else None

        video_formats = []
        audio_formats = []

        seen_video = set()
        seen_audio = set()

        for f in info.get("formats", []):

            format_id = f.get("format_id")
            if not format_id:
                continue

            height = f.get("height")
            abr = f.get("abr")
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")

            # ----------------------------
            # VIDEO FORMATS
            # ----------------------------
            if height and vcodec != "none":
                quality = f"{height}p"
                if quality not in seen_video:
                    video_formats.append({
                        "format_id": format_id,
                        "ext": f.get("ext"),
                        "resolution": quality,
                        "height": height,
                        "fps": f.get("fps"),
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "filesize": f.get("filesize"),
                    })
                    seen_video.add(quality)

            # ----------------------------
            # AUDIO FORMATS
            # ----------------------------
            elif abr and acodec != "none":
                bitrate = f"{int(abr)}k"
                if bitrate not in seen_audio:
                    audio_formats.append({
                        "format_id": format_id,
                        "ext": f.get("ext"),
                        "audio_bitrate": bitrate,
                        "acodec": acodec,
                        "filesize": f.get("filesize"),
                    })
                    seen_audio.add(bitrate)

        # Sort formats: high → low
        video_formats.sort(key=lambda x: x["height"], reverse=True)
        audio_formats.sort(key=lambda x: int(x["audio_bitrate"].replace("k", "")), reverse=True)

        return {
            "success": True,
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "video_formats": video_formats,
            "audio_formats": audio_formats,
        }

    except DownloadError as e:
        return {"success": False, "error": str(e)}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# ----------------------------
# REQUEST MODEL
# ----------------------------
class ExtractRequest(BaseModel):
    url: str


# ----------------------------
# API ENDPOINT
# ----------------------------
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
        video_formats=info.get("video_formats"),
        audio_formats=info.get("audio_formats"),
    )
