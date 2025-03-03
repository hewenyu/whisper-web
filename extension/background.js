// 插件安装或更新时初始化设置
chrome.runtime.onInstalled.addListener(function() {
  // 设置默认配置
  chrome.storage.local.set({
    isActive: false,
    settings: {
      serverUrl: 'http://localhost:8000',
      language: 'auto',
      subtitlePosition: 'bottom',
      fontSize: '20'
    }
  });
  
  console.log('Whisper Web 插件已安装/更新');
});

// 监听来自内容脚本的消息
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === 'getStatus') {
    // 获取当前状态和设置
    chrome.storage.local.get(['isActive', 'settings'], function(result) {
      sendResponse({
        isActive: result.isActive || false,
        settings: result.settings || {
          serverUrl: 'http://localhost:8000',
          language: 'auto',
          subtitlePosition: 'bottom',
          fontSize: '20'
        }
      });
    });
    return true; // 异步响应
  }
  
  if (request.action === 'log') {
    console.log('Content script log:', request.message);
    sendResponse({ success: true });
  }
}); 