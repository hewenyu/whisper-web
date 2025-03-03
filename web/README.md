# Whisper Web 前端应用

基于Next.js的视频字幕生成Web应用，使用Whisper模型进行语音识别。

## 功能

- 视频上传和处理
- 实时字幕生成
- 多语言支持
- 字幕预览和下载
- 响应式设计，适配各种设备

## 技术栈

- Next.js
- React
- TypeScript
- Tailwind CSS
- Axios
- React Dropzone
- React Player

## 安装和运行

1. 安装依赖：

```bash
npm install
# 或
yarn install
```

2. 开发模式运行：

```bash
npm run dev
# 或
yarn dev
```

应用将在 http://localhost:3000 启动。

## 构建和部署

1. 构建应用：

```bash
npm run build
# 或
yarn build
```

2. 启动生产服务器：

```bash
npm run start
# 或
yarn start
```

## 环境变量

在项目根目录创建`.env.local`文件，设置以下环境变量：

```
API_URL=http://localhost:8000  # 后端API地址
```

## 项目结构

- `src/components/`: React组件
- `src/pages/`: Next.js页面
- `src/services/`: API服务和工具函数
- `src/styles/`: 全局样式和Tailwind配置
- `public/`: 静态资源

## 与后端集成

前端应用通过API与Whisper Web后端服务通信，确保后端服务已启动并可访问。默认后端地址为`http://localhost:8000`。 