# Whisper Web 后端服务

基于FastAPI和faster-whisper的视频字幕生成服务。

## 功能

- 视频/音频文件转录
- 实时音频流转录
- 多语言支持
- 生成VTT/SRT/JSON格式字幕
- 浏览器扩展API支持
- 音频提取和下载支持
- CUDA加速支持

## 项目结构

```
server/
├── app/                    # 主应用目录
│   ├── main.py            # 主应用入口和WebSocket服务
│   ├── browser_extension.py # 浏览器扩展相关API
│   └── models.py          # 数据模型定义
├── stream_whisper/        # 流式转录模块
├── audio_downloader/      # 音频下载模块
├── streaming_sensevoice/  # 语音识别模块
├── temp/                  # 临时文件目录
├── subtitles/            # 字幕文件输出目录
├── requirements.txt      # Python依赖
└── run.py               # 服务启动脚本
```

## 安装

1. 安装Python依赖：

```bash
pip install -r requirements.txt
```

2. 安装FFmpeg（用于处理视频/音频）：

Windows:
```
# 使用Chocolatey
choco install ffmpeg

# 或下载二进制文件并添加到PATH
```

Linux:
```
sudo apt update
sudo apt install ffmpeg
```

macOS:
```
brew install ffmpeg
```

## 配置

编辑`.env`文件设置环境变量：

```
# 服务器配置
HOST=0.0.0.0
PORT=8000
RELOAD=True

# Whisper模型配置
MODEL_SIZE=base  # 可选: tiny, base, small, medium, large
DEVICE=cuda     # 或 cpu
COMPUTE_TYPE=float16  # 或 int8
```

## API端点

### 文件转录

- `POST /transcribe`
  - 支持文件上传或UUID引用
  - 参数：
    - `file`: 上传的音频/视频文件
    - `file_uuid`: 已下载文件的UUID
    - `language`: 语言代码（可选）
    - `task`: 任务类型（transcribe/translate）

### 音频提取

- `POST /extract-audio`
  - 从URL提取音频
  - 参数：
    - `url`: 视频URL
    - `video_id`: 视频ID

### 字幕下载

- `GET /subtitles/{file_uuid}.{format}`
  - 下载生成的字幕文件
  - 支持格式：vtt, srt, json

### 实时转录

- `WebSocket /ws/stream/{client_id}`
  - 实时音频流转录
  - 支持浏览器麦克风输入

### 状态检查

- `GET /status`
  - 获取服务状态和模型信息

## 运行

```bash
python run.py
```

服务器将在 http://localhost:8000 启动。
API文档可在 http://localhost:8000/docs 查看。

## 测试页面

访问 http://localhost:8000/test 可以测试实时语音转录功能。

## 注意事项

- 确保有足够的磁盘空间用于临时文件和字幕存储
- 使用CUDA时需要安装对应的NVIDIA驱动和CUDA工具包
- 临时文件会在1小时后自动清理
- 建议在生产环境中配置适当的CORS策略

## 许可证

MIT 