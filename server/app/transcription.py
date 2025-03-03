import os
import logging
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Optional, Any, Tuple
import uuid
import json
from datetime import timedelta
import time

from faster_whisper import WhisperModel
import ffmpeg
import whisperx

from .models import TranscriptionSegment, SubtitleFormat

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None
    ):
        """
        初始化Whisper转录器
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
            device: 设备 ("cpu", "cuda", "auto")
            compute_type: 计算类型 ("float16", "float32", "int8")
        """
        # 从环境变量读取配置
        model_size = model_size or os.environ.get("MODEL_SIZE", "base")
        device = device or os.environ.get("DEVICE", "auto")
        compute_type = compute_type or os.environ.get("COMPUTE_TYPE", "float16")
        
        logger.info(f"Initializing WhisperTranscriber with model_size={model_size}, device={device}, compute_type={compute_type}")
        
        # 检查CUDA可用性
        import torch
        cuda_available = torch.cuda.is_available()
        logger.info(f"CUDA available: {cuda_available}")
        if device == "cuda" and not cuda_available:
            logger.warning("CUDA requested but not available, falling back to CPU")
            device = "cpu"
        
        if device == "auto":
            device = "cuda" if cuda_available else "cpu"
            logger.info(f"Using device: {device}")
        
        # 记录系统信息
        if device == "cuda":
            try:
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU: {gpu_name}")
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info(f"GPU Memory: {gpu_memory:.2f} GB")
            except Exception as e:
                logger.warning(f"Failed to get GPU info: {str(e)}")
        
        try:
            # 加载模型
            logger.info(f"Loading Whisper model: {model_size}")
            start_time = time.time()
            self.model = whisperx.load_model(
                model_size,
                device,
                compute_type=compute_type,
                language="auto",
                asr_options={"suppress_blank": True}
            )
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            logger.exception("Detailed model loading error:")
            raise
        
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
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
                
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            logger.info(f"Processing file: {file_path} ({file_size} bytes)")
            
            # 检查文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # 如果已经是音频文件，直接返回
            if ext in ['.wav', '.mp3', '.ogg', '.flac', '.aac', '.webm']:
                logger.info(f"File is already an audio file ({ext}), skipping extraction")
                return file_path
                
            # 提取音频
            output_path = os.path.join("temp", f"{uuid.uuid4()}.wav")
            logger.info(f"Extracting audio to: {output_path}")
            
            try:
                # 使用ffmpeg提取音频
                (
                    ffmpeg
                    .input(file_path)
                    .output(output_path, acodec='pcm_s16le', ar='16000', ac=1)
                    .run(capture_stdout=True, capture_stderr=True)
                )
                logger.info(f"Audio extraction successful: {output_path}")
                return output_path
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg error: {e.stderr.decode()}")
                raise
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
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
                
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(f"Empty file: {file_path}")
                raise ValueError(f"Empty file: {file_path}")
                
            logger.info(f"Transcribing file: {file_path} ({file_size} bytes)")
            
            # 提取音频
            audio_path = await self.extract_audio(file_path)
            
            # 执行转录
            logger.info(f"Starting transcription with language={language}, task={task}")
            try:
                segments, info = self.model.transcribe(
                    audio_path,
                    language=language,
                    task=task,
                    vad_filter=True,
                    word_timestamps=True
                )
                
                logger.info(f"Transcription info: {info}")
                
                # 转换为我们的数据模型
                result = []
                segment_count = 0
                
                for i, segment in enumerate(segments):
                    segment_count += 1
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
                
                logger.info(f"Transcription completed: {segment_count} segments")
                
                # 如果音频是临时提取的，则删除
                if audio_path != file_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    
                return result
            except Exception as e:
                logger.error(f"Transcription error: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Error in transcribe_file: {str(e)}")
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