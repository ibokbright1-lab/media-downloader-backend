from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.sql import func
from database.db import Base

class Download(Base):
    __tablename__ = "downloads"

    id = Column(String, primary_key=True, index=True)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    format_id = Column(String, nullable=True)
    is_audio = Column(Boolean, default=False)
    audio_bitrate = Column(String, nullable=True)
    status = Column(String, default="queued")  # queued, started, downloading, paused, finished, failed
    filepath = Column(Text, nullable=True)
    progress_percent = Column(String, nullable=True)
    speed = Column(String, nullable=True)
    eta = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
