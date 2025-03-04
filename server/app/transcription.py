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
                language=None,
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
            
            # 如果已经是WAV音频文件，检查格式是否符合要求
            if ext == '.wav':
                try:
                    import wave
                    with wave.open(file_path, 'rb') as wf:
                        channels = wf.getnchannels()
                        width = wf.getsampwidth()
                        rate = wf.getframerate()
                        
                        logger.info(f"WAV file info: channels={channels}, width={width}, rate={rate}")
                        
                        # 如果已经是16位单声道16kHz WAV，直接返回
                        if channels == 1 and width == 2 and rate == 16000:
                            logger.info(f"WAV file already in correct format, skipping extraction")
                            return file_path
                except Exception as e:
                    logger.warning(f"Error checking WAV file: {str(e)}, will convert anyway")
            
            # 提取音频到16位单声道16kHz WAV
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
                
                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Output file size: {os.path.getsize(output_path)} bytes")
                    return output_path
                else:
                    logger.error(f"Output file is empty or does not exist: {output_path}")
                    raise ValueError(f"Failed to extract audio: output file is empty or does not exist")
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg error: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}")
                raise
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            logger.exception("Detailed extraction error:")
            raise
    
    def load_audio(self, file_path: str, sr: int = 16000):
        """
        加载音频文件并返回numpy数组
        
        Args:
            file_path: 音频文件路径
            sr: 采样率
            
        Returns:
            numpy数组形式的音频数据
        """
        try:
            logger.info(f"Loading audio file: {file_path}")
            import numpy as np
            import wave
            
            with wave.open(file_path, 'rb') as wf:
                # 获取音频参数
                channels = wf.getnchannels()
                width = wf.getsampwidth()
                rate = wf.getframerate()
                frames = wf.getnframes()
                
                logger.info(f"Audio info: channels={channels}, width={width}, rate={rate}, frames={frames}")
                
                # 读取所有音频数据
                data = wf.readframes(frames)
                
                # 转换为numpy数组
                if width == 2:  # 16-bit audio
                    dtype = np.int16
                elif width == 4:  # 32-bit audio
                    dtype = np.int32
                else:
                    dtype = np.int8
                
                audio_data = np.frombuffer(data, dtype=dtype)
                
                # 如果是立体声，转换为单声道
                if channels == 2:
                    audio_data = audio_data.reshape(-1, 2).mean(axis=1)
                
                # 转换为float32并归一化
                audio_data = audio_data.astype(np.float32) / np.iinfo(dtype).max
                
                # 重采样到目标采样率
                if rate != sr:
                    logger.info(f"Resampling from {rate}Hz to {sr}Hz")
                    # 简单的线性插值重采样
                    audio_length = len(audio_data)
                    new_length = int(audio_length * sr / rate)
                    indices = np.linspace(0, audio_length - 1, new_length)
                    indices = indices.astype(np.int32)
                    audio_data = audio_data[indices]
                
                logger.info(f"Loaded audio data: shape={audio_data.shape}, dtype={audio_data.dtype}")
                return audio_data
                
        except Exception as e:
            logger.error(f"Error loading audio: {str(e)}")
            logger.exception("Detailed audio loading error:")
            raise

    async def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> List[Dict[str, Any]]:
        """
        转录音频/视频文件
        
        Args:
            file_path: 文件路径
            language: 语言代码 (如 "zh", "en", None 表示自动检测)
            task: 任务类型 ("transcribe" 或 "translate")
            
        Returns:
            转录结果段落列表
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
                
            logger.info(f"Transcribing file: {file_path} ({file_size} bytes)")
            
            # 提取音频
            audio_path = await self.extract_audio(file_path)
            
            # 如果语言参数是"auto"，将其设置为None以触发自动检测
            if language == "auto":
                logger.info("Language parameter is 'auto', setting to None for auto-detection")
                language = None
            
            # 执行转录
            logger.info(f"Starting transcription with language={language}, task={task}")
            try:
                # 使用自定义方法加载音频
                audio = self.load_audio(audio_path)
                
                # 如果没有指定语言，先进行语言检测
                detected_language = None
                if language is None:
                    logger.info("No language specified, detecting language")
                    try:
                        # 使用少量音频进行语言检测
                        result = self.model.transcribe(audio[:24000], task="transcribe")
                        detected_language = result["language"]
                        logger.info(f"Detected language: {detected_language}")
                    except Exception as e:
                        logger.warning(f"Language detection failed: {str(e)}")
                        # 默认使用英语
                        detected_language = "en"
                
                # 使用检测到的语言或指定的语言进行转录
                transcribe_language = language or detected_language or "en"
                logger.info(f"Using language for transcription: {transcribe_language}")
                
                result = self.model.transcribe(
                    audio=audio,
                    language=transcribe_language,
                    task=task,
                )
                
                # 获取转录结果
                segments = result["segments"]
                logger.info(f"Transcription completed with {len(segments)} segments")
                
                # 转换为我们的数据模型
                result_segments = []
                for i, segment in enumerate(segments):
                    words = []
                    if "words" in segment:
                        for word in segment["words"]:
                            words.append({
                                "start": word["start"],
                                "end": word["end"],
                                "word": word["word"],
                                "probability": word.get("probability", 1.0)
                            })
                    
                    result_segments.append(TranscriptionSegment(
                        id=i,
                        start=segment["start"],
                        end=segment["end"],
                        text=segment["text"],
                        words=words
                    ))
                
                logger.info(f"Processed {len(result_segments)} segments")
                
                # 如果音频是临时提取的，则删除
                if audio_path != file_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    
                return result_segments
            except Exception as e:
                logger.error(f"Transcription error: {str(e)}")
                logger.exception("Detailed transcription error:")
                raise
        except Exception as e:
            logger.error(f"Error in transcribe_file: {str(e)}")
            logger.exception("Detailed error:")
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