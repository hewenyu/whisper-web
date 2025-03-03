document.addEventListener('DOMContentLoaded', function() {
  // 获取DOM元素
  const statusIndicator = document.getElementById('statusIndicator');
  const statusText = document.getElementById('statusText');
  const serverUrlInput = document.getElementById('serverUrl');
  const languageSelect = document.getElementById('language');
  const subtitlePositionSelect = document.getElementById('subtitlePosition');
  const fontSizeInput = document.getElementById('fontSize');
  const fontSizeValue = document.getElementById('fontSizeValue');
  const activateBtn = document.getElementById('activateBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  
  // 加载保存的设置
  loadSettings();
  
  // 更新字体大小显示
  fontSizeInput.addEventListener('input', function() {
    fontSizeValue.textContent = `${this.value}px`;
  });
  
  // 激活/停用字幕按钮
  activateBtn.addEventListener('click', function() {
    chrome.storage.local.get(['isActive'], function(result) {
      const isActive = !result.isActive;
      
      // 更新状态
      chrome.storage.local.set({ isActive: isActive }, function() {
        updateStatus(isActive);
        
        // 向当前标签页发送消息
        chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
          chrome.tabs.sendMessage(tabs[0].id, { 
            action: isActive ? 'activate' : 'deactivate',
            settings: {
              serverUrl: serverUrlInput.value,
              language: languageSelect.value,
              subtitlePosition: subtitlePositionSelect.value,
              fontSize: fontSizeInput.value
            }
          });
        });
      });
    });
  });
  
  // 保存设置按钮
  saveSettingsBtn.addEventListener('click', function() {
    const settings = {
      serverUrl: serverUrlInput.value,
      language: languageSelect.value,
      subtitlePosition: subtitlePositionSelect.value,
      fontSize: fontSizeInput.value
    };
    
    chrome.storage.local.set({ settings: settings }, function() {
      // 显示保存成功提示
      saveSettingsBtn.textContent = '已保存';
      setTimeout(function() {
        saveSettingsBtn.textContent = '保存设置';
      }, 1500);
      
      // 如果字幕已激活，则向当前标签页发送更新设置消息
      chrome.storage.local.get(['isActive'], function(result) {
        if (result.isActive) {
          chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
            chrome.tabs.sendMessage(tabs[0].id, { 
              action: 'updateSettings',
              settings: settings
            });
          });
        }
      });
    });
  });
  
  // 加载设置
  function loadSettings() {
    chrome.storage.local.get(['settings', 'isActive'], function(result) {
      // 更新状态
      updateStatus(result.isActive || false);
      
      // 更新设置表单
      if (result.settings) {
        serverUrlInput.value = result.settings.serverUrl || 'http://localhost:8000';
        languageSelect.value = result.settings.language || 'auto';
        subtitlePositionSelect.value = result.settings.subtitlePosition || 'bottom';
        fontSizeInput.value = result.settings.fontSize || '20';
        fontSizeValue.textContent = `${fontSizeInput.value}px`;
      }
    });
  }
  
  // 更新状态显示
  function updateStatus(isActive) {
    if (isActive) {
      statusIndicator.classList.add('active');
      statusText.textContent = '已激活';
      activateBtn.textContent = '停用字幕';
      activateBtn.classList.add('active');
    } else {
      statusIndicator.classList.remove('active');
      statusText.textContent = '未激活';
      activateBtn.textContent = '激活字幕';
      activateBtn.classList.remove('active');
    }
  }
}); 