import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.db import SessionLocal, Base, engine
from database.models import Download
from celery_app import celery_app

# Import extractor router and function
from downloader.extractor import router as extractor_router, extract_info
from downloader.download import get_status, pause_task, resume_task, start_download

# -----------------------------------
# Database Setup
# -----------------------------------
Base.metadata.create_all(bind=engine)

# -----------------------------------
# FastAPI App
# -----------------------------------
app = FastAPI(
    title="Media Downloader Backend",
    version="1.0.3",
)

# Include extractor routes
app.include_router(extractor_router)

# -----------------------------------
# Dependency - DB Session
# -----------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------
# Pydantic Models
# -----------------------------------
class StartDownloadRequest(BaseModel):
    url: str
    is_audio: bool = False
    format_id: Optional[str] = None
    fallback: Optional[str] = None   # ✅ NEW
    audio_bitrate: Optional[str] = "128k"
# -----------------------------------
# Root & Health
# -----------------------------------
@app.get("/")
def root():
    return {
        "message": "Media Downloader Backend is running",
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------------
# Get available formats (NEW)
# -----------------------------------
@app.get("/formats")
def api_formats(url: str):
    """
    Returns available audio and video formats for a given URL.
    Frontend can use this to display options to the user before download.
    """
    info = extract_info(url)
    if not info.get("success"):
        raise HTTPException(status_code=400, detail=info.get("error"))

    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "video_formats": info.get("video_formats"),
        "audio_formats": info.get("audio_formats"),
    }

# -----------------------------------
# Start Download (updated)
# -----------------------------------
@app.post("/download")
def api_download(req: StartDownloadRequest, db: Session = Depends(get_db)):

    task_id = str(uuid.uuid4())

    # Store the download request in DB
    new_download = Download(
        id=task_id,
        url=req.url,
        title="",
        format_id=req.format_id,  # store exact format selected
        is_audio=req.is_audio,
        audio_bitrate=req.audio_bitrate,
        status="queued",
        created_at=datetime.utcnow(),
    )

    db.add(new_download)
    db.commit()

    # Start download using Celery or local fallback
    try:
        celery_app.send_task(
            "downloader.download.start_download_task",
            args=[task_id, req.url, req.format_id, req.fallback, req.is_audio, req.audio_bitrate]
        )
    except Exception:
        from concurrent.futures import ThreadPoolExecutor
        ThreadPoolExecutor(max_workers=1).submit(
            start_download,
            task_id,
            req.url,
            req.format_id,
            req.is_audio,
            req.audio_bitrate,
        )

    return {"task_id": task_id}

# -----------------------------------
# Task Status
# -----------------------------------
@app.get("/status/{task_id}")
def api_status(task_id: str):
    status = get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

# -----------------------------------
# Pause Task
# -----------------------------------
@app.post("/pause/{task_id}")
def api_pause(task_id: str):
    ok = pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or cannot pause")
    return {"task_id": task_id, "paused": True}

# -----------------------------------
# Resume Task
# -----------------------------------
@app.post("/resume/{task_id}")
def api_resume(task_id: str):
    ok = resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or cannot resume")
    return {"task_id": task_id, "resumed": True}

# -----------------------------------
# Download History
# -----------------------------------
@app.get("/history")
def api_history(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Download).order_by(Download.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "url": r.url,
            "title": r.title,
            "format_id": r.format_id,
            "status": r.status,
            "filepath": r.filepath,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

# -----------------------------------
# Download File
# -----------------------------------
@app.get("/download/file/{task_id}")
def download_file(task_id: str, db: Session = Depends(get_db)):
    row = db.query(Download).filter(Download.id == task_id).first()
    if not row or not row.filepath:
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.exists(row.filepath):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        path=row.filepath,
        filename=os.path.basename(row.filepath),
        media_type="application/octet-stream",
    )

# -----------------------------------
# Dev Run
# -----------------------------------
if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
