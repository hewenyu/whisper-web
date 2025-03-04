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
from .base_transcriber import BaseTranscriber

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoTranscriber(BaseTranscriber):
    """
    视频转录器类，用于处理视频文件的转录和字幕生成
    支持分段处理长视频，使用强制对齐算法提高字幕准确性
    """
    
    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        segment_duration: float = 30.0,  # 每段音频的长度（秒）
        overlap_duration: float = 2.0,   # 重叠部分长度（秒）
    ):
        """
        初始化视频转录器
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
            device: 设备 ("cpu", "cuda", "auto")
            compute_type: 计算类型 ("float16", "float32", "int8")
            segment_duration: 分段长度（秒）
            overlap_duration: 重叠部分长度（秒）
        """
        # 调用父类初始化
        super().__init__(model_size, device, compute_type)
        
        self.segment_duration = segment_duration
        self.overlap_duration = overlap_duration
        
        try:
            # 加载Whisper模型
            self._load_whisper_model()
            
            # 加载强制对齐模型
            self._load_alignment_model()
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            raise

    def _load_alignment_model(self):
        """
        加载强制对齐模型
        """
        try:
            logger.info("加载强制对齐模型")
            import whisperx
            self.alignment_model, self.metadata = whisperx.load_align_model(
                language_code="zh",
                device=self.device
            )
            logger.info("强制对齐模型加载完成")
        except Exception as e:
            logger.error(f"加载强制对齐模型失败: {str(e)}")
            raise

    async def process_complete_video(self, audio_path: str, language: Optional[str] = None) -> List[TranscriptionSegment]:
        """
        处理完整视频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码
            
        Returns:
            转录段落列表
        """
        try:
            # 加载音频
            audio = self.load_audio(audio_path)
            sample_rate = 16000
            
            # 计算总时长（秒）
            total_duration = len(audio) / sample_rate
            logger.info(f"音频总时长: {total_duration:.2f} 秒")
            
            # 分段处理
            all_segments = await self.process_audio_segments(audio_path, language)
            
            # 应用强制对齐
            aligned_segments = await self.apply_forced_alignment(audio, all_segments)
            
            # 合并和优化字幕段落
            final_segments = self.optimize_segments(aligned_segments)
            
            return final_segments
            
        except Exception as e:
            logger.error(f"处理完整视频失败: {str(e)}")
            raise

    async def apply_forced_alignment(self, audio: np.ndarray, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
        """
        应用强制对齐算法
        
        Args:
            audio: 音频数据
            segments: 原始转录段落
            
        Returns:
            对齐后的段落
        """
        try:
            logger.info("应用强制对齐算法")
            
            # 准备输入数据
            whisperx_segments = [{
                "start": s.start,
                "end": s.end,
                "text": s.text
            } for s in segments]
            
            # 应用强制对齐
            result = whisperx.align(
                whisperx_segments,
                self.alignment_model,
                self.metadata,
                audio,
                device=self.device,
                return_char_alignments=False
            )
            
            # 转换回TranscriptionSegment格式
            aligned_segments = []
            for segment in result["segments"]:
                aligned_segments.append(TranscriptionSegment(
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"],
                    words=[{
                        "word": w["word"],
                        "start": w["start"],
                        "end": w["end"],
                        "score": w.get("score", 1.0)
                    } for w in segment.get("words", [])]
                ))
            
            return aligned_segments
            
        except Exception as e:
            logger.error(f"强制对齐失败: {str(e)}")
            raise

    def optimize_segments(self, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
        """
        优化字幕段落
        
        Args:
            segments: 字幕段落列表
            
        Returns:
            优化后的段落列表
        """
        try:
            logger.info("优化字幕段落")
            
            # 按时间排序
            segments.sort(key=lambda x: x.start)
            
            # 合并过短的段落
            MIN_DURATION = 1.0  # 最短段落时长（秒）
            MAX_DURATION = 5.0  # 最长段落时长（秒）
            
            optimized = []
            current = None
            
            for segment in segments:
                if not current:
                    current = segment
                    continue
                    
                # 计算当前段落时长
                current_duration = current.end - current.start
                
                # 如果当前段落过短，且与下一段落间隔很短，则合并
                if (current_duration < MIN_DURATION and 
                    segment.start - current.end < 0.3):
                    current.end = segment.end
                    current.text += " " + segment.text
                    current.words.extend(segment.words)
                else:
                    # 如果当前段落过长，则拆分
                    if current_duration > MAX_DURATION:
                        split_segments = self._split_long_segment(current)
                        optimized.extend(split_segments)
                    else:
                        optimized.append(current)
                    current = segment
            
            # 处理最后一个段落
            if current:
                if current.end - current.start > MAX_DURATION:
                    optimized.extend(self._split_long_segment(current))
                else:
                    optimized.append(current)
            
            return optimized
            
        except Exception as e:
            logger.error(f"优化段落失败: {str(e)}")
            raise

    def _split_long_segment(self, segment: TranscriptionSegment) -> List[TranscriptionSegment]:
        """
        拆分过长的段落
        
        Args:
            segment: 要拆分的段落
            
        Returns:
            拆分后的段落列表
        """
        try:
            # 根据标点符号或停顿拆分文本
            parts = []
            current_part = []
            current_words = []
            
            for word in segment.words:
                current_part.append(word["word"])
                current_words.append(word)
                
                # 在标点符号处拆分
                if any(p in word["word"] for p in "。，！？.!?"):
                    if current_part:
                        parts.append({
                            "text": "".join(current_part),
                            "words": current_words.copy()
                        })
                        current_part = []
                        current_words = []
            
            # 处理剩余部分
            if current_part:
                parts.append({
                    "text": "".join(current_part),
                    "words": current_words
                })
            
            # 创建新的段落
            result = []
            for part in parts:
                if not part["words"]:
                    continue
                    
                result.append(TranscriptionSegment(
                    start=part["words"][0]["start"],
                    end=part["words"][-1]["end"],
                    text=part["text"],
                    words=part["words"]
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"拆分段落失败: {str(e)}")
            raise

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
    
    async def process_audio_segments(self, audio_path: str, language: Optional[str] = None) -> List[TranscriptionSegment]:
        """
        分段处理长音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码
            
        Returns:
            转录段落列表
        """
        try:
            # 加载音频
            audio = self.load_audio(audio_path)
            sample_rate = 16000
            
            # 计算总时长（秒）
            total_duration = len(audio) / sample_rate
            logger.info(f"Total audio duration: {total_duration:.2f} seconds")
            
            # 如果音频较短，直接处理
            if total_duration <= self.segment_duration:
                logger.info("Audio is short enough for direct processing")
                return await self.transcribe_audio(audio, language)
            
            # 分段处理
            logger.info(f"Processing audio in segments of {self.segment_duration} seconds with {self.overlap_duration} seconds overlap")
            
            all_segments = []
            segment_start = 0
            
            while segment_start < total_duration:
                # 计算当前段的结束时间
                segment_end = min(segment_start + self.segment_duration, total_duration)
                
                # 计算音频样本的起止索引
                start_idx = int(segment_start * sample_rate)
                end_idx = int(segment_end * sample_rate)
                
                # 提取当前段的音频
                segment_audio = audio[start_idx:end_idx]
                
                logger.info(f"Processing segment from {segment_start:.2f}s to {segment_end:.2f}s")
                
                # 转录当前段
                segment_results = await self.transcribe_audio(segment_audio, language, offset=segment_start)
                
                # 添加到结果中
                all_segments.extend(segment_results)
                
                # 更新下一段的起始时间（考虑重叠）
                segment_start = segment_end - self.overlap_duration
                
                # 如果已经处理到末尾，退出循环
                if segment_end >= total_duration:
                    break
            
            # 合并重叠的段落
            merged_segments = self._merge_overlapping_segments(all_segments)
            
            return merged_segments
            
        except Exception as e:
            logger.error(f"Error processing audio segments: {str(e)}")
            raise
    
    async def transcribe_audio(self, audio: np.ndarray, language: Optional[str] = None, offset: float = 0.0) -> List[TranscriptionSegment]:
        """
        转录音频数据
        
        Args:
            audio: 音频数据
            language: 语言代码
            offset: 时间偏移量（秒）
            
        Returns:
            转录段落列表
        """
        try:
            # 检测语言（如果未指定）
            if language == "auto" or language is None:
                language = self.detect_language(audio)
            
            # 转录音频
            logger.info(f"Transcribing audio with language: {language}")
            result = self.model.transcribe(
                audio,
                language=language,
                task="transcribe",
                beam_size=5,
                word_timestamps=True
            )
            
            # 应用强制对齐
            logger.info("Applying forced alignment")
            result = whisperx.align(
                result["segments"],
                self.alignment_model,
                self.metadata,
                audio,
                device=self.model.device,
                return_char_alignments=False
            )
            
            # 转换为TranscriptionSegment格式
            segments = []
            for segment in result["segments"]:
                # 应用时间偏移
                start_time = segment["start"] + offset
                end_time = segment["end"] + offset
                
                # 创建段落对象
                transcription_segment = TranscriptionSegment(
                    id=len(segments),
                    start=start_time,
                    end=end_time,
                    text=segment["text"].strip(),
                    words=[
                        {
                            "word": word["word"],
                            "start": word["start"] + offset,
                            "end": word["end"] + offset,
                            "score": word.get("score", 0.0)
                        }
                        for word in segment.get("words", [])
                    ]
                )
                
                segments.append(transcription_segment)
            
            logger.info(f"Transcription completed: {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise
    
    def _merge_overlapping_segments(self, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
        """
        合并重叠的段落
        
        Args:
            segments: 转录段落列表
            
        Returns:
            合并后的段落列表
        """
        if not segments:
            return []
        
        # 按开始时间排序
        sorted_segments = sorted(segments, key=lambda s: s.start)
        
        merged = []
        current = sorted_segments[0]
        
        for next_segment in sorted_segments[1:]:
            # 如果当前段落的结束时间与下一段落的开始时间重叠
            if current.end >= next_segment.start:
                # 如果重叠超过50%，合并段落
                overlap_duration = current.end - next_segment.start
                next_duration = next_segment.end - next_segment.start
                
                if overlap_duration > 0.5 * next_duration:
                    # 更新当前段落的结束时间
                    current.end = max(current.end, next_segment.end)
                    
                    # 合并文本（避免重复）
                    if next_segment.text not in current.text:
                        current.text += " " + next_segment.text
                    
                    # 合并单词
                    current.words.extend([
                        word for word in next_segment.words
                        if not any(w["word"] == word["word"] and abs(w["start"] - word["start"]) < 0.1 for w in current.words)
                    ])
                else:
                    # 重叠不够大，添加当前段落并移动到下一个
                    merged.append(current)
                    current = next_segment
            else:
                # 没有重叠，添加当前段落并移动到下一个
                merged.append(current)
                current = next_segment
        
        # 添加最后一个段落
        merged.append(current)
        
        # 重新分配ID
        for i, segment in enumerate(merged):
            segment.id = i
        
        return merged
    
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