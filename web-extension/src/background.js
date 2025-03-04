// 监听来自内容脚本的消息
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  // 处理从内容脚本发来的消息
  if (request.action === 'extractAudio') {
    const { videoUrl, videoId, serverUrl } = request;
    
    // 调用服务器API提取音频
    extractAudioFromUrl(videoUrl, videoId, serverUrl)
      .then(response => {
        sendResponse(response);
      })
      .catch(error => {
        sendResponse({
          success: false,
          message: '提取音频失败: ' + error.message
        });
      });
    
    // 返回true表示将异步发送响应
    return true;
  }
  
  // 处理转录请求
  if (request.action === 'transcribe') {
    const { fileUuid, language, format, serverUrl } = request;
    
    // 调用服务器API进行转录
    transcribeAudio(fileUuid, language, format, serverUrl)
      .then(response => {
        sendResponse(response);
      })
      .catch(error => {
        sendResponse({
          success: false,
          message: '转录失败: ' + error.message
        });
      });
    
    // 返回true表示将异步发送响应
    return true;
  }
});

// 从URL提取音频
async function extractAudioFromUrl(videoUrl, videoId, serverUrl) {
  try {
    console.log(`开始从URL提取音频: ${videoUrl}`);
    
    // 创建FormData对象
    const formData = new FormData();
    formData.append('url', videoUrl);
    formData.append('video_id', videoId);
    
    // 发送请求到服务器
    const response = await fetch(`${serverUrl}/extract-audio`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('提取音频失败:', response.status, errorText);
      throw new Error(`服务器错误 (${response.status}): ${errorText}`);
    }
    
    // 解析响应
    const data = await response.json();
    console.log('提取音频响应:', data);
    
    if (!data.success) {
      throw new Error(data.message || '提取音频失败');
    }
    
    return {
      success: true,
      message: '音频提取成功',
      fileUuid: data.file_uuid
    };
  } catch (error) {
    console.error('提取音频时出错:', error);
    throw error;
  }
}

// 转录音频
async function transcribeAudio(fileUuid, language, format, serverUrl) {
  try {
    console.log(`开始转录请求: fileUuid=${fileUuid}`);
    
    // 创建FormData对象
    const formData = new FormData();
    formData.append('file_uuid', fileUuid);
    
    // 只发送必要的UUID参数，其他参数使用服务器默认值
    console.log('发送转录请求，参数:', {
      file_uuid: fileUuid
    });
    
    // 发送请求到服务器
    const response = await fetch(`${serverUrl}/transcribe`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('服务器返回错误:', response.status, errorText);
      throw new Error(`服务器错误 (${response.status}): ${errorText}`);
    }
    
    // 解析响应
    const data = await response.json();
    console.log('转录响应:', data);
    
    // 检查响应中是否包含字幕文件路径
    if (!data.subtitle_file) {
      throw new Error('响应中缺少字幕文件路径');
    }
    
    // 获取字幕文件内容
    const subtitleUrl = new URL(data.subtitle_file, serverUrl).href;
    console.log('获取字幕文件:', subtitleUrl);
    
    const subtitleResponse = await fetch(subtitleUrl);
    if (!subtitleResponse.ok) {
      throw new Error(`获取字幕文件失败: ${subtitleResponse.status}`);
    }
    
    const subtitleContent = await subtitleResponse.text();
    console.log('获取到字幕内容:', subtitleContent.substring(0, 100) + '...');
    
    return {
      success: true,
      message: '转录成功',
      subtitleFile: subtitleContent,
      segments: data.segments
    };
  } catch (error) {
    console.error('转录音频时出错:', error);
    throw error;
  }
} 