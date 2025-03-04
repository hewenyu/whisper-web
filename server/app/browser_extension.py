import os
import asyncio
import logging
import tempfile
from typing import Optional, List, Dict, Any
from enum import Enum
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from stream_whisper.faster_whisper import FasterWhisperStream
from audio_downloader import AudioDownloader
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 创建路由器
router = APIRouter(
    prefix="",
    tags=["browser_extension"],
    responses={404: {"description": "Not found"}},
)

# 初始化转录器
transcriber = FasterWhisperStream(output_path="subtitles",device="cuda",compute_type="float16")

output_path = "temp"
subtitles_path = "subtitles"
audio_format = "wav"
quality = "0"

ytdlp_downloader = AudioDownloader(output_path, audio_format, quality)

@router.post("/transcribe")
async def transcribe_for_browser_extension(
    background_tasks: BackgroundTasks,
    file_uuid: str = Form(None),
    file: Optional[UploadFile] = File(None),
    language: Optional[str] = Form(None),
    task: str = Form("transcribe"),
):
    """
    为浏览器扩展提供的转录端点
    接收视频/音频文件或已下载文件的UUID，返回转录结果
    
    Args:
        file_uuid: 已下载文件的UUID
        file: 上传的视频/音频文件
        language: 语言代码 (如 "zh", "en", None 表示自动检测)
        task: 任务类型 ("transcribe" 或 "translate")
        format: 字幕格式 ("vtt", "srt", "json")
        
    Returns:
        转录结果
    """
    try:
        if file:
            # 添加清理任务
            background_tasks.add_task(os.unlink, temp_path)
        elif file_uuid:
            logger.info(f"接收到浏览器扩展转录请求: UUID={file_uuid}, language={language}, task={task}")
            # 根据UUID查找文件
            temp_path = os.path.join(output_path, f"{file_uuid}.{audio_format}")
            if not os.path.exists(temp_path):
                raise HTTPException(status_code=404, detail=f"找不到文件: {file_uuid}")
        else:
            raise HTTPException(status_code=400, detail="必须提供文件或文件UUID")
        
        # 转录文件 - 注意这里不传递subtitle_format参数
        segments_vtt = await transcriber.transcribe_file(
            temp_path,
            language=language,
            task=task
        )

        subtitle_file = os.path.join(subtitles_path, segments_vtt)
        
        # 返回结果
        return {
            "success": True,
            "message": "转录成功",
            "segments": segments_vtt,
            "subtitle_file": subtitle_file
            
        }
        
    except Exception as e:
        logger.error(f"浏览器扩展转录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

@router.get("/status")
async def get_extension_status():
    """
    获取服务状态
    
    Returns:
        服务状态信息
    """
    try:
        # 获取模型信息
        model_info = {
            "model_size": os.environ.get("MODEL_SIZE", "base"),
            "device": os.environ.get("DEVICE", "cpu"),
            "compute_type": os.environ.get("COMPUTE_TYPE", "int8")
        }
        
        return {
            "status": "healthy",
            "model": model_info,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"获取状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


# download subtitles
@router.get("/subtitles/{file_uuid}.{format}")
async def get_subtitles(
    file_uuid: str,
    format: str
):
    """
    获取指定文件的指定格式字幕
    
    Args:
        file_uuid: 字幕文件UUID
        format: 字幕文件格式(srt/vtt)
        
    Returns:
        字幕文件下载响应
    """
    try:
        # 验证格式是否合法
        if format.lower() not in ["srt", "vtt", "json"]:
            raise HTTPException(status_code=400, detail=f"不支持的字幕格式: {format}")
            
        file_path = os.path.join(subtitles_path, f"{file_uuid}.{format}")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"找不到字幕文件: {file_uuid}.{format}")
            
        # 设置文件名，让浏览器正确处理下载
        filename = f"subtitle_{file_uuid}.{format}"
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path, 
            filename=filename,
            media_type="application/octet-stream"
        )
    except Exception as e:
        logger.error(f"下载字幕失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载字幕失败: {str(e)}")

@router.post("/extract-audio")
async def extract_audio_from_url(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    video_id: str = Form(...)
):
    """从URL提取音频"""
    logger.info(f"收到音频提取请求: {url}, video_id: {video_id}")
    
    try:
        audio_filepath = ytdlp_downloader.download_audio(url)
       
        return {
            "success": True,
            "audio_url": audio_filepath,
            "message": "音频提取成功 (yt-dlp)",
            "file_uuid": os.path.basename(audio_filepath).split('.')[0]  # 返回文件UUID，用于后续转录
        }
        
    except Exception as e:
        logger.exception(f"提取音频时发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"提取音频失败: {str(e)}"}
        )

async def delayed_delete(path, delay=3600):  # 1小时后删除
    """延迟删除文件"""
    try:
        await asyncio.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"已删除临时文件: {path}")
    except Exception as e:
        logger.error(f"删除临时文件失败: {path}, 错误: {str(e)}") 