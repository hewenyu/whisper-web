import os
import logging
import time
import numpy as np
from typing import List, Dict, Optional, Any, Generator, Tuple
from queue import Queue
from threading import Thread

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
        vad_parameters: Optional[Dict[str, Any]] = None
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
        device = device or os.environ.get("DEVICE", "auto")
        compute_type = compute_type or os.environ.get("COMPUTE_TYPE", "int8")
        
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
        
    def add_audio_chunk(self, audio_chunk: np.ndarray, sample_rate: int = 16000):
        """
        添加音频块到处理队列
        
        Args:
            audio_chunk: 音频数据，形状为 (samples,) 的numpy数组
            sample_rate: 采样率，默认16kHz
        """
        if not self.is_running:
            self.start_processing()
        
        # 确保音频是正确的格式
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.mean(axis=1)  # 转换为单声道
        
        # 如果采样率不是16kHz，需要重采样
        if sample_rate != 16000:
            # 这里简化处理，实际应该使用librosa等库进行重采样
            logger.warning(f"采样率 {sample_rate}Hz 不是16kHz，可能影响转录质量")
        
        self.audio_queue.put(audio_chunk)
        
    def finalize(self):
        """
        完成音频处理，获取最终结果
        """
        self.is_final = True
        self.audio_queue.put(None)  # 发送结束信号
        
        # 等待处理完成
        if self.processing_thread:
            self.processing_thread.join(timeout=10.0)
        
        # 返回最终结果
        return self.current_segments
        
    def _process_audio_queue(self):
        """
        处理音频队列的线程函数
        """
        buffer = np.array([], dtype=np.float32)
        
        while self.is_running:
            try:
                # 获取音频块
                chunk = self.audio_queue.get(timeout=0.1)
                
                # 检查是否是结束信号
                if chunk is None:
                    if buffer.size > 0:
                        # 处理剩余的音频
                        self._transcribe_audio(buffer)
                    break
                
                # 添加到缓冲区
                buffer = np.concatenate([buffer, chunk])
                
                # 当缓冲区足够大时进行处理
                if buffer.size > 16000 * 3:  # 3秒音频
                    self._transcribe_audio(buffer)
                    buffer = np.array([], dtype=np.float32)
                
            except Exception as e:
                if not isinstance(e, TimeoutError):
                    logger.error(f"音频处理错误: {str(e)}")
        
        logger.info("音频处理线程结束")
        
    def _transcribe_audio(self, audio: np.ndarray):
        """
        转录音频数据
        
        Args:
            audio: 音频数据，形状为 (samples,) 的numpy数组
        """
        try:
            # 转录音频
            segments, info = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                vad_parameters=self.vad_parameters
            )
            
            # 处理转录结果
            new_segments = []
            for segment in segments:
                new_segment = {
                    "id": len(self.current_segments),
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "words": []
                }
                
                # 添加词级时间戳（如果有）
                if segment.words:
                    for word in segment.words:
                        new_segment["words"].append({
                            "start": word.start,
                            "end": word.end,
                            "word": word.word
                        })
                
                new_segments.append(new_segment)
                self.current_segments.append(new_segment)
            
            # 返回新的片段
            return new_segments
            
        except Exception as e:
            logger.error(f"转录错误: {str(e)}")
            return []
    
    def stream_transcribe(self, audio_stream: Generator[np.ndarray, None, None], sample_rate: int = 16000) -> Generator[List[Dict], None, None]:
        """
        流式转录音频
        
        Args:
            audio_stream: 音频数据生成器，每次生成一个音频块
            sample_rate: 采样率，默认16kHz
            
        Yields:
            转录结果列表
        """
        # 重置状态
        self.current_segments = []
        self.is_final = False
        
        # 启动处理线程
        self.start_processing()
        
        last_segment_count = 0
        
        try:
            # 处理音频流
            for audio_chunk in audio_stream:
                self.add_audio_chunk(audio_chunk, sample_rate)
                
                # 如果有新的片段，返回
                if len(self.current_segments) > last_segment_count:
                    new_segments = self.current_segments[last_segment_count:]
                    last_segment_count = len(self.current_segments)
                    yield new_segments
            
            # 处理剩余的音频
            final_segments = self.finalize()
            
            # 如果有新的片段，返回
            if len(final_segments) > last_segment_count:
                yield final_segments[last_segment_count:]
                
        finally:
            # 确保停止处理
            self.stop_processing()


# 测试代码
if __name__ == "__main__":
    import soundfile as sf
    
    # 创建转录器
    transcriber = FasterWhisperStream(model_size="base", device="cpu")
    
    # 加载测试音频
    audio_file = "test.wav"
    if os.path.exists(audio_file):
        audio, sample_rate = sf.read(audio_file)
        
        # 模拟流式输入
        def audio_generator():
            chunk_size = sample_rate  # 1秒
            for i in range(0, len(audio), chunk_size):
                yield audio[i:i+chunk_size]
                time.sleep(0.1)  # 模拟实时流
        
        # 流式转录
        for segments in transcriber.stream_transcribe(audio_generator(), sample_rate):
            for segment in segments:
                print(f"[{segment['start']:.2f} -> {segment['end']:.2f}] {segment['text']}")
    else:
        print(f"测试文件 {audio_file} 不存在") 