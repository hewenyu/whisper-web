/**
 * Whisper Web 字幕处理工具
 * 用于处理和显示字幕数据
 */

class WhisperSubtitles {
  constructor(options = {}) {
    this.options = {
      position: options.position || 'bottom',
      fontSize: options.fontSize || 20,
      language: options.language || 'auto',
      serverUrl: options.serverUrl || 'http://localhost:8000'
    };
    
    this.subtitles = [];
    this.currentIndex = -1;
    this.container = null;
    this.element = null;
    this.videoElement = null;
    this.isActive = false;
  }
  
  /**
   * 初始化字幕容器
   * @param {HTMLElement} videoContainer - 视频容器元素
   * @param {HTMLVideoElement} videoElement - 视频元素
   */
  init(videoContainer, videoElement) {
    this.videoElement = videoElement;
    
    // 创建字幕容器
    this.container = document.createElement('div');
    this.container.className = `whisper-web-subtitle-container ${this.options.position}`;
    
    // 创建字幕元素
    this.element = document.createElement('div');
    this.element.className = 'whisper-web-subtitle';
    this.element.style.fontSize = `${this.options.fontSize}px`;
    
    this.container.appendChild(this.element);
    videoContainer.appendChild(this.container);
    
    // 隐藏字幕容器
    this.hide();
    
    // 监听视频时间更新事件
    this.videoElement.addEventListener('timeupdate', this.onTimeUpdate.bind(this));
  }
  
  /**
   * 设置字幕数据
   * @param {Array} subtitles - 字幕数据数组
   */
  setSubtitles(subtitles) {
    this.subtitles = subtitles;
    this.currentIndex = -1;
  }
  
  /**
   * 视频时间更新事件处理
   */
  onTimeUpdate() {
    if (!this.isActive || !this.subtitles.length) return;
    
    const currentTime = this.videoElement.currentTime;
    let foundSubtitle = false;
    
    // 查找当前时间对应的字幕
    for (let i = 0; i < this.subtitles.length; i++) {
      const subtitle = this.subtitles[i];
      
      if (currentTime >= subtitle.start && currentTime <= subtitle.end) {
        if (this.currentIndex !== i) {
          this.currentIndex = i;
          this.updateText(subtitle.text);
        }
        foundSubtitle = true;
        break;
      }
    }
    
    // 如果没有找到字幕，则隐藏字幕
    if (!foundSubtitle) {
      this.hide();
      this.currentIndex = -1;
    }
  }
  
  /**
   * 更新字幕文本
   * @param {string} text - 字幕文本
   */
  updateText(text) {
    if (!text) {
      this.hide();
      return;
    }
    
    this.element.textContent = text;
    this.show();
  }
  
  /**
   * 显示字幕
   */
  show() {
    this.container.style.display = 'block';
  }
  
  /**
   * 隐藏字幕
   */
  hide() {
    this.container.style.display = 'none';
  }
  
  /**
   * 激活字幕
   */
  activate() {
    this.isActive = true;
  }
  
  /**
   * 停用字幕
   */
  deactivate() {
    this.isActive = false;
    this.hide();
  }
  
  /**
   * 更新选项
   * @param {Object} options - 新选项
   */
  updateOptions(options) {
    this.options = { ...this.options, ...options };
    
    // 更新样式
    this.container.className = `whisper-web-subtitle-container ${this.options.position}`;
    this.element.style.fontSize = `${this.options.fontSize}px`;
  }
  
  /**
   * 销毁字幕组件
   */
  destroy() {
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }
    
    if (this.videoElement) {
      this.videoElement.removeEventListener('timeupdate', this.onTimeUpdate);
    }
    
    this.container = null;
    this.element = null;
    this.videoElement = null;
    this.subtitles = [];
    this.isActive = false;
  }
}

// 导出字幕类
window.WhisperSubtitles = WhisperSubtitles; 