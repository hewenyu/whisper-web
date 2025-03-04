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
// 跟踪哪些视频元素已经连接到音频上下文
let connectedVideoElements = {};
// 存储处理器节点
let processorNodes = {};
// 存储音频处理器
let audioProcessors = {};
// 跟踪字幕是否应该被显示
let subtitleEnabled = {};

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
  
  // 监听页面卸载事件，确保清理资源
  window.addEventListener('beforeunload', function() {
    log('页面即将卸载，清理资源');
    removeAllSubtitles();
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
  
  // 保存控件元素引用
  controlsElements[videoId] = controls;
  
  // 将字幕容器和控制元素添加到视频容器
  let videoContainer = video.parentElement;
  
  // 对于YouTube，尝试找到正确的容器
  if (window.location.hostname.includes('youtube.com')) {
    // 查找YouTube播放器容器
    const ytContainer = video.closest('.html5-video-player');
    if (ytContainer) {
      videoContainer = ytContainer;
    }
  }
  
  // 如果找不到容器，使用body
  if (!videoContainer) {
    videoContainer = document.body;
  }
  
  // 设置字幕容器样式
  subtitleContainer.style.position = 'absolute';
  subtitleContainer.style.zIndex = '2147483647'; // 最大z-index值
  
  videoContainer.appendChild(subtitleContainer);
  videoContainer.appendChild(controls);
  
  // 初始化字幕启用状态
  subtitleEnabled[videoId] = false;
  
  // 设置音频处理 - 在这里创建音频上下文和处理器，但默认不处理数据
  setupAudioProcessor(video, videoId);
  
  // 监听视频事件
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

// 设置音频处理器
function setupAudioProcessor(video, videoId) {
  try {
    // 检查视频元素是否有效
    if (!video || !video.tagName || video.tagName.toLowerCase() !== 'video') {
      log(`无效的视频元素 [${videoId}]`);
      return;
    }
    
    // 如果已经设置了音频处理器，则不重复设置
    if (audioProcessors[videoId]) {
      log(`音频处理器 [${videoId}] 已存在`);
      return;
    }
    
    log(`设置音频处理器 [${videoId}]`);
    
    // 创建音频上下文
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 16000 // 使用16kHz采样率，与服务器期望的一致
    });
    audioContexts[videoId] = audioCtx;
    
    // 创建媒体源
    const source = audioCtx.createMediaElementSource(video);
    
    // 创建分析器节点
    const analyser = audioCtx.createAnalyser();
    
    // 创建脚本处理器节点
    const bufferSize = 4096;
    const processorNode = audioCtx.createScriptProcessor(bufferSize, 1, 1);
    
    // 连接节点 - 确保音频同时输出到扬声器和处理节点
    // 源 -> 分析器 -> 目标(扬声器)
    source.connect(analyser);
    analyser.connect(audioCtx.destination);
    
    // 源 -> 处理器 -> 目标(用于处理，不连接到扬声器)
    source.connect(processorNode);
    // 处理器需要连接到目标，但我们使用一个静音的增益节点，这样不会影响原始音频
    const silentGain = audioCtx.createGain();
    silentGain.gain.value = 0; // 设置增益为0，完全静音
    processorNode.connect(silentGain);
    silentGain.connect(audioCtx.destination);
    
    // 设置音频处理函数 - 默认不做任何处理
    processorNode.onaudioprocess = function(e) {
      // 默认不处理数据，只在active为true时处理
      // 这个函数会在startProcessing中被替换
    };
    
    // 保存音频处理器
    audioProcessors[videoId] = {
      audioCtx: audioCtx,
      source: source,
      analyser: analyser,
      processorNode: processorNode,
      silentGain: silentGain,
      active: false
    };
    
    // 保存处理器节点引用
    processorNodes[videoId] = processorNode;
    
    // 标记视频元素已连接
    connectedVideoElements[videoId] = true;
    
    log(`音频处理器 [${videoId}] 设置完成`);
  } catch (error) {
    log(`设置音频处理器时出错 [${videoId}]: ${error.message}`);
  }
}

// 开始处理视频音频
function startProcessing(video, videoId) {
  try {
    // 检查视频元素是否有效
    if (!video || !video.tagName || video.tagName.toLowerCase() !== 'video') {
      log(`无效的视频元素 [${videoId}]`);
      return;
    }
    
    // 检查视频是否有音轨
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      log(`视频元素 [${videoId}] 尚未加载`);
      updateSubtitle(videoId, '等待视频加载...');
      // 等待视频加载
      const checkVideo = setInterval(() => {
        if (video.videoWidth > 0 && video.videoHeight > 0) {
          clearInterval(checkVideo);
          startProcessing(video, videoId);
        }
      }, 1000);
      return;
    }
    
    // 检查音频处理器是否已设置
    if (!audioProcessors[videoId]) {
      log(`音频处理器 [${videoId}] 不存在，尝试设置`);
      setupAudioProcessor(video, videoId);
      
      // 如果仍然无法设置，则退出
      if (!audioProcessors[videoId]) {
        log(`无法设置音频处理器 [${videoId}]`);
        updateSubtitle(videoId, '无法设置音频处理，请刷新页面后重试');
        return;
      }
    }
    
    // 更新状态
    processingStatus[videoId] = true;
    // 设置字幕启用标志
    subtitleEnabled[videoId] = true;
    updateControlsStatus(videoId, 'processing');
    
    // 立即更新按钮文本
    const controls = controlsElements[videoId];
    if (controls) {
      const button = controls.querySelector('button');
      if (button) {
        button.textContent = '停止字幕';
      }
    }
    
    // 显示连接中的提示
    updateSubtitle(videoId, '正在连接字幕服务...');
    
    // 检查服务器状态
    const serverUrl = settings.serverUrl.replace(/^https?:\/\//, '');
    log('检查服务器状态: ' + serverUrl);
    
    // 创建一个临时的fetch请求来检查服务器是否在线
    fetch(`http://${serverUrl}/health`, { 
      method: 'GET',
      mode: 'no-cors' // 使用no-cors模式避免CORS问题
    })
    .then(response => {
      log('服务器状态检查响应: ' + response.status);
    })
    .catch(error => {
      log('服务器状态检查错误: ' + error.message);
      // 显示警告但继续尝试连接WebSocket
      updateSubtitle(videoId, '警告: 服务器连接检查失败，但仍将尝试连接');
    });
    
    // 创建WebSocket连接
    const wsUrl = settings.serverUrl.replace(/^https?:\/\//, '');
    log('使用服务器URL: ' + wsUrl);
    
    // 确保使用正确的端口
    let wsUrlFinal;
    if (wsUrl.includes(':')) {
      wsUrlFinal = `ws://${wsUrl}/ws/stream/${videoId}`;
    } else {
      // 默认使用8000端口
      wsUrlFinal = `ws://${wsUrl}:8000/ws/stream/${videoId}`;
    }
    
    log('连接WebSocket: ' + wsUrlFinal);
    const ws = new WebSocket(wsUrlFinal);
    ws.binaryType = 'arraybuffer'; // 确保正确处理二进制数据
    websockets[videoId] = ws;
    
    ws.onopen = function() {
      log('WebSocket连接已建立');
      
      // 发送测试消息，检查服务器响应
      log('发送测试消息到服务器');
      ws.send(JSON.stringify({ type: 'test', message: 'Hello from Whisper Web Extension' }));
      
      // 更新字幕，告知用户连接已建立，等待音频
      updateSubtitle(videoId, '字幕服务已连接，等待音频...');
      
      // 发送心跳消息，确保连接保持活跃
      const heartbeatInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          log('发送心跳消息');
          ws.send(JSON.stringify({ type: 'heartbeat' }));
        } else {
          clearInterval(heartbeatInterval);
        }
      }, 10000); // 每10秒发送一次
      
      // 获取音频处理器
      const processor = audioProcessors[videoId];
      
      // 设置音频处理函数 - 现在开始处理数据
      processor.processorNode.onaudioprocess = function(e) {
        if (processor.active && ws.readyState === WebSocket.OPEN) {
          // 获取输入缓冲区
          const inputBuffer = e.inputBuffer;
          // 获取第一个通道的数据
          const inputData = inputBuffer.getChannelData(0);
          
          // 转换为16位整数
          const pcmBuffer = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            // 将-1.0到1.0的浮点数转换为-32768到32767的整数
            pcmBuffer[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
          }
          
          // 发送PCM数据
          try {
            ws.send(pcmBuffer.buffer);
            log(`发送PCM音频数据: ${pcmBuffer.buffer.byteLength} 字节`);
          } catch (error) {
            log(`发送PCM音频数据时出错: ${error.message}`);
          }
        }
      };
      
      // 标记处理器为活跃状态
      processor.active = true;
      
      log('PCM音频处理已启动');
      
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
            
            // 如果字幕已被禁用，则不显示任何字幕
            if (!subtitleEnabled[videoId]) {
              log(`字幕已禁用 [${videoId}]，忽略收到的字幕数据`);
              return;
            }
            
            if (data.type === 'streaming_result') {
              log('收到流式字幕结果');
              if (data.text) {
                log('收到字幕文本: ' + data.text);
                updateSubtitle(videoId, data.text);
              } else {
                log('收到的字幕文本为空');
              }
            } else if (data.type === 'interim_result' || data.type === 'final_result') {
              log('收到字幕结果类型: ' + data.type);
              if (data.segments && data.segments.length > 0) {
                // 显示最后一段文本
                const lastSegment = data.segments[data.segments.length - 1];
                log('收到字幕文本: ' + lastSegment.text);
                updateSubtitle(videoId, lastSegment.text);
                
                // 如果是最终结果，保存所有字幕段落
                if (data.type === 'final_result') {
                  log(`收到最终字幕结果，共 ${data.segments.length} 段`);
                  // 这里可以添加保存字幕的逻辑
                }
              } else if (data.type === 'final_result') {
                // 最终结果但没有段落，可能是处理结束
                log('收到最终结果信号，但没有字幕段落');
              } else {
                log('收到的字幕段落为空');
              }
            } else if (data.type === 'error') {
              log('错误: ' + data.message);
              
              // 检查是否是音频处理错误
              if (data.message && data.message.includes('unpack requires a buffer')) {
                log('检测到音频格式错误，尝试重置处理');
                resetProcessing(video, videoId);
              } else {
                updateSubtitle(videoId, '字幕服务错误，请重试');
                stopProcessing(video, videoId);
              }
            } else if (data.type === 'test_response') {
              log('收到测试响应: ' + data.message);
              // 不再显示测试字幕
            } else if (data.type === 'heartbeat_response') {
              log('收到心跳响应: ' + data.message);
            } else if (data.type === 'info') {
              log('收到信息: ' + data.message);
            } else if (data.type === 'reset_complete') {
              log('重置完成');
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
      log('WebSocket错误: ' + JSON.stringify(error));
      
      // 尝试获取更多错误信息
      if (error.message) {
        log('错误消息: ' + error.message);
      }
      
      if (error.target && error.target.readyState) {
        log('WebSocket状态: ' + error.target.readyState);
      }
      
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
  if (audioProcessors[videoId] && audioProcessors[videoId].active) {
    // 标记处理器为非活跃状态
    audioProcessors[videoId].active = false;
    // 暂停字幕显示，但不完全禁用
    // 我们不设置subtitleEnabled[videoId] = false，因为我们希望恢复时继续显示字幕
    log(`暂停音频处理 [${videoId}]`);
  }
}

// 恢复处理
function resumeProcessing(video, videoId) {
  if (processingStatus[videoId] && audioProcessors[videoId]) {
    // 标记处理器为活跃状态
    audioProcessors[videoId].active = true;
    // 恢复字幕显示
    subtitleEnabled[videoId] = true;
    log(`恢复音频处理 [${videoId}]`);
  } else if (processingStatus[videoId]) {
    // 如果处理器不存在但处理状态为true，则重新启动处理
    startProcessing(video, videoId);
    log(`重新开始音频处理 [${videoId}]`);
  }
}

// 停止处理
function stopProcessing(video, videoId) {
  processingStatus[videoId] = false;
  // 设置字幕禁用标志
  subtitleEnabled[videoId] = false;
  updateControlsStatus(videoId, 'inactive');
  
  // 更新按钮文本
  const controls = controlsElements[videoId];
  if (controls) {
    const button = controls.querySelector('button');
    if (button) {
      button.textContent = '开始字幕';
    }
  }
  
  // 停止音频处理
  if (audioProcessors[videoId]) {
    // 重置音频处理函数为空函数
    audioProcessors[videoId].processorNode.onaudioprocess = function(e) {
      // 不处理数据
    };
    
    // 标记处理器为非活跃状态
    audioProcessors[videoId].active = false;
    
    log(`停止音频处理 [${videoId}]`);
  }
  
  // 关闭WebSocket连接
  if (websockets[videoId]) {
    if (websockets[videoId].readyState === WebSocket.OPEN) {
      // 发送结束信号
      try {
        websockets[videoId].send("END_OF_AUDIO");
        log('已发送END_OF_AUDIO信号');
      } catch (error) {
        log(`发送END_OF_AUDIO信号时出错: ${error.message}`);
      }
      
      // 给服务器一些时间处理最后的音频数据
      setTimeout(() => {
        if (websockets[videoId] && websockets[videoId].readyState === WebSocket.OPEN) {
          websockets[videoId].close();
        }
        delete websockets[videoId];
      }, 2000);
    } else {
      delete websockets[videoId];
    }
  }
  
  // 隐藏字幕 - 确保字幕完全隐藏
  updateSubtitle(videoId, "");
  
  // 直接操作字幕容器，确保它被隐藏
  const subtitleContainer = subtitleContainers[videoId];
  if (subtitleContainer) {
    subtitleContainer.style.display = 'none';
    subtitleContainer.style.visibility = 'hidden';
    log(`强制隐藏字幕容器 [${videoId}]`);
  }
}

// 更新字幕
function updateSubtitle(videoId, text) {
  log(`更新字幕 [${videoId}]: "${text}"`);
  
  // 如果字幕已被禁用，则不显示任何字幕
  if (!subtitleEnabled[videoId] && text && text.trim() !== '') {
    log(`字幕已禁用 [${videoId}]，忽略字幕更新`);
    return;
  }
  
  const subtitleContainer = subtitleContainers[videoId];
  if (subtitleContainer) {
    const subtitle = subtitleContainer.querySelector('.whisper-web-subtitle');
    
    // 确保文本内容被正确设置
    if (text && text.trim() !== '') {
      subtitle.textContent = text.trim();
      subtitleContainer.style.display = 'block';
      subtitleContainer.style.visibility = 'visible';
      subtitleContainer.style.opacity = '1';
      
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
      subtitleContainer.style.visibility = 'hidden';
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
    const videoId = video.dataset.whisperId;
    if (videoId && processingStatus[videoId]) {
      stopProcessing(video, videoId);
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
  
  // 关闭所有音频上下文
  for (const videoId in audioContexts) {
    try {
      if (audioContexts[videoId] && audioContexts[videoId].state !== 'closed') {
        log(`关闭音频上下文 [${videoId}]`);
        audioContexts[videoId].close().catch(error => {
          log(`关闭音频上下文时出错: ${error.message}`);
        });
      }
    } catch (error) {
      log(`处理音频上下文时出错: ${error.message}`);
    }
  }
  
  // 清空引用
  videoElements = [];
  subtitleContainers = {};
  controlsElements = {};
  processingStatus = {};
  audioContexts = {};
  websockets = {};
  mediaRecorders = {};
  connectedVideoElements = {};
  processorNodes = {};
  audioProcessors = {};
  subtitleEnabled = {};
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

// 重置处理
function resetProcessing(video, videoId) {
  log(`重置音频处理 [${videoId}]`);
  
  // 检查WebSocket连接
  if (websockets[videoId] && websockets[videoId].readyState === WebSocket.OPEN) {
    // 发送重置信号
    try {
      websockets[videoId].send("RESET");
      log('已发送RESET信号');
      
      // 更新字幕
      updateSubtitle(videoId, '正在重置音频处理...');
    } catch (error) {
      log(`发送RESET信号时出错: ${error.message}`);
      
      // 如果发送失败，尝试重新启动处理
      stopProcessing(video, videoId);
      setTimeout(() => {
        startProcessing(video, videoId);
      }, 1000);
    }
  } else {
    // 如果WebSocket未连接，则重新启动处理
    stopProcessing(video, videoId);
    setTimeout(() => {
      startProcessing(video, videoId);
    }, 1000);
  }
}

// 恢复视频音频
function restoreVideoAudio(video) {
  if (!video || !video.tagName || video.tagName.toLowerCase() !== 'video') {
    log('无效的视频元素，无法恢复音频');
    return;
  }
  
  try {
    log(`尝试恢复视频音频: ${video.src || '(无源)'}`);
    
    // 在某些情况下，我们可能需要重新加载视频
    const currentTime = video.currentTime;
    const wasPlaying = !video.paused;
    
    // 如果视频没有声音，尝试重新加载
    if (video.volume === 0 || video.muted) {
      log('视频当前已静音，尝试取消静音');
      video.muted = false;
      video.volume = 1.0;
    }
    
    // 如果视频仍然没有声音，可能需要更复杂的处理
    // 这里我们只记录一个消息，因为实际的恢复在stopProcessing中处理
    log('已尝试恢复视频音频，如果仍然没有声音，可能需要刷新页面');
  } catch (error) {
    log(`恢复视频音频时出错: ${error.message}`);
  }
}

// 初始化插件
init(); 