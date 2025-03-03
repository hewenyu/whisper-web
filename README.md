# Whisper Web

基于faster-whisper的在线视频字幕工具，包含Web应用和浏览器插件。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-green.svg" alt="FastAPI Version">
  <img src="https://img.shields.io/badge/Next.js-13.4+-orange.svg" alt="Next.js Version">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 项目概述

Whisper Web 是一个基于 OpenAI 的 Whisper 模型的在线视频字幕生成工具，使用 faster-whisper 作为后端引擎，提供了简单易用的 Web 界面和浏览器插件，让用户可以轻松为视频添加高质量的字幕。

本项目包含三个主要部分：

- **后端服务**：基于 FastAPI 和 faster-whisper 的 API 服务，负责处理视频/音频文件并生成字幕
- **前端应用**：基于 Next.js 的 Web 应用，提供用户界面，允许用户上传视频并获取字幕
- **浏览器插件**：Chrome/Firefox 扩展，可以为任意网站上的视频添加实时字幕

## 功能特点

- **视频上传和URL导入**：支持本地视频上传和网络视频URL导入
- **实时语音识别**：使用 faster-whisper 模型进行高精度语音识别
- **多语言支持**：支持中文、英文、日语等多种语言的识别和转录
- **字幕编辑和导出**：支持 VTT、SRT 和 JSON 格式的字幕导出
- **浏览器插件**：为任意网站上的视频添加实时字幕
- **响应式设计**：适配各种设备，包括桌面和移动设备

## 系统要求

- Python 3.8+
- Node.js 16+
- FFmpeg（用于视频/音频处理）
- 至少 4GB RAM（推荐 8GB+，特别是使用较大的模型时）
- 支持 CUDA 的 NVIDIA GPU（可选，但推荐用于更快的处理速度）

## 安装指南

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/whisper-web.git
cd whisper-web
```

### 2. 安装后端依赖

```bash
cd server
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd ../web
npm install
# 或
yarn install
```

### 4. 安装 FFmpeg

#### Windows:
```bash
# 使用 Chocolatey
choco install ffmpeg

# 或下载二进制文件并添加到 PATH
```

#### Linux:
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS:
```bash
brew install ffmpeg
```

## 配置

### 后端配置

编辑 `server/.env` 文件：

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

### 前端配置

创建 `web/.env.local` 文件：

```
API_URL=http://localhost:8000  # 后端API地址
```

## 运行项目

### 1. 启动后端服务

```bash
cd server
python run.py
```

服务器将在 http://localhost:8000 启动。API文档可在 http://localhost:8000/docs 查看。

### 2. 启动前端应用

```bash
cd ../web
npm run dev
# 或
yarn dev
```

前端应用将在 http://localhost:3000 启动。

### 3. 安装浏览器插件

#### Chrome:
1. 打开 Chrome 扩展页面 `chrome://extensions/`
2. 启用"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择项目中的 `extension` 目录

#### Firefox:
1. 打开 Firefox 扩展页面 `about:debugging#/runtime/this-firefox`
2. 点击"临时载入附加组件"
3. 选择项目中的 `extension/manifest.json` 文件

## 使用方法

### Web应用

1. 访问 http://localhost:3000
2. 点击"上传视频"页面
3. 上传视频文件或提供视频URL
4. 选择语言和字幕格式
5. 点击"生成字幕"按钮
6. 预览生成的字幕
7. 下载字幕文件

### 浏览器插件

1. 点击浏览器工具栏中的插件图标
2. 设置服务器地址和其他选项
3. 点击"激活字幕"按钮
4. 浏览包含视频的网页
5. 视频右上角会出现字幕控制按钮
6. 点击"开始字幕"按钮开始生成字幕

## 技术架构

### 后端技术栈

- Python
- FastAPI
- faster-whisper
- FFmpeg
- WebSockets

### 前端技术栈

- Next.js
- React
- TypeScript
- Tailwind CSS
- Axios
- React Dropzone
- React Player

### 浏览器插件技术栈

- JavaScript
- Chrome/Firefox 扩展 API
- WebSockets

## 项目结构

```
whisper-web/
├── server/             # 后端服务
│   ├── app/            # FastAPI 应用
│   ├── requirements.txt # Python 依赖
│   ├── run.py          # 启动脚本
│   └── .env            # 环境变量
├── web/                # 前端应用
│   ├── src/            # 源代码
│   ├── public/         # 静态资源
│   └── package.json    # Node.js 依赖
└── extension/          # 浏览器插件
    ├── manifest.json   # 插件配置
    ├── popup.html      # 弹出窗口
    └── content.js      # 内容脚本
```

## 常见问题

1. **Q: 转录速度很慢怎么办？**  
   A: 尝试使用较小的模型（tiny 或 base），或者启用 GPU 加速（在 .env 文件中设置 DEVICE=cuda）。

2. **Q: 字幕准确度不高怎么办？**  
   A: 尝试使用较大的模型（medium 或 large），或者指定正确的语言而不是使用自动检测。

3. **Q: 浏览器插件无法访问视频音频怎么办？**  
   A: 某些网站出于安全原因限制了媒体访问。尝试在不同的网站上使用，或者使用 Web 应用上传视频。

## 贡献指南

欢迎贡献代码、报告问题或提出改进建议！请遵循以下步骤：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 提供基础语音识别模型
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - 提供优化的 Whisper 实现
- [FastAPI](https://fastapi.tiangolo.com/) - 提供高性能 API 框架
- [Next.js](https://nextjs.org/) - 提供 React 框架
