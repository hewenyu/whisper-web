from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import tempfile
import asyncio
import logging
from typing import List, Dict, Optional
import uuid
import json
import time

from .transcription import WhisperTranscriber
from .models import TranscriptionRequest, TranscriptionResponse, SubtitleFormat

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper Web API",
    description="API for transcribing audio/video using faster-whisper",
    version="0.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化转录器
transcriber = WhisperTranscriber()

# 存储活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Whisper Web API")
    # 确保临时目录存在
    os.makedirs("temp", exist_ok=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Whisper Web API")
    # 清理临时文件
    for file in os.listdir("temp"):
        try:
            os.remove(os.path.join("temp", file))
        except Exception as e:
            logger.error(f"Error removing temp file: {e}")

@app.get("/")
async def root():
    return {"message": "Welcome to Whisper Web API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_file(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    task: str = "transcribe",
    format: SubtitleFormat = SubtitleFormat.vtt
):
    """
    上传音频或视频文件进行转录
    """
    try:
        # 保存上传的文件到临时目录
        temp_file_path = os.path.join("temp", f"{uuid.uuid4()}_{file.filename}")
        with open(temp_file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 执行转录
        result = await transcriber.transcribe_file(
            file_path=temp_file_path,
            language=language,
            task=task
        )
        
        # 生成字幕文件
        subtitle_path = transcriber.generate_subtitles(result, format)
        
        # 清理临时文件
        os.remove(temp_file_path)
        
        return {
            "success": True,
            "message": "Transcription completed successfully",
            "segments": result,
            "subtitle_file": subtitle_path
        }
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.websocket("/ws/transcribe/{client_id}")
async def websocket_transcribe(websocket: WebSocket, client_id: str):
    """
    WebSocket端点，用于实时音频流转录
    """
    await websocket.accept()
    active_connections[client_id] = websocket
    
    try:
        # 创建临时文件用于存储音频数据
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
            
        audio_data = b""
        
        while True:
            # 接收音频数据
            data = await websocket.receive_bytes()
            
            if data == b"END_OF_AUDIO":
                # 音频传输结束，执行转录
                with open(temp_path, "wb") as f:
                    f.write(audio_data)
                
                # 执行转录
                result = await transcriber.transcribe_file(
                    file_path=temp_path,
                    language=None,
                    task="transcribe"
                )
                
                # 发送结果
                await websocket.send_json({
                    "type": "final_result",
                    "segments": result
                })
                
                # 清理
                audio_data = b""
                os.remove(temp_path)
            else:
                # 累积音频数据
                audio_data += data
                
                # 如果累积了足够的数据，可以进行实时转录
                if len(audio_data) > 1024 * 50:  # 例如，每50KB进行一次转录
                    with open(temp_path, "wb") as f:
                        f.write(audio_data)
                    
                    # 执行转录
                    result = await transcriber.transcribe_file(
                        file_path=temp_path,
                        language=None,
                        task="transcribe"
                    )
                    
                    # 发送中间结果
                    await websocket.send_json({
                        "type": "interim_result",
                        "segments": result
                    })
    
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        # 清理
        if client_id in active_connections:
            del active_connections[client_id]
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 