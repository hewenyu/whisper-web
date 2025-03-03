import os
import logging
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Optional, Any, Tuple
import uuid
import json
from datetime import timedelta

from faster_whisper import WhisperModel
import ffmpeg

from .models import TranscriptionSegment, SubtitleFormat

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(self, model_size: str = None, device: str = None, compute_type: str = None):
        """
        初始化Whisper转录器
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
            device: 使用的设备 ("cpu" 或 "cuda")
            compute_type: 计算类型 ("float16", "int8")
        """
        # 从环境变量读取配置，如果没有提供参数
        self.model_size = model_size or os.getenv("MODEL_SIZE", "base")
        self.device = device or os.getenv("DEVICE", "cpu")
        self.compute_type = compute_type or os.getenv("COMPUTE_TYPE", "int8")
        
        # 检查CUDA是否可用，如果不可用则强制使用CPU
        if self.device == "cuda":
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning("CUDA is not available, falling back to CPU")
                    self.device = "cpu"
                    self.compute_type = "int8"
            except ImportError:
                logger.warning("PyTorch not found or CUDA is not available, falling back to CPU")
                self.device = "cpu"
                self.compute_type = "int8"
        
        logger.info(f"Loading Whisper model: {self.model_size} on {self.device} with {self.compute_type}")
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        
        # 确保临时目录存在
        os.makedirs("temp", exist_ok=True)
        os.makedirs("subtitles", exist_ok=True)
    
    async def extract_audio(self, file_path: str) -> str:
        """
        从视频文件中提取音频
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            音频文件路径
        """
        # 检查文件是否为音频文件
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in ['.mp3', '.wav', '.flac', '.ogg']:
            return file_path
        
        # 提取音频
        audio_path = os.path.join("temp", f"{uuid.uuid4()}.wav")
        
        try:
            # 使用ffmpeg提取音频
            (
                ffmpeg
                .input(file_path)
                .output(audio_path, acodec='pcm_s16le', ar='16000', ac=1)
                .run(quiet=True, overwrite_output=True)
            )
            return audio_path
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            raise
    
    async def transcribe_file(
        self, 
        file_path: str, 
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> List[TranscriptionSegment]:
        """
        转录音频/视频文件
        
        Args:
            file_path: 文件路径
            language: 语言代码 (如 "en", "zh", "ja")
            task: 任务类型 ("transcribe" 或 "translate")
            
        Returns:
            转录结果段落列表
        """
        try:
            # 提取音频
            audio_path = await self.extract_audio(file_path)
            
            # 执行转录
            logger.info(f"Transcribing file: {audio_path}")
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                task=task,
                vad_filter=True,
                word_timestamps=True
            )
            
            # 转换为我们的数据模型
            result = []
            for i, segment in enumerate(segments):
                result.append(TranscriptionSegment(
                    id=i,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    words=[{
                        "start": word.start,
                        "end": word.end,
                        "word": word.word,
                        "probability": word.probability
                    } for word in segment.words]
                ))
            
            # 如果音频是临时提取的，则删除
            if audio_path != file_path and os.path.exists(audio_path):
                os.remove(audio_path)
                
            return result
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise
    
    def generate_subtitles(self, segments: List[TranscriptionSegment], format: SubtitleFormat) -> str:
        """
        根据转录结果生成字幕文件
        
        Args:
            segments: 转录结果段落
            format: 字幕格式
            
        Returns:
            字幕文件路径
        """
        subtitle_path = os.path.join("subtitles", f"{uuid.uuid4()}.{format}")
        
        try:
            with open(subtitle_path, "w", encoding="utf-8") as f:
                if format == SubtitleFormat.vtt:
                    f.write("WEBVTT\n\n")
                    for segment in segments:
                        start_time = self._format_timestamp(segment.start, format)
                        end_time = self._format_timestamp(segment.end, format)
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{segment.text.strip()}\n\n")
                
                elif format == SubtitleFormat.srt:
                    for i, segment in enumerate(segments):
                        start_time = self._format_timestamp(segment.start, format)
                        end_time = self._format_timestamp(segment.end, format)
                        f.write(f"{i+1}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{segment.text.strip()}\n\n")
                
                elif format == SubtitleFormat.json:
                    json_data = [segment.dict() for segment in segments]
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return subtitle_path
        except Exception as e:
            logger.error(f"Error generating subtitles: {str(e)}")
            raise
    
    def _format_timestamp(self, seconds: float, format: SubtitleFormat) -> str:
        """
        格式化时间戳
        
        Args:
            seconds: 秒数
            format: 字幕格式
            
        Returns:
            格式化的时间戳
        """
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = td.microseconds // 1000
        
        if format == SubtitleFormat.vtt:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        elif format == SubtitleFormat.srt:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}" 