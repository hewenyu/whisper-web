import os
import logging
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Optional, Any, Tuple, BinaryIO
import uuid
import json
from datetime import timedelta
import time
import numpy as np
import io

from faster_whisper import WhisperModel
import ffmpeg
import whisperx

from .models import TranscriptionSegment, SubtitleFormat

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseTranscriber:
    """
    基础转录器类，提供共享的功能
    """
    
    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None
    ):
        """
        初始化基础转录器
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
            device: 设备 ("cpu", "cuda", "auto")
            compute_type: 计算类型 ("float16", "float32", "int8")
        """
        # 从环境变量读取配置
        self.model_size = model_size or os.environ.get("MODEL_SIZE", "base")
        self.device = device or os.environ.get("DEVICE", "auto")
        self.compute_type = compute_type or os.environ.get("COMPUTE_TYPE", "float16")
        
        logger.info(f"Initializing BaseTranscriber with model_size={self.model_size}, device={self.device}, compute_type={self.compute_type}")
        
        # 检查CUDA可用性
        import torch
        cuda_available = torch.cuda.is_available()
        logger.info(f"CUDA available: {cuda_available}")
        if self.device == "cuda" and not cuda_available:
            logger.warning("CUDA requested but not available, falling back to CPU")
            self.device = "cpu"
        
        if self.device == "auto":
            self.device = "cuda" if cuda_available else "cpu"
            logger.info(f"Using device: {self.device}")
        
        # 记录系统信息
        if self.device == "cuda":
            try:
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU: {gpu_name}")
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info(f"GPU Memory: {gpu_memory:.2f} GB")
            except Exception as e:
                logger.warning(f"Failed to get GPU info: {str(e)}")
        
        # 确保临时目录存在
        os.makedirs("temp", exist_ok=True)
        os.makedirs("subtitles", exist_ok=True)
        
        # 模型将由子类加载
        self.model = None
    
    def _load_whisper_model(self):
        """
        加载Whisper模型
        """
        try:
            # 加载模型
            logger.info(f"Loading Whisper model: {self.model_size}")
            start_time = time.time()
            self.model = whisperx.load_model(
                self.model_size,
                self.device,
                compute_type=self.compute_type,
                language=None,
                asr_options={"suppress_blank": True}
            )
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            logger.exception("Detailed model loading error:")
            return False
    
    async def extract_audio(self, file_path: str) -> str:
        """
        从视频文件中提取音频
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            音频文件路径
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 生成临时音频文件路径
            audio_file = os.path.join("temp", f"{uuid.uuid4()}.wav")
            
            # 使用ffmpeg提取音频
            logger.info(f"Extracting audio from {file_path} to {audio_file}")
            
            # 使用subprocess调用ffmpeg
            cmd = [
                "ffmpeg",
                "-i", file_path,
                "-vn",  # 不处理视频
                "-acodec", "pcm_s16le",  # 16位PCM编码
                "-ar", "16000",  # 16kHz采样率
                "-ac", "1",  # 单声道
                "-y",  # 覆盖已存在的文件
                audio_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                raise Exception(f"Failed to extract audio: {stderr.decode()}")
            
            logger.info(f"Audio extraction completed: {audio_file}")
            return audio_file
            
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            raise
    
    def load_audio(self, file_path: str, sr: int = 16000):
        """
        加载音频文件
        
        Args:
            file_path: 音频文件路径
            sr: 采样率
            
        Returns:
            音频数据
        """
        try:
            # 使用ffmpeg加载音频
            logger.info(f"Loading audio from {file_path}")
            
            out, _ = (
                ffmpeg.input(file_path)
                .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=sr)
                .run(cmd=["ffmpeg", "-nostdin"], capture_stdout=True, capture_stderr=True)
            )
            
            # 将字节转换为numpy数组
            audio = np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
            logger.info(f"Audio loaded: {len(audio) / sr:.2f} seconds")
            
            return audio
            
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}")
            raise
    
    def generate_subtitles(self, segments: List[TranscriptionSegment], format: SubtitleFormat) -> str:
        """
        生成字幕文件
        
        Args:
            segments: 转录段落列表
            format: 字幕格式
            
        Returns:
            字幕文本
        """
        if format == SubtitleFormat.SRT:
            return self._generate_srt(segments)
        elif format == SubtitleFormat.VTT:
            return self._generate_vtt(segments)
        elif format == SubtitleFormat.JSON:
            return json.dumps([segment.dict() for segment in segments], ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported subtitle format: {format}")
    
    def _generate_srt(self, segments: List[TranscriptionSegment]) -> str:
        """
        生成SRT格式字幕
        
        Args:
            segments: 转录段落列表
            
        Returns:
            SRT字幕文本
        """
        lines = []
        
        for i, segment in enumerate(segments):
            # 序号
            lines.append(str(i + 1))
            
            # 时间戳
            start_time = self._format_timestamp(segment.start, SubtitleFormat.SRT)
            end_time = self._format_timestamp(segment.end, SubtitleFormat.SRT)
            lines.append(f"{start_time} --> {end_time}")
            
            # 文本
            lines.append(segment.text)
            
            # 空行
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_vtt(self, segments: List[TranscriptionSegment]) -> str:
        """
        生成VTT格式字幕
        
        Args:
            segments: 转录段落列表
            
        Returns:
            VTT字幕文本
        """
        lines = ["WEBVTT", ""]
        
        for segment in segments:
            # 时间戳
            start_time = self._format_timestamp(segment.start, SubtitleFormat.VTT)
            end_time = self._format_timestamp(segment.end, SubtitleFormat.VTT)
            lines.append(f"{start_time} --> {end_time}")
            
            # 文本
            lines.append(segment.text)
            
            # 空行
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_timestamp(self, seconds: float, format: SubtitleFormat) -> str:
        """
        格式化时间戳
        
        Args:
            seconds: 秒数
            format: 字幕格式
            
        Returns:
            格式化的时间戳
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        
        if format == SubtitleFormat.SRT:
            # SRT格式: 00:00:00,000
            return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{int((seconds - int(seconds)) * 1000):03d}"
        elif format == SubtitleFormat.VTT:
            # VTT格式: 00:00:00.000
            return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}.{int((seconds - int(seconds)) * 1000):03d}"
        else:
            raise ValueError(f"Unsupported subtitle format: {format}")
    
    def detect_language(self, audio: np.ndarray) -> str:
        """
        检测音频语言
        
        Args:
            audio: 音频数据
            
        Returns:
            语言代码
        """
        if self.model is None:
            self._load_whisper_model()
        
        try:
            logger.info("Detecting language")
            audio_for_detection = audio[:16000 * 30]  # 使用前30秒进行语言检测
            _, language_probs = self.model.detect_language(audio_for_detection)
            detected_lang = max(language_probs, key=language_probs.get)
            logger.info(f"Detected language: {detected_lang} (confidence: {language_probs[detected_lang]:.2f})")
            return detected_lang
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return "en"  # 默认返回英语 