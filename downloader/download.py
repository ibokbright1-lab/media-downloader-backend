# downloader/download.py

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
# Paths
# ----------------------------
BASE_DIR = os.getcwd()
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ----------------------------
# In-memory control fallback
# ----------------------------
download_controls = {}

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
            update_db(
                task_id,
                status="downloading",
                progress_percent=percent,
                speed=str(speed),
                eta=str(eta),
            )
            ctrl = get_task_state(task_id) or {}
            if ctrl.get("paused"):
                raise yt_dlp.utils.DownloadError("Paused by user")
        elif status == "finished":
            filename = d.get("filename")
            update_db(task_id, status="processing", filepath=filename)
            delete_task_state(task_id)
    return hook

# ----------------------------
# Restart if paused too long
# ----------------------------
def ensure_fresh_or_restart(task_id):
    ctrl = get_task_state(task_id) or download_controls.get(task_id)
    if not ctrl:
        return
    paused_at = ctrl.get("paused_at")
    if not paused_at:
        return
    paused_at = datetime.fromisoformat(paused_at)
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
def convert_audio(input_path, out_path, bitrate):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-ab", bitrate, "-ar", "44100", "-ac", "2",
        out_path
    ]
    subprocess.run(cmd, check=True)

def scale_video(input_path, out_path, height):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        out_path
    ]
    subprocess.run(cmd, check=True)

# ----------------------------
# Build yt-dlp format string
# ----------------------------
def build_format_string(format_id: str, is_audio=False):
    if is_audio:
        return format_id or "bestaudio/best"
    return format_id or "bestvideo+bestaudio/best"

# ----------------------------
# Celery download task
# ----------------------------
@celery_app.task(bind=True, name="downloader.download.start_download_task")
def start_download_task(self, task_id, url, format_id=None, is_audio=False, audio_bitrate="128k"):
    set_task_state(task_id, {"paused": False, "paused_at": None})
    ensure_fresh_or_restart(task_id)

    out_template = os.path.join(DOWNLOADS_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "continuedl": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook_factory(task_id)],
        "format": safe_format_selector(format_id, fallback, is_audio),
        "merge_output_format": "mp4",
        "retries": 10,
        "concurrent_fragment_downloads": 5,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        "cookiefile": os.path.join(os.getcwd(), "cookies.txt") if os.path.exists("cookies.txt") else None,
    }

    update_db(task_id, status="started")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except Exception as e:
        if "paused by user" in str(e).lower():
            state = get_task_state(task_id) or {}
            state["paused"] = True
            state["paused_at"] = datetime.utcnow().isoformat()
            set_task_state(task_id, state)
            update_db(task_id, status="paused")
            return
        update_db(task_id, status="failed")
        return

    final_path = filename

    # ----------------------------
    # AUDIO CONVERSION
    # ----------------------------
    if is_audio:
        base, _ = os.path.splitext(final_path)
        mp3_path = base + ".mp3"
        try:
            convert_audio(final_path, mp3_path, audio_bitrate)
            os.remove(final_path)
            update_db(task_id, filepath=mp3_path, status="finished")
        except Exception:
            update_db(task_id, status="failed")
        return

    # ----------------------------
    # VIDEO SCALING / CREATE MISSING FORMAT
    # ----------------------------
    # Determine requested resolution from format_id
    target_height = None
    if format_id and format_id.lower().endswith("p"):
        try:
            target_height = int(format_id.lower().replace("p",""))
        except:
            pass

    if target_height:
        try:
            scaled_path = final_path.replace(".mp4", f"_{target_height}p.mp4")
            scale_video(final_path, scaled_path, target_height)
            os.remove(final_path)
            final_path = scaled_path
        except Exception:
            pass

    update_db(task_id, filepath=final_path, status="finished")

# ----------------------------
# Pause / Resume / Status
# ----------------------------
def pause_task(task_id: str):
    state = get_task_state(task_id) or download_controls.get(task_id)
    if not state:
        return False
    state["paused"] = True
    state["paused_at"] = datetime.utcnow().isoformat()
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
        args=[task_id, row.url, row.format_id, row.is_audio, row.audio_bitrate],
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
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
def safe_format_selector(format_id: str, fallback: str, is_audio=False):

    if is_audio:
        return format_id or "bestaudio/best"

    return (
        f"{format_id}+bestaudio/"
        f"{fallback}/"
        "best"
    )
# ----------------------------
# Local fallback
# ----------------------------
def start_download(task_id, url, format_id=None, is_audio=False, audio_bitrate="128k"):
    start_download_task(task_id, url, format_id, is_audio, audio_bitrate)
