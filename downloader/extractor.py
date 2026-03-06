# downloader/extractor.py

import os
from typing import Dict, Any, List, Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ExtractResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    formats: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


def get_ydl_options(download: bool = False) -> dict:

    ydl_opts = {
        "format": "best",
        "ignoreerrors": True,
        "extract_flat": False,
        "dump_single_json": True,
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

    cookie_path = os.path.join(os.getcwd(), "cookies.txt")

    if os.path.exists(cookie_path):
        ydl_opts["cookiefile"] = cookie_path

    if download:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts["outtmpl"] = "downloads/%(title)s.%(ext)s"

    return ydl_opts


def extract_info(url: str) -> Dict[str, Any]:

    try:
        with YoutubeDL(get_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {"success": False, "error": "No video information found"}

        duration = info.get("duration")

        if duration is not None:
            duration = float(duration)

        formats = []

        for f in info.get("formats", []):

            if not f.get("format_id"):
                continue

            formats.append(
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "height": f.get("height"),  # important for resolution matching
                    "fps": f.get("fps"),
                    "abr": f.get("abr"),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                }
            )

        return {
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": duration,
            "formats": formats,
        }

    except DownloadError as e:

        return {
            "success": False,
            "error": str(e)
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


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
