import os
import logging
import time
import numpy as np
from typing import List, Dict, Optional, Any, Generator, Tuple
from queue import Queue
from threading import Thread
from datetime import timedelta
from enum import Enum
from faster_whisper import WhisperModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FasterWhisperStream:
    """
    基于faster-whisper的流式转录实现
    支持实时音频流的转录和字幕生成
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_parameters: Optional[Dict[str, Any]] = None,
        output_path: str = "subtitles"
    ):
        """
        初始化流式转录器
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
            device: 设备 ("cpu", "cuda", "auto")
            compute_type: 计算类型 ("float16", "int8")
            language: 语言代码 (如 "zh", "en", None 表示自动检测)
            beam_size: 束搜索大小
            vad_filter: 是否使用语音活动检测
            vad_parameters: VAD参数
        """
        # 从环境变量读取配置
        model_size = model_size or os.environ.get("MODEL_SIZE", "base")
        device = device or os.environ.get("DEVICE", "cpu")
        compute_type = compute_type or os.environ.get("COMPUTE_TYPE", "int8")
        self.output_path = output_path or os.environ.get("OUTPUT_PATH", "subtitles")
        
        logger.info(f"初始化FasterWhisperStream: model_size={model_size}, device={device}, compute_type={compute_type}")
        
        # 加载模型
        try:
            start_time = time.time()
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=os.path.join(os.path.dirname(__file__), "models")
            )
            load_time = time.time() - start_time
            logger.info(f"模型加载完成，耗时 {load_time:.2f} 秒")
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise
        
        # 转录参数
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.vad_parameters = vad_parameters or {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 30,
            "min_silence_duration_ms": 500
        }
        
        # 流式处理状态
        self.audio_queue = Queue()
        self.is_running = False
        self.processing_thread = None
        self.current_segments = []
        self.is_final = False
        
    def start_processing(self):
        """
        启动流式处理线程
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = Thread(target=self._process_audio_queue)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("流式处理线程已启动")
        
    def stop_processing(self):
        """
        停止流式处理线程
        """
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
            self.processing_thread = None
        logger.info("流式处理线程已停止")

    async def transcribe_file(self, file_path: str, language: Optional[str] = None, task: str = "transcribe") -> str:
        """
        转录文件
        """
        # 输出当前目录
        logger.info(f"当前目录: {os.getcwd()}")
        logger.info(f"开始转录文件: {file_path}")
        # 获取文件名, 去掉扩展名
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        segments, _ = self.model.transcribe(file_path, language=language, task=task, max_new_tokens=42)
        # 将字幕转换为vtt格式 并保存
        
        vtt_content = self.convert_to_vtt(segments)
        vtt_name = f"{file_name}.vtt"
        logger.info(f"vtt文件名: {vtt_name}")
        vtt_path = os.path.join(self.output_path, vtt_name)
        logger.info(f"vtt文件路径: {vtt_path}")
        

        try:
            # Ensure the output directory exists
            os.makedirs(self.output_path, exist_ok=True)
            
            with open(vtt_path, "w", encoding="utf-8") as f:
                f.write(vtt_content)
            return vtt_name
        except Exception as e:
            logger.error(f"保存vtt文件失败: {str(e)}")
            raise

    def convert_to_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """
        将字幕转换为vtt格式
        """
        vtt_content = "WEBVTT\n\n"
        for segment in segments:
            start = self._format_timestamp(segment.start, "vtt")
            end = self._format_timestamp(segment.end, "vtt")
            text = segment.text.strip()
            vtt_content += f"{start} --> {end}\n{text}\n\n"
        return vtt_content
    
    def _format_timestamp(self, seconds: float, subtitle_format: str) -> str:
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
        
        if subtitle_format == "vtt":
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        elif subtitle_format == "srt":
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

