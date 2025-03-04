// 当弹出窗口加载完成时
document.addEventListener('DOMContentLoaded', function() {
  // 获取DOM元素
  const generateBtn = document.getElementById('generateBtn');
  const statusElement = document.getElementById('status');
  const serverUrlInput = document.getElementById('serverUrl');
  
  // 从存储中加载设置
  chrome.storage.sync.get({
    serverUrl: 'http://localhost:8000'
  }, function(items) {
    serverUrlInput.value = items.serverUrl;
  });
  
  // 保存设置
  function saveSettings() {
    chrome.storage.sync.set({
      serverUrl: serverUrlInput.value
    });
  }
  
  // 当设置改变时保存
  serverUrlInput.addEventListener('change', saveSettings);
  
  // 生成字幕按钮点击事件
  generateBtn.addEventListener('click', function() {
    // 更新状态
    statusElement.textContent = '状态: 正在检测视频...';
    
    // 获取当前标签页
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      const currentTab = tabs[0];
      
      // 发送消息到内容脚本
      chrome.tabs.sendMessage(currentTab.id, {
        action: 'generateSubtitles',
        settings: {
          serverUrl: serverUrlInput.value
        }
      }, function(response) {
        if (response && response.success) {
          statusElement.textContent = '状态: ' + response.message;
        } else {
          statusElement.textContent = '状态: 错误 - ' + (response ? response.message : '无法连接到页面');
        }
      });
    });
  });
  
  // 检查服务器状态
  function checkServerStatus() {
    const serverUrl = serverUrlInput.value;
    
    fetch(`${serverUrl}/status`)
      .then(response => response.json())
      .then(data => {
        if (data.status === 'healthy') {
          statusElement.textContent = '状态: 服务器连接正常';
          generateBtn.disabled = false;
        } else {
          statusElement.textContent = '状态: 服务器连接异常';
        }
      })
      .catch(error => {
        statusElement.textContent = '状态: 无法连接到服务器';
        generateBtn.disabled = true;
      });
  }
  
  // 初始检查服务器状态
  checkServerStatus();
}); 