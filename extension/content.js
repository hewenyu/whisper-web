// 全局变量
let isActive = false;
let settings = {
  serverUrl: 'http://localhost:8000',
  language: 'auto',
  subtitlePosition: 'bottom',
  fontSize: '20'
};
let videoElements = [];
let subtitleContainers = {};
let controlsElements = {};
let websockets = {};
let audioContexts = {};
let mediaRecorders = {};
let processingStatus = {};

// 初始化
function init() {
  // 获取当前状态和设置
  chrome.runtime.sendMessage({ action: 'getStatus' }, function(response) {
    isActive = response.isActive;
    settings = response.settings;
    
    // 如果已激活，则扫描视频元素
    if (isActive) {
      scanForVideos();
    }
  });
  
  // 监听来自弹出窗口的消息
  chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.action === 'activate') {
      isActive = true;
      settings = request.settings;
      scanForVideos();
      sendResponse({ success: true });
    }
    
    if (request.action === 'deactivate') {
      isActive = false;
      removeAllSubtitles();
      sendResponse({ success: true });
    }
    
    if (request.action === 'updateSettings') {
      settings = request.settings;
      updateSubtitleStyles();
      sendResponse({ success: true });
    }
  });
  
  // 监听DOM变化，检测新的视频元素
  const observer = new MutationObserver(function(mutations) {
    if (isActive) {
      scanForVideos();
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

// 扫描页面中的视频元素
function scanForVideos() {
  const videos = document.querySelectorAll('video');
  
  videos.forEach(function(video) {
    // 如果该视频元素尚未处理
    if (!videoElements.includes(video)) {
      videoElements.push(video);
      setupVideoElement(video);
    }
  });
}

// 为视频元素设置字幕和控制
function setupVideoElement(video) {
  const videoId = 'whisper-web-' + Math.random().toString(36).substr(2, 9);
  
  // 创建字幕容器
  const subtitleContainer = document.createElement('div');
  subtitleContainer.className = `whisper-web-subtitle-container ${settings.subtitlePosition}`;
  subtitleContainer.id = `subtitle-${videoId}`;
  
  // 创建字幕元素
  const subtitle = document.createElement('div');
  subtitle.className = 'whisper-web-subtitle';
  subtitle.style.fontSize = `${settings.fontSize}px`;
  subtitle.textContent = '';
  
  subtitleContainer.appendChild(subtitle);
  
  // 创建控制元素
  const controls = document.createElement('div');
  controls.className = 'whisper-web-controls';
  controls.id = `controls-${videoId}`;
  
  const statusIndicator = document.createElement('span');
  statusIndicator.className = 'whisper-web-status inactive';
  
  const toggleButton = document.createElement('button');
  toggleButton.textContent = '开始字幕';
  toggleButton.addEventListener('click', function() {
    if (processingStatus[videoId]) {
      stopProcessing(video, videoId);
    } else {
      startProcessing(video, videoId);
    }
  });
  
  controls.appendChild(statusIndicator);
  controls.appendChild(toggleButton);
  
  // 将元素添加到视频容器
  const videoContainer = video.parentElement;
  videoContainer.style.position = 'relative';
  videoContainer.appendChild(subtitleContainer);
  videoContainer.appendChild(controls);
  
  // 存储引用
  subtitleContainers[videoId] = subtitleContainer;
  controlsElements[videoId] = controls;
  processingStatus[videoId] = false;
  
  // 监听视频播放/暂停事件
  video.addEventListener('play', function() {
    if (processingStatus[videoId]) {
      resumeProcessing(video, videoId);
    }
  });
  
  video.addEventListener('pause', function() {
    if (processingStatus[videoId]) {
      pauseProcessing(videoId);
    }
  });
  
  video.addEventListener('ended', function() {
    if (processingStatus[videoId]) {
      stopProcessing(video, videoId);
    }
  });
}

// 开始处理视频音频
function startProcessing(video, videoId) {
  try {
    // 更新状态
    processingStatus[videoId] = true;
    updateControlsStatus(videoId, 'processing');
    
    // 创建WebSocket连接
    const serverUrl = settings.serverUrl.replace(/^https?:\/\//, '');
    const ws = new WebSocket(`ws://${serverUrl}/ws/transcribe/${videoId}`);
    websockets[videoId] = ws;
    
    ws.onopen = function() {
      log('WebSocket连接已建立');
      
      // 创建音频上下文
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioContexts[videoId] = audioCtx;
      
      // 创建媒体源
      const source = audioCtx.createMediaElementSource(video);
      
      // 创建分析器
      const analyser = audioCtx.createAnalyser();
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
      
      // 创建处理器
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processor.connect(audioCtx.destination);
      
      // 创建媒体录制器
      const options = {
        audioBitsPerSecond: 128000,
        mimeType: 'audio/webm;codecs=opus'
      };
      
      // 确保音频流正确创建
      const audioStream = createAudioStreamTrack(audioCtx, processor);
      if (!audioStream) {
        log('无法创建音频流');
        updateSubtitle(videoId, '无法创建音频流，请重试');
        stopProcessing(video, videoId);
        return;
      }
      
      const mediaRecorder = new MediaRecorder(new MediaStream([audioStream]), options);
      mediaRecorders[videoId] = mediaRecorder;
      
      // 处理音频数据
      processor.onaudioprocess = function(e) {
        if (mediaRecorder.state === 'recording') {
          analyser.getByteTimeDomainData(new Uint8Array(analyser.frequencyBinCount));
        }
      };
      
      // 发送录制的数据
      mediaRecorder.ondataavailable = function(e) {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      
      // 开始录制
      mediaRecorder.start(1000);
      
      // 更新控件
      const controls = controlsElements[videoId];
      controls.querySelector('button').textContent = '停止字幕';
    };
    
    ws.onmessage = function(event) {
      const data = JSON.parse(event.data);
      
      if (data.type === 'interim_result' || data.type === 'final_result') {
        if (data.segments && data.segments.length > 0) {
          // 显示最后一段文本
          const lastSegment = data.segments[data.segments.length - 1];
          updateSubtitle(videoId, lastSegment.text);
          log('收到字幕: ' + lastSegment.text);
        }
      } else if (data.type === 'error') {
        log('错误: ' + data.message);
        updateSubtitle(videoId, '字幕服务错误，请重试');
        stopProcessing(video, videoId);
      }
    };
    
    ws.onerror = function(error) {
      log('WebSocket错误: ' + error);
      updateSubtitle(videoId, '连接字幕服务失败');
      stopProcessing(video, videoId);
    };
    
    ws.onclose = function() {
      log('WebSocket连接已关闭');
      if (processingStatus[videoId]) {
        stopProcessing(video, videoId);
      }
    };
  } catch (error) {
    log('启动处理时出错: ' + error.message);
    updateSubtitle(videoId, '启动字幕服务失败');
    stopProcessing(video, videoId);
  }
}

// 暂停处理
function pauseProcessing(videoId) {
  if (mediaRecorders[videoId] && mediaRecorders[videoId].state === 'recording') {
    mediaRecorders[videoId].pause();
  }
}

// 恢复处理
function resumeProcessing(video, videoId) {
  if (mediaRecorders[videoId] && mediaRecorders[videoId].state === 'paused') {
    mediaRecorders[videoId].resume();
  } else if (processingStatus[videoId] && (!mediaRecorders[videoId] || mediaRecorders[videoId].state === 'inactive')) {
    startProcessing(video, videoId);
  }
}

// 停止处理
function stopProcessing(video, videoId) {
  processingStatus[videoId] = false;
  updateControlsStatus(videoId, 'inactive');
  
  // 停止媒体录制器
  if (mediaRecorders[videoId]) {
    if (mediaRecorders[videoId].state !== 'inactive') {
      mediaRecorders[videoId].stop();
    }
    delete mediaRecorders[videoId];
  }
  
  // 关闭音频上下文
  if (audioContexts[videoId]) {
    audioContexts[videoId].close();
    delete audioContexts[videoId];
  }
  
  // 关闭WebSocket连接
  if (websockets[videoId]) {
    if (websockets[videoId].readyState === WebSocket.OPEN) {
      websockets[videoId].send(new Uint8Array(Buffer.from('END_OF_AUDIO')));
      websockets[videoId].close();
    }
    delete websockets[videoId];
  }
  
  // 更新控件
  const controls = controlsElements[videoId];
  if (controls) {
    controls.querySelector('button').textContent = '开始字幕';
  }
  
  // 清除字幕
  updateSubtitle(videoId, '');
}

// 更新字幕
function updateSubtitle(videoId, text) {
  const subtitleContainer = subtitleContainers[videoId];
  if (subtitleContainer) {
    const subtitle = subtitleContainer.querySelector('.whisper-web-subtitle');
    
    // 确保文本内容被正确设置
    if (text && text.trim() !== '') {
      subtitle.textContent = text.trim();
      subtitleContainer.style.display = 'block';
    } else {
      subtitle.textContent = '';
      subtitleContainer.style.display = 'none';
    }
  }
}

// 更新控件状态
function updateControlsStatus(videoId, status) {
  const controls = controlsElements[videoId];
  if (controls) {
    const statusIndicator = controls.querySelector('.whisper-web-status');
    statusIndicator.className = `whisper-web-status ${status}`;
  }
}

// 更新所有字幕样式
function updateSubtitleStyles() {
  for (const videoId in subtitleContainers) {
    const container = subtitleContainers[videoId];
    container.className = `whisper-web-subtitle-container ${settings.subtitlePosition}`;
    
    const subtitle = container.querySelector('.whisper-web-subtitle');
    subtitle.style.fontSize = `${settings.fontSize}px`;
  }
}

// 移除所有字幕和控件
function removeAllSubtitles() {
  // 停止所有处理
  videoElements.forEach(function(video) {
    for (const videoId in processingStatus) {
      if (processingStatus[videoId]) {
        stopProcessing(video, videoId);
      }
    }
  });
  
  // 移除所有字幕容器和控件
  for (const videoId in subtitleContainers) {
    const container = subtitleContainers[videoId];
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
    
    const controls = controlsElements[videoId];
    if (controls && controls.parentNode) {
      controls.parentNode.removeChild(controls);
    }
  }
  
  // 清空引用
  videoElements = [];
  subtitleContainers = {};
  controlsElements = {};
  processingStatus = {};
}

// 创建音频流轨道
function createAudioStreamTrack(audioContext, processor) {
  try {
    const dest = audioContext.createMediaStreamDestination();
    processor.connect(dest);
    return dest.stream.getAudioTracks()[0];
  } catch (error) {
    log('创建音频流轨道时出错: ' + error.message);
    return null;
  }
}

// 日志函数
function log(message) {
  console.log('[Whisper Web]', message);
  chrome.runtime.sendMessage({ action: 'log', message: message });
}

// 初始化插件
init(); 