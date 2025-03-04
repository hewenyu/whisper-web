from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
import os
import tempfile
import asyncio
import logging
from typing import List, Dict, Optional, Any
import uuid
import json
import time
import numpy as np

from .transcription import WhisperTranscriber
from .models import TranscriptionRequest, TranscriptionResponse, SubtitleFormat

from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 存储活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}
# 存储流式转录器实例
streaming_transcribers: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Whisper Web API")
    # 确保临时目录存在
    os.makedirs("temp", exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Whisper Web API")
    # 清理临时文件
    for file in os.listdir("temp"):
        try:
            os.remove(os.path.join("temp", file))
        except Exception as e:
            logger.error(f"Error removing temp file: {e}")

app = FastAPI(
    title="Whisper Web API",
    description="API for transcribing audio/video using faster-whisper",
    version="0.1.0",
    lifespan=lifespan
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

@app.get("/")
async def root():
    return {"message": "Welcome to Whisper Web API"}

@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """
    提供一个简单的测试页面，用于测试字幕功能
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Whisper Web 测试页面</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 {
                color: #333;
            }
            .container {
                margin-top: 20px;
            }
            button {
                padding: 10px 15px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin-right: 10px;
            }
            button:hover {
                background-color: #45a049;
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            #status {
                margin-top: 20px;
                padding: 10px;
                border-radius: 4px;
            }
            .success {
                background-color: #d4edda;
                color: #155724;
            }
            .error {
                background-color: #f8d7da;
                color: #721c24;
            }
            .info {
                background-color: #d1ecf1;
                color: #0c5460;
            }
            #subtitles {
                margin-top: 20px;
                padding: 15px;
                background-color: #333;
                color: white;
                border-radius: 4px;
                min-height: 50px;
                text-align: center;
                font-size: 18px;
            }
        </style>
    </head>
    <body>
        <h1>Whisper Web 测试页面</h1>
        <p>使用此页面测试Whisper Web API的流式字幕功能</p>
        
        <div class="container">
            <button id="startBtn">开始录音</button>
            <button id="stopBtn" disabled>停止录音</button>
        </div>
        
        <div id="status" class="info">准备就绪</div>
        
        <div id="subtitles">字幕将在这里显示</div>
        
        <script>
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            const status = document.getElementById('status');
            const subtitles = document.getElementById('subtitles');
            
            let websocket = null;
            let mediaRecorder = null;
            let audioContext = null;
            let audioStream = null;
            
            // 更新状态
            function updateStatus(message, type) {
                status.textContent = message;
                status.className = type;
            }
            
            // 更新字幕
            function updateSubtitles(text) {
                subtitles.textContent = text || '字幕将在这里显示';
            }
            
            // 连接WebSocket
            function connectWebSocket() {
                const clientId = 'test_' + Date.now();
                const wsUrl = `ws://${window.location.host}/ws/stream/${clientId}`;
                
                updateStatus('正在连接服务器...', 'info');
                
                websocket = new WebSocket(wsUrl);
                websocket.binaryType = 'arraybuffer';
                
                websocket.onopen = () => {
                    updateStatus('已连接到服务器', 'success');
                    startRecording();
                };
                
                websocket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        
                        if (data.type === 'streaming_result') {
                            updateSubtitles(data.text);
                        } else if (data.type === 'error') {
                            updateStatus(`错误: ${data.message}`, 'error');
                        } else if (data.type === 'info') {
                            updateStatus(data.message, 'info');
                        }
                    } catch (error) {
                        console.error('解析消息时出错:', error);
                    }
                };
                
                websocket.onclose = () => {
                    updateStatus('连接已关闭', 'info');
                    stopRecording(false);
                };
                
                websocket.onerror = (error) => {
                    updateStatus('连接错误', 'error');
                    console.error('WebSocket错误:', error);
                    stopRecording(false);
                };
            }
            
            // 开始录音
            async function startRecording() {
                try {
                    updateStatus('请求麦克风权限...', 'info');
                    
                    // 获取音频流
                    audioStream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        } 
                    });
                    
                    // 创建音频上下文
                    audioContext = new (window.AudioContext || window.webkitAudioContext)({
                        sampleRate: 16000
                    });
                    const source = audioContext.createMediaStreamSource(audioStream);
                    
                    // 创建处理节点
                    const processor = audioContext.createScriptProcessor(4096, 1, 1);
                    
                    // 连接节点
                    source.connect(processor);
                    processor.connect(audioContext.destination);
                    
                    // 处理音频数据
                    processor.onaudioprocess = (e) => {
                        if (!websocket || websocket.readyState !== WebSocket.OPEN) return;
                        
                        // 获取音频数据
                        const inputData = e.inputBuffer.getChannelData(0);
                        
                        // 转换为16位整数
                        const pcmData = new Int16Array(inputData.length);
                        for (let i = 0; i < inputData.length; i++) {
                            pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                        }
                        
                        // 发送音频数据
                        websocket.send(pcmData.buffer);
                    };
                    
                    updateStatus('正在录音...', 'success');
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    
                } catch (error) {
                    updateStatus(`录音错误: ${error.message}`, 'error');
                    console.error('启动录音时出错:', error);
                }
            }
            
            // 停止录音
            function stopRecording(sendEndSignal = true) {
                // 停止音频流
                if (audioStream) {
                    audioStream.getTracks().forEach(track => track.stop());
                    audioStream = null;
                }
                
                // 关闭音频上下文
                if (audioContext) {
                    audioContext.close().catch(console.error);
                    audioContext = null;
                }
                
                // 发送结束信号
                if (websocket && websocket.readyState === WebSocket.OPEN && sendEndSignal) {
                    websocket.send('END_OF_AUDIO');
                    updateStatus('已停止录音，正在处理...', 'info');
                }
                
                // 关闭WebSocket
                if (websocket) {
                    setTimeout(() => {
                        if (websocket.readyState === WebSocket.OPEN) {
                            websocket.close();
                        }
                        websocket = null;
                    }, 1000);
                }
                
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
            
            // 事件监听
            startBtn.addEventListener('click', () => {
                connectWebSocket();
            });
            
            stopBtn.addEventListener('click', () => {
                stopRecording();
                updateStatus('录音已停止', 'info');
            });
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.websocket("/ws/stream/{client_id}")
async def websocket_stream(websocket: WebSocket, client_id: str):
    """
    WebSocket端点，用于实时流式音频转录，提供实时字幕
    """
    try:
        from streaming_sensevoice import StreamingSenseVoice
        from pysilero import VADIterator
        import numpy as np
    except ImportError as e:
        logger.error(f"导入流式转录模块时出错: {str(e)}")
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": f"服务器缺少必要的模块: {str(e)}"
        })
        await websocket.close(code=1011, reason=f"服务器缺少必要的模块: {str(e)}")
        return
    
    logger.info(f"客户端 {client_id} 请求流式转录连接")
    await websocket.accept()
    logger.info(f"已接受客户端 {client_id} 的WebSocket连接")
    
    # 发送连接成功消息
    await websocket.send_json({
        "type": "info",
        "message": "连接成功，等待音频数据"
    })
    
    # 初始化流式转录器
    try:
        logger.info(f"为客户端 {client_id} 初始化流式转录器")
        model = StreamingSenseVoice()
        vad_iterator = VADIterator(speech_pad_ms=300)
        streaming_transcribers[client_id] = {
            "model": model,
            "vad_iterator": vad_iterator
        }
        logger.info(f"客户端 {client_id} 的流式转录器初始化成功")
    except Exception as e:
        logger.error(f"初始化流式转录器时出错: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"初始化转录器失败: {str(e)}"
        })
        await websocket.close(code=1011, reason=f"初始化转录器失败: {str(e)}")
        return
    
    active_connections[client_id] = websocket
    
    try:
        audio_buffer = []
        sample_rate = 16000
        
        while True:
            # 接收数据
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(f"客户端 {client_id} 断开连接")
                break
            except Exception as e:
                logger.error(f"接收消息时出错: {str(e)}")
                break
            
            # 检查消息类型
            if 'text' in message:
                text_data = message['text']
                logger.info(f"收到文本消息: {text_data}")
                
                if text_data == "END_OF_AUDIO":
                    logger.info(f"客户端 {client_id} 发送了END_OF_AUDIO信号")
                    # 处理剩余的音频数据
                    if audio_buffer:
                        try:
                            audio_samples = np.concatenate(audio_buffer)
                            for speech_dict, speech_samples in vad_iterator(audio_samples):
                                is_last = "end" in speech_dict
                                for res in model.streaming_inference(speech_samples * 32768, is_last):
                                    await websocket.send_json({
                                        "type": "streaming_result",
                                        "timestamps": res["timestamps"],
                                        "text": res["text"]
                                    })
                        except Exception as e:
                            logger.error(f"处理最终音频数据时出错: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"处理音频失败: {str(e)}"
                            })
                    
                    # 发送最终结果标记
                    await websocket.send_json({
                        "type": "final_result"
                    })
                    logger.info(f"客户端 {client_id} 的转录已完成")
                    break
                
                elif text_data == "RESET":
                    logger.info(f"客户端 {client_id} 请求重置")
                    # 重置模型和VAD
                    try:
                        model.reset()
                        vad_iterator = VADIterator(speech_pad_ms=300)
                        streaming_transcribers[client_id]["vad_iterator"] = vad_iterator
                        audio_buffer = []
                        await websocket.send_json({
                            "type": "reset_complete"
                        })
                        logger.info(f"客户端 {client_id} 重置完成")
                    except Exception as e:
                        logger.error(f"重置转录器时出错: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"重置失败: {str(e)}"
                        })
            
            elif 'bytes' in message:
                # 处理二进制音频数据
                audio_data = message['bytes']
                logger.debug(f"收到音频数据: {len(audio_data)} 字节")
                
                # 将二进制数据转换为浮点数组
                try:
                    # 假设音频数据是16位PCM
                    import struct
                    audio_samples = np.array(struct.unpack(f"{len(audio_data)//2}h", audio_data), dtype=np.float32) / 32768.0
                    audio_buffer.append(audio_samples)
                    
                    # 处理音频数据
                    for speech_dict, speech_samples in vad_iterator(audio_samples):
                        if "start" in speech_dict:
                            logger.debug(f"检测到语音开始")
                            model.reset()
                        is_last = "end" in speech_dict
                        if is_last:
                            logger.debug(f"检测到语音结束")
                        
                        try:
                            for res in model.streaming_inference(speech_samples * 32768, is_last):
                                await websocket.send_json({
                                    "type": "streaming_result",
                                    "timestamps": res["timestamps"],
                                    "text": res["text"]
                                })
                        except Exception as e:
                            logger.error(f"流式转录时出错: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"转录失败: {str(e)}"
                            })
                except Exception as e:
                    logger.error(f"处理音频数据时出错: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"处理音频失败: {str(e)}"
                    })
    
    except WebSocketDisconnect:
        logger.info(f"客户端 {client_id} 断开连接")
    
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            })
        except:
            pass
    
    finally:
        logger.info(f"清理客户端 {client_id} 的资源")
        if client_id in active_connections:
            del active_connections[client_id]
        if client_id in streaming_transcribers:
            del streaming_transcribers[client_id]

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 