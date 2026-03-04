import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import SessionLocal, Base, engine
from database.models import Download

from downloader.extractor import extract_info
from downloader.download import get_status, pause_task, resume_task
from celery_app import celery_app
from downloader.download import start_download  # fallback for local testing
from typing import Optional, List, Dict, Any
from pydantic import BaseModel



# Create DB tables if not exists
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Media Downloader Backend")


# -------------------------------------------------
# ROOT + HEALTH ROUTES (Prevents 404 on Render)
# -------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Media Downloader Backend is running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# -------------------------------------------------
# Pydantic models
# -------------------------------------------------

class ExtractResponse(BaseModel):
    title: str
    thumbnail: Optional[str]
    duration: Optional[float]   # ✅ FIXED
    formats: List[Dict[str, Any]]


class StartDownloadRequest(BaseModel):
    url: str
    format_id: str
    is_audio: bool = False
    audio_bitrate: str | None = "128k"


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# Endpoints
# -------------------------------------------------

@app.post("/extract", response_model=ExtractResponse)
def api_extract(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")
    info = extract_info(url)
    return info


@app.post("/download")
def api_download(req: StartDownloadRequest):
    task_id = str(uuid.uuid4())

    db: Session = next(get_db())
    d = Download(
        id=task_id,
        url=req.url,
        title="",
        format_id=req.format_id,
        is_audio=req.is_audio,
        audio_bitrate=req.audio_bitrate,
        status="queued",
        created_at=datetime.utcnow()
    )
    db.add(d)
    db.commit()
    db.close()

    # Submit Celery task
    try:
        celery_app.send_task(
            "downloader.download.start_download_task",
            args=[task_id, req.url, req.format_id, req.is_audio, req.audio_bitrate]
        )
    except Exception:
        # Local development fallback
        from concurrent.futures import ThreadPoolExecutor
        ThreadPoolExecutor(max_workers=1).submit(
            start_download,
            task_id,
            req.url,
            req.format_id,
            req.is_audio,
            req.audio_bitrate
        )

    return {"task_id": task_id}


@app.get("/status/{task_id}")
def api_status(task_id: str):
    status = get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@app.post("/pause/{task_id}")
def api_pause(task_id: str):
    ok = pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or cannot pause")
    return {"task_id": task_id, "paused": True}


@app.post("/resume/{task_id}")
def api_resume(task_id: str):
    ok = resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or cannot resume")
    return {"task_id": task_id, "resumed": ok}


@app.get("/history")
def api_history(limit: int = 50):
    db: Session = next(get_db())
    rows = db.query(Download).order_by(
        Download.created_at.desc()
    ).limit(limit).all()

    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "url": r.url,
            "title": r.title,
            "format_id": r.format_id,
            "status": r.status,
            "filepath": r.filepath,
            "created_at": r.created_at.isoformat()
        })

    db.close()
    return result


@app.get("/download/file/{task_id}")
def download_file(task_id: str):
    db: Session = next(get_db())
    row = db.query(Download).filter(
        Download.id == task_id
    ).first()
    db.close()

    if not row or not row.filepath or not os.path.exists(row.filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=row.filepath,
        filename=os.path.basename(row.filepath),
        media_type="application/octet-stream"
    )


# -------------------------------------------------
# Local CLI Run (ignored by Render)
# -------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("Starting uvicorn (dev) on http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

