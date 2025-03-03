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
            # 接收数据（可能是文本或二进制）
            message = await websocket.receive()
            
            # 检查消息类型
            if 'text' in message:
                # 处理文本消息
                text_data = message['text']
                logger.info(f"Received text message: {text_data}")
                
                if text_data == "END_OF_AUDIO":
                    # 音频传输结束，执行转录
                    if len(audio_data) > 0:
                        logger.info(f"Received END_OF_AUDIO signal, processing final audio data ({len(audio_data)} bytes)")
                        try:
                            with open(temp_path, "wb") as f:
                                f.write(audio_data)
                            
                            # 检查文件大小
                            file_size = os.path.getsize(temp_path)
                            logger.info(f"Saved final audio data to temporary file: {temp_path} ({file_size} bytes)")
                            
                            # 执行转录
                            logger.info("Starting final transcription")
                            result = await transcriber.transcribe_file(
                                file_path=temp_path,
                                language=None,
                                task="transcribe"
                            )
                            
                            # 检查结果
                            if result:
                                logger.info(f"Final transcription successful, got {len(result)} segments")
                                # 发送最终结果
                                await websocket.send_json({
                                    "type": "final_result",
                                    "segments": result
                                })
                            else:
                                logger.warning("Final transcription returned empty result")
                                await websocket.send_json({
                                    "type": "info",
                                    "message": "No transcription result"
                                })
                        except Exception as e:
                            logger.error(f"Error during final transcription: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Final transcription error: {str(e)}"
                            })
                        finally:
                            # 清理
                            audio_data = b""
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    else:
                        logger.warning("Received END_OF_AUDIO but no audio data was accumulated")
                elif text_data.startswith("{") and text_data.endswith("}"):
                    # 处理JSON消息
                    try:
                        json_data = json.loads(text_data)
                        if json_data.get("type") == "test":
                            # 响应测试消息
                            await websocket.send_json({
                                "type": "test_response",
                                "message": "Server received test message"
                            })
                        elif json_data.get("type") == "heartbeat":
                            # 响应心跳消息
                            await websocket.send_json({
                                "type": "heartbeat_response",
                                "message": "Server is alive"
                            })
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON: {text_data}")
                else:
                    # 其他文本消息
                    await websocket.send_json({
                        "type": "info",
                        "message": f"Received text: {text_data}"
                    })
            elif 'bytes' in message:
                # 处理二进制消息（音频数据）
                binary_data = message['bytes']
                logger.info(f"Received binary data: {len(binary_data)} bytes")
                
                # 累积音频数据
                audio_data += binary_data
                
                # 如果累积了足够的数据，可以进行实时转录
                if len(audio_data) > 1024 * 10:  # 降低阈值到10KB，更频繁地进行转录
                    logger.info(f"Accumulated enough data ({len(audio_data)} bytes), performing transcription")
                    try:
                        # 保存音频数据到临时文件
                        with open(temp_path, "wb") as f:
                            f.write(audio_data)
                        
                        # 检查文件大小
                        file_size = os.path.getsize(temp_path)
                        logger.info(f"Saved audio data to temporary file: {temp_path} ({file_size} bytes)")
                        
                        # 执行转录
                        logger.info("Starting transcription")
                        result = await transcriber.transcribe_file(
                            file_path=temp_path,
                            language=None,
                            task="transcribe"
                        )
                        
                        # 检查结果
                        if result:
                            logger.info(f"Transcription successful, got {len(result)} segments")
                            # 发送中间结果
                            await websocket.send_json({
                                "type": "interim_result",
                                "segments": result
                            })
                        else:
                            logger.warning("Transcription returned empty result")
                    except Exception as e:
                        logger.error(f"Error during transcription: {str(e)}")
                        # 发送错误消息但不中断连接
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Transcription error: {str(e)}"
                        })
            else:
                logger.warning(f"Received unknown message type: {message}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Unknown message format"
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