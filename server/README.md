# Whisper Web 后端服务

基于FastAPI和faster-whisper的视频字幕生成服务。

## 功能

- 视频/音频文件转录
- 实时音频流转录
- 多语言支持
- 生成VTT/SRT/JSON格式字幕

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
DEVICE=cpu  # 或 cuda (需要NVIDIA GPU)
COMPUTE_TYPE=int8  # 或 float16
```

## 运行

```bash
python run.py
```

服务器将在 http://localhost:8000 启动。

## API文档

启动服务器后，访问 http://localhost:8000/docs 查看API文档。

### 主要端点

- `POST /transcribe` - 上传视频/音频文件进行转录
- `WebSocket /ws/transcribe/{client_id}` - 实时音频流转录

## 示例

### 文件转录

```python
import requests

url = "http://localhost:8000/transcribe"
files = {"file": open("video.mp4", "rb")}
params = {"language": "zh", "task": "transcribe", "format": "vtt"}

response = requests.post(url, files=files, params=params)
print(response.json())
```

### WebSocket实时转录

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/transcribe/client123");

ws.onopen = () => {
  console.log("Connected to WebSocket");
  
  // 发送音频数据
  ws.send(audioChunk);
  
  // 结束音频传输
  ws.send(new Uint8Array(Buffer.from("END_OF_AUDIO")));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);
};
``` 