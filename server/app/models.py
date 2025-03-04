from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum

class SubtitleFormat(str, Enum):
    vtt = "vtt"
    srt = "srt"
    json = "json"

class TranscriptionSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: Optional[List[Dict[str, Any]]] = None

class TranscriptionRequest(BaseModel):
    language: Optional[str] = None
    task: str = "transcribe"
    format: SubtitleFormat = SubtitleFormat.vtt

class TranscriptionResponse(BaseModel):
    success: bool
    message: str
    segments: List[TranscriptionSegment] = []
    subtitle_file: Optional[str] = None

class WebSocketMessage(BaseModel):
    type: str
    data: Any 