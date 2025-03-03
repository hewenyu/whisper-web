# Whisper Web 浏览器插件

为网页视频添加实时字幕的Chrome/Firefox扩展。

## 功能

- 自动检测网页中的视频元素
- 提取视频音频流并发送到Whisper Web服务器进行处理
- 在视频上显示实时字幕
- 支持多语言
- 可自定义字幕样式和位置

## 安装

### Chrome

1. 打开Chrome扩展页面 `chrome://extensions/`
2. 启用"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择本目录

### Firefox

1. 打开Firefox扩展页面 `about:debugging#/runtime/this-firefox`
2. 点击"临时载入附加组件"
3. 选择本目录中的`manifest.json`文件

## 使用方法

1. 确保Whisper Web服务器已启动
2. 点击浏览器工具栏中的Whisper Web图标
3. 在弹出窗口中设置服务器地址和其他选项
4. 点击"激活字幕"按钮
5. 浏览包含视频的网页，视频右上角会出现字幕控制按钮
6. 点击"开始字幕"按钮开始生成字幕

## 设置选项

- **服务器地址**: Whisper Web服务器的URL
- **语言**: 视频音频的语言（自动检测或指定语言）
- **字幕位置**: 字幕显示在视频的顶部或底部
- **字体大小**: 字幕文本的大小

## 注意事项

- 插件需要访问视频音频流，某些网站可能会阻止此操作
- 实时字幕生成需要较好的网络连接和服务器性能
- 字幕准确度取决于Whisper模型和音频质量

## 开发

### 项目结构

- `manifest.json`: 插件配置文件
- `popup.html/js/css`: 弹出窗口界面
- `background.js`: 后台脚本
- `content.js/css`: 内容脚本，处理网页中的视频
- `subtitles.js`: 字幕处理库

### 构建和打包

```bash
# 打包Chrome扩展
zip -r whisper-web-chrome.zip * -x "*.git*"

# 打包Firefox扩展
web-ext build
``` 