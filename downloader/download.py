import os
import subprocess
from datetime import datetime, timedelta

import yt_dlp
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Download
from redis_client import set_task_state, get_task_state, delete_task_state
from celery_app import celery_app

# ----------------------------
# Folder paths
# ----------------------------
BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "media_downloader_backend")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ----------------------------
# In-memory fallback control
# ----------------------------
download_controls = {}  # task_id -> {"paused": False, "paused_at": None, "last_update": datetime}

# ----------------------------
# Database helper
# ----------------------------
def update_db(task_id: str, **kwargs):
    db: Session = SessionLocal()
    row = db.query(Download).filter(Download.id == task_id).first()
    if not row:
        db.close()
        return
    for k, v in kwargs.items():
        setattr(row, k, v)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.close()

# ----------------------------
# Progress hook
# ----------------------------
def progress_hook_factory(task_id):
    def hook(d):
        status = d.get("status")
        if status == "downloading":
            percent = d.get("_percent_str") or ""
            speed = d.get("_speed_str") or ""
            eta = d.get("_eta_str") or ""
            update_db(task_id, status="downloading", progress_percent=percent, speed=str(speed), eta=str(eta))
            # Check pause from Redis
            ctrl = get_task_state(task_id) or {}
            if ctrl.get("paused"):
                raise yt_dlp.utils.DownloadError("Paused by user")
        elif status == "finished":
            filename = d.get("filename")
            update_db(task_id, status="finished", filepath=filename)
            delete_task_state(task_id)
    return hook

# ----------------------------
# Fresh restart if paused > 2 hours
# ----------------------------
def ensure_fresh_or_restart(task_id):
    ctrl = get_task_state(task_id) or download_controls.get(task_id)
    if not ctrl:
        return
    paused_at = ctrl.get("paused_at")
    if not paused_at:
        return
    if datetime.utcnow() - paused_at > timedelta(hours=2):
        db = SessionLocal()
        row = db.query(Download).filter(Download.id == task_id).first()
        if row and row.filepath and os.path.exists(row.filepath):
            try:
                os.remove(row.filepath)
            except Exception:
                pass
        db.close()
        ctrl["paused"] = False
        ctrl["paused_at"] = None
        set_task_state(task_id, ctrl)

# ----------------------------
# FFmpeg helpers
# ----------------------------
def convert_audio_with_ffmpeg(input_path: str, out_path: str, bitrate: str = "128k"):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-ab", bitrate, "-ar", "44100", "-ac", "2",
        out_path
    ]
    subprocess.run(cmd, check=True)

def compress_video_with_ffmpeg(input_path: str, out_path: str, crf: int = 23, preset: str = "fast"):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libx264", "-crf", str(crf), "-preset", preset,
        "-acodec", "aac", "-b:a", "128k",
        out_path
    ]
    subprocess.run(cmd, check=True)

# ----------------------------
# Celery task
# ----------------------------
@celery_app.task(bind=True, name="downloader.download.start_download_task")
def start_download_task(self, task_id, url, format_id, is_audio=False, audio_bitrate="128k"):
    set_task_state(task_id, {"paused": False, "paused_at": None, "last_update": str(datetime.utcnow())})
    ensure_fresh_or_restart(task_id)

    out_template = os.path.join(DOWNLOADS_DIR, f"{task_id}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "continuedl": True,
        "noplaylist": True,
        "progress_hooks": [progress_hook_factory(task_id)],
        "quiet": True,
        "no_warnings": True,
        "format": format_id,
    }

    update_db(task_id, status="started")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        if "paused by user" in str(e).lower():
            state = get_task_state(task_id) or {}
            state["paused"] = True
            state["paused_at"] = str(datetime.utcnow())
            set_task_state(task_id, state)
            update_db(task_id, status="paused")
            return
        update_db(task_id, status="failed")
        return

    db = SessionLocal()
    row = db.query(Download).filter(Download.id == task_id).first()
    db.close()
    final_path = row.filepath if row else None

    if final_path and is_audio:
        base, _ = os.path.splitext(final_path)
        out_path = base + ".mp3"
        try:
            convert_audio_with_ffmpeg(final_path, out_path, bitrate=audio_bitrate or "128k")
            try:
                os.remove(final_path)
            except Exception:
                pass
            update_db(task_id, filepath=out_path, status="finished")
        except Exception:
            update_db(task_id, status="failed")
            return
    elif final_path:
        base, ext = os.path.splitext(final_path)
        compressed = base + ".compressed" + ext
        try:
            compress_video_with_ffmpeg(final_path, compressed, crf=23, preset="fast")
            try:
                if os.path.exists(compressed) and os.path.getsize(compressed) < os.path.getsize(final_path):
                    os.replace(compressed, final_path)
                else:
                    os.remove(compressed)
            except Exception:
                pass
            update_db(task_id, status="finished")
        except Exception:
            update_db(task_id, status="finished")
            return

# ----------------------------
# Pause / Resume / Status
# ----------------------------
def pause_task(task_id: str):
    state = get_task_state(task_id) or download_controls.get(task_id)
    if not state:
        return False
    state["paused"] = True
    state["paused_at"] = str(datetime.utcnow())
    set_task_state(task_id, state)
    return True

def resume_task(task_id: str):
    state = get_task_state(task_id) or download_controls.get(task_id)
    if not state:
        return False
    state["paused"] = False
    state["paused_at"] = None
    set_task_state(task_id, state)

    db = SessionLocal()
    row = db.query(Download).filter(Download.id == task_id).first()
    db.close()
    if not row:
        return False

    celery_app.send_task(
        "downloader.download.start_download_task",
        args=[task_id, row.url, row.format_id, row.is_audio, row.audio_bitrate]
    )
    return True

def get_status(task_id: str):
    db = SessionLocal()
    row = db.query(Download).filter(Download.id == task_id).first()
    db.close()
    if not row:
        return None
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "format_id": row.format_id,
        "status": row.status,
        "filepath": row.filepath,
        "progress": row.progress_percent,
        "speed": row.speed,
        "eta": row.eta,
        "created_at": row.created_at.isoformat() if row.created_at else None
    }

# ----------------------------
# Local fallback for main.py imports
# ----------------------------
def start_download(task_id, url, format_id, is_audio=False, audio_bitrate="128k"):
    """
    Fallback start_download for local testing (so main.py can import it)
    Calls the Celery task directly
    """
    start_download_task(task_id, url, format_id, is_audio, audio_bitrate)
