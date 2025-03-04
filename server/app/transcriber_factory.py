import os
import logging
from typing import Optional, Dict, Any, Type

from .base_transcriber import BaseTranscriber
from .video_transcription import VideoTranscriber

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriberFactory:
    """
    转录器工厂类，用于创建不同类型的转录器实例
    """
    
    # 注册的转录器类型
    _transcriber_types = {
        "video": VideoTranscriber,
        # 可以在这里添加更多转录器类型
    }
    
    # 缓存的转录器实例
    _instances: Dict[str, BaseTranscriber] = {}
    
    @classmethod
    def get_transcriber(
        cls,
        transcriber_type: str,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        force_new: bool = False
    ) -> BaseTranscriber:
        """
        获取转录器实例
        
        Args:
            transcriber_type: 转录器类型 ("video", "stream", 等)
            model_size: 模型大小
            device: 设备
            compute_type: 计算类型
            force_new: 是否强制创建新实例
            
        Returns:
            转录器实例
        """
        # 检查转录器类型是否有效
        if transcriber_type not in cls._transcriber_types:
            raise ValueError(f"Invalid transcriber type: {transcriber_type}")
        
        # 生成实例键
        instance_key = f"{transcriber_type}_{model_size or os.environ.get('MODEL_SIZE', 'base')}_{device or os.environ.get('DEVICE', 'auto')}_{compute_type or os.environ.get('COMPUTE_TYPE', 'float16')}"
        
        # 如果需要强制创建新实例，或者实例不存在，则创建新实例
        if force_new or instance_key not in cls._instances:
            logger.info(f"Creating new {transcriber_type} transcriber instance")
            transcriber_class = cls._transcriber_types[transcriber_type]
            cls._instances[instance_key] = transcriber_class(
                model_size=model_size,
                device=device,
                compute_type=compute_type
            )
        
        return cls._instances[instance_key]
    
    @classmethod
    def register_transcriber_type(cls, name: str, transcriber_class: Type[BaseTranscriber]):
        """
        注册新的转录器类型
        
        Args:
            name: 转录器类型名称
            transcriber_class: 转录器类
        """
        cls._transcriber_types[name] = transcriber_class
        logger.info(f"Registered new transcriber type: {name}")
    
    @classmethod
    def clear_instances(cls):
        """
        清除所有缓存的转录器实例
        """
        cls._instances.clear()
        logger.info("Cleared all transcriber instances") 