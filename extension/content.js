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
  // 生成唯一ID
  const videoId = 'video-' + Math.random().toString(36).substr(2, 9);
  video.dataset.whisperId = videoId;
  
  log(`设置视频元素 [${videoId}]`);
  
  // 创建字幕容器
  const subtitleContainer = document.createElement('div');
  subtitleContainer.className = `whisper-web-subtitle-container ${settings.subtitlePosition}`;
  subtitleContainer.style.display = 'none';
  subtitleContainer.style.zIndex = '9999';  // 确保字幕在最上层
  
  // 创建字幕元素
  const subtitle = document.createElement('div');
  subtitle.className = 'whisper-web-subtitle';
  subtitle.style.fontSize = `${settings.fontSize}px`;
  subtitle.textContent = '字幕将在这里显示';  // 添加默认文本
  
  subtitleContainer.appendChild(subtitle);
  subtitleContainers[videoId] = subtitleContainer;
  
  log(`创建字幕容器 [${videoId}]`);
  
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
  
  // 确保字幕容器在视频上方正确显示
  subtitleContainer.style.position = 'absolute';
  subtitleContainer.style.left = '0';
  subtitleContainer.style.width = '100%';
  subtitleContainer.style.textAlign = 'center';
  
  videoContainer.appendChild(subtitleContainer);
  videoContainer.appendChild(controls);
  
  // 存储引用
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
    
    // 显示测试字幕，验证字幕显示功能
    updateSubtitle(videoId, '正在连接字幕服务...');
    
    // 创建WebSocket连接
    const serverUrl = settings.serverUrl.replace(/^https?:\/\//, '');
    log('使用服务器URL: ' + serverUrl);
    
    // 确保使用正确的端口
    let wsUrl;
    if (serverUrl.includes(':')) {
      wsUrl = `ws://${serverUrl}/ws/transcribe/${videoId}`;
    } else {
      // 默认使用8000端口
      wsUrl = `ws://${serverUrl}:8000/ws/transcribe/${videoId}`;
    }
    
    log('连接WebSocket: ' + wsUrl);
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer'; // 确保正确处理二进制数据
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
      
      // 检查浏览器支持的MIME类型
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = '';
          log('警告: 浏览器不支持WebM格式，将使用默认格式');
        } else {
          log('使用音频格式: audio/webm');
        }
      } else {
        log('使用音频格式: audio/webm;codecs=opus');
      }
      
      const mediaRecorderOptions = {
        audioBitsPerSecond: 128000
      };
      
      if (mimeType) {
        mediaRecorderOptions.mimeType = mimeType;
      }
      
      // 确保音频流正确创建
      const audioStream = createAudioStreamTrack(audioCtx, processor);
      if (!audioStream) {
        log('无法创建音频流');
        updateSubtitle(videoId, '无法创建音频流，请重试');
        stopProcessing(video, videoId);
        return;
      }
      
      const mediaRecorder = new MediaRecorder(new MediaStream([audioStream]), mediaRecorderOptions);
      mediaRecorders[videoId] = mediaRecorder;
      
      // 处理音频数据
      processor.onaudioprocess = function(e) {
        if (mediaRecorder.state === 'recording') {
          analyser.getByteTimeDomainData(new Uint8Array(analyser.frequencyBinCount));
        }
      };
      
      // 发送录制的数据
      mediaRecorder.ondataavailable = function(e) {
        if (e.data.size > 0) {
          if (ws.readyState === WebSocket.OPEN) {
            log(`发送音频数据: ${e.data.size} 字节`);
            ws.send(e.data);
          } else {
            log(`WebSocket未连接，无法发送音频数据: ${e.data.size} 字节`);
          }
        } else {
          log('录制的音频数据为空');
        }
      };
      
      // 开始录制
      mediaRecorder.start(1000);
      log('开始录制音频，每1000ms发送一次');
      
      // 更新控件
      const controls = controlsElements[videoId];
      controls.querySelector('button').textContent = '停止字幕';
    };
    
    ws.onmessage = function(event) {
      try {
        // 检查数据类型
        if (typeof event.data === 'string') {
          log('收到WebSocket文本消息: ' + event.data.substring(0, 100) + (event.data.length > 100 ? '...' : ''));
          
          try {
            const data = JSON.parse(event.data);
            
            log('解析的JSON类型: ' + data.type);
            
            if (data.type === 'interim_result' || data.type === 'final_result') {
              log('收到字幕结果类型: ' + data.type);
              if (data.segments && data.segments.length > 0) {
                // 显示最后一段文本
                const lastSegment = data.segments[data.segments.length - 1];
                log('收到字幕文本: ' + lastSegment.text);
                updateSubtitle(videoId, lastSegment.text);
              } else {
                log('收到的字幕段落为空');
              }
            } else if (data.type === 'error') {
              log('错误: ' + data.message);
              updateSubtitle(videoId, '字幕服务错误，请重试');
              stopProcessing(video, videoId);
            } else {
              log('收到未知类型的消息: ' + data.type);
            }
          } catch (jsonError) {
            log('解析JSON时出错: ' + jsonError.message);
            log('原始消息: ' + event.data);
          }
        } else if (event.data instanceof ArrayBuffer) {
          log('收到WebSocket二进制消息: ' + event.data.byteLength + ' 字节');
        } else if (event.data instanceof Blob) {
          log('收到WebSocket Blob消息: ' + event.data.size + ' 字节');
        } else {
          log('收到未知类型的WebSocket消息: ' + typeof event.data);
        }
      } catch (error) {
        log('处理WebSocket消息时出错: ' + error.message);
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
      // 使用TextEncoder替代Node.js的Buffer
      log('发送END_OF_AUDIO信号');
      const encoder = new TextEncoder();
      websockets[videoId].send('END_OF_AUDIO');  // 直接发送字符串，而不是二进制数据
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
  log(`更新字幕 [${videoId}]: "${text}"`);
  
  const subtitleContainer = subtitleContainers[videoId];
  if (subtitleContainer) {
    const subtitle = subtitleContainer.querySelector('.whisper-web-subtitle');
    
    // 确保文本内容被正确设置
    if (text && text.trim() !== '') {
      subtitle.textContent = text.trim();
      subtitleContainer.style.display = 'block';
      
      // 检查字幕容器是否可见
      setTimeout(() => {
        const isVisible = subtitleContainer.offsetWidth > 0 && subtitleContainer.offsetHeight > 0;
        log(`字幕容器可见性 [${videoId}]: ${isVisible ? '可见' : '不可见'}`);
        
        if (!isVisible) {
          log('字幕容器不可见，尝试强制显示');
          subtitleContainer.style.display = 'block';
          subtitleContainer.style.visibility = 'visible';
          subtitleContainer.style.opacity = '1';
        }
      }, 100);
      
      log(`字幕已显示 [${videoId}]`);
    } else {
      subtitle.textContent = '';
      subtitleContainer.style.display = 'none';
      log(`字幕已隐藏 [${videoId}]`);
    }
  } else {
    log(`未找到字幕容器 [${videoId}]`);
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
    log('开始创建音频流轨道');
    const dest = audioContext.createMediaStreamDestination();
    processor.connect(dest);
    
    const tracks = dest.stream.getAudioTracks();
    log(`创建的音频轨道数量: ${tracks.length}`);
    
    if (tracks.length === 0) {
      log('警告: 未能创建音频轨道');
      return null;
    }
    
    log(`音频轨道已创建: ${tracks[0].label}`);
    return tracks[0];
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