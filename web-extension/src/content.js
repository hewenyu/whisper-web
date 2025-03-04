// 存储当前页面的视频元素和字幕信息
let currentVideoElement = null;
let currentSubtitles = null;
let currentTrack = null;

// 监听来自弹出窗口的消息
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === 'generateSubtitles') {
    console.log('收到生成字幕请求:', request.settings);
    
    // 处理生成字幕的请求
    handleGenerateSubtitles(request.settings)
      .then(response => {
        console.log('字幕生成完成:', response);
        sendResponse(response);
      })
      .catch(error => {
        console.error('字幕生成失败:', error);
        sendResponse({
          success: false,
          message: error.message
        });
      });
    
    // 返回true表示将异步发送响应
    return true;
  }
});

// 处理生成字幕的请求
async function handleGenerateSubtitles(settings) {
  try {
    console.log('开始处理字幕生成请求，设置:', settings);
    
    // 查找页面中的视频元素
    const videoElement = findMainVideoElement();
    
    if (!videoElement) {
      throw new Error('未找到视频元素');
    }
    
    console.log('找到视频元素:', videoElement);
    currentVideoElement = videoElement;
    
    // 获取视频URL
    const videoUrl = window.location.href;
    const videoId = generateVideoId(videoUrl);
    console.log('视频信息:', { url: videoUrl, id: videoId });
    
    // 显示加载状态
    showLoadingOverlay(videoElement, '正在提取音频...');
    
    // 发送消息到后台脚本提取音频
    console.log('开始提取音频...');
    const extractResponse = await sendMessageToBackground({
      action: 'extractAudio',
      videoUrl: videoUrl,
      videoId: videoId,
      serverUrl: settings.serverUrl
    });
    
    console.log('音频提取响应:', extractResponse);
    
    if (!extractResponse.success) {
      throw new Error(extractResponse.message);
    }
    
    // 更新加载状态
    updateLoadingOverlay('正在转录音频...');
    
    // 发送消息到后台脚本进行转录
    console.log('开始转录音频，文件UUID:', extractResponse.fileUuid);
    const transcribeResponse = await sendMessageToBackground({
      action: 'transcribe',
      fileUuid: extractResponse.fileUuid,
      serverUrl: settings.serverUrl
    });
    
    console.log('转录响应:', transcribeResponse);
    
    if (!transcribeResponse.success) {
      throw new Error(transcribeResponse.message);
    }
    
    // 保存字幕数据
    currentSubtitles = transcribeResponse.subtitleFile;
    
    // 将字幕添加到视频
    console.log('添加字幕到视频...');
    addSubtitlesToVideo(videoElement, transcribeResponse.subtitleFile, settings.format);
    
    // 移除加载状态
    removeLoadingOverlay();
    
    return {
      success: true,
      message: '字幕生成成功'
    };
  } catch (error) {
    console.error('生成字幕时出错:', error);
    removeLoadingOverlay();
    throw error;
  }
}

// 查找页面中的主要视频元素
function findMainVideoElement() {
  const videos = document.querySelectorAll('video');
  
  if (videos.length === 0) {
    return null;
  }
  
  // 如果只有一个视频元素，直接返回
  if (videos.length === 1) {
    return videos[0];
  }
  
  // 如果有多个视频元素，尝试找到最大的一个
  let largestVideo = videos[0];
  let largestArea = getVideoArea(videos[0]);
  
  for (let i = 1; i < videos.length; i++) {
    const area = getVideoArea(videos[i]);
    if (area > largestArea) {
      largestArea = area;
      largestVideo = videos[i];
    }
  }
  
  return largestVideo;
}

// 计算视频元素的面积
function getVideoArea(video) {
  const rect = video.getBoundingClientRect();
  return rect.width * rect.height;
}

// 生成视频ID
function generateVideoId(url) {
  // 简单地使用URL的哈希值作为ID
  let hash = 0;
  for (let i = 0; i < url.length; i++) {
    const char = url.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // 转换为32位整数
  }
  return 'video_' + Math.abs(hash).toString(16);
}

// 发送消息到后台脚本
function sendMessageToBackground(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, response => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

// 将字幕添加到视频
function addSubtitlesToVideo(videoElement, subtitleContent, format) {
  try {
    console.log(`添加字幕到视频`);
    
    // 移除现有的字幕轨道
    removeExistingTracks(videoElement);
    
    // 确保字幕内容不为空
    if (!subtitleContent || subtitleContent.trim() === '') {
      console.error('字幕内容为空');
      throw new Error('字幕内容为空');
    }
    
    // 检测字幕格式
    let detectedFormat = 'vtt';
    if (subtitleContent.trim().startsWith('WEBVTT')) {
      detectedFormat = 'vtt';
    } else if (subtitleContent.trim().match(/^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}/)) {
      detectedFormat = 'srt';
    } else if (subtitleContent.trim().startsWith('[') || subtitleContent.trim().startsWith('{')) {
      detectedFormat = 'json';
    }
    
    console.log('检测到字幕格式:', detectedFormat);
    
    // 根据格式确定MIME类型
    let mimeType;
    switch (detectedFormat) {
      case 'vtt':
        mimeType = 'text/vtt';
        break;
      case 'srt':
        mimeType = 'application/x-subrip';
        break;
      case 'json':
        mimeType = 'application/json';
        break;
      default:
        mimeType = 'text/vtt';
    }
    
    console.log('创建Blob URL，MIME类型:', mimeType);
    
    // 创建Blob URL
    const blob = new Blob([subtitleContent], { type: mimeType });
    const subtitleUrl = URL.createObjectURL(blob);
    
    // 创建字幕轨道
    const track = document.createElement('track');
    track.kind = 'subtitles';
    track.label = '自动生成的字幕';
    track.srclang = 'zh';
    track.src = subtitleUrl;
    track.default = true;
    
    // 保存当前轨道引用以便后续清理
    currentTrack = track;
    
    // 添加到视频
    videoElement.appendChild(track);
    console.log('字幕轨道已添加到视频');
    
    // 确保字幕显示
    setTimeout(() => {
      try {
        if (videoElement.textTracks && videoElement.textTracks.length > 0) {
          videoElement.textTracks[0].mode = 'showing';
          console.log('字幕已设置为显示模式');
        } else {
          console.warn('未找到文本轨道');
        }
      } catch (e) {
        console.error('设置字幕显示模式时出错:', e);
      }
    }, 100);
  } catch (error) {
    console.error('添加字幕到视频时出错:', error);
    throw error;
  }
}

// 移除现有的字幕轨道
function removeExistingTracks(videoElement) {
  const tracks = videoElement.querySelectorAll('track');
  tracks.forEach(track => {
    if (track.parentNode === videoElement) {
      videoElement.removeChild(track);
    }
  });
  
  // 如果有之前创建的轨道，释放其资源
  if (currentTrack && currentTrack.src) {
    URL.revokeObjectURL(currentTrack.src);
    currentTrack = null;
  }
}

// 显示加载状态覆盖层
function showLoadingOverlay(videoElement, message) {
  // 移除现有的覆盖层
  removeLoadingOverlay();
  
  // 创建覆盖层
  const overlay = document.createElement('div');
  overlay.id = 'subtitle-loading-overlay';
  overlay.style.position = 'absolute';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.width = '100%';
  overlay.style.height = '100%';
  overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
  overlay.style.color = 'white';
  overlay.style.display = 'flex';
  overlay.style.justifyContent = 'center';
  overlay.style.alignItems = 'center';
  overlay.style.zIndex = '9999';
  overlay.style.fontFamily = 'Arial, sans-serif';
  
  // 创建加载消息
  const messageElement = document.createElement('div');
  messageElement.id = 'subtitle-loading-message';
  messageElement.textContent = message;
  messageElement.style.padding = '20px';
  messageElement.style.borderRadius = '5px';
  messageElement.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
  
  // 添加到覆盖层
  overlay.appendChild(messageElement);
  
  // 获取视频容器
  const videoContainer = videoElement.parentElement;
  
  // 设置容器为相对定位，以便覆盖层可以正确定位
  if (videoContainer) {
    const originalPosition = window.getComputedStyle(videoContainer).position;
    if (originalPosition === 'static') {
      videoContainer.style.position = 'relative';
    }
    videoContainer.appendChild(overlay);
  } else {
    // 如果没有父容器，直接添加到视频元素旁边
    const videoRect = videoElement.getBoundingClientRect();
    overlay.style.position = 'fixed';
    overlay.style.top = `${videoRect.top}px`;
    overlay.style.left = `${videoRect.left}px`;
    overlay.style.width = `${videoRect.width}px`;
    overlay.style.height = `${videoRect.height}px`;
    document.body.appendChild(overlay);
  }
}

// 更新加载状态消息
function updateLoadingOverlay(message) {
  const messageElement = document.getElementById('subtitle-loading-message');
  if (messageElement) {
    messageElement.textContent = message;
  }
}

// 移除加载状态覆盖层
function removeLoadingOverlay() {
  const overlay = document.getElementById('subtitle-loading-overlay');
  if (overlay) {
    overlay.parentElement.removeChild(overlay);
  }
} 