import React from 'react';
import Link from 'next/link';

const Footer: React.FC = () => {
  return (
    <footer className="bg-gray-800 text-white py-8">
      <div className="container-custom">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="text-lg font-semibold mb-4">Whisper Web</h3>
            <p className="text-gray-300">
              基于faster-whisper的在线视频字幕工具，包含Web应用和浏览器插件。
            </p>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold mb-4">快速链接</h3>
            <ul className="space-y-2">
              <li>
                <Link href="/" className="text-gray-300 hover:text-white">
                  首页
                </Link>
              </li>
              <li>
                <Link href="/upload" className="text-gray-300 hover:text-white">
                  上传视频
                </Link>
              </li>
              <li>
                <Link href="/transcribe" className="text-gray-300 hover:text-white">
                  在线转录
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-gray-300 hover:text-white">
                  关于
                </Link>
              </li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold mb-4">相关资源</h3>
            <ul className="space-y-2">
              <li>
                <a href="https://github.com/openai/whisper" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white">
                  OpenAI Whisper
                </a>
              </li>
              <li>
                <a href="https://github.com/guillaumekln/faster-whisper" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white">
                  Faster Whisper
                </a>
              </li>
              <li>
                <a href="https://github.com/your-username/whisper-web" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white">
                  GitHub 仓库
                </a>
              </li>
            </ul>
          </div>
        </div>
        
        <div className="mt-8 pt-8 border-t border-gray-700 text-center text-gray-400">
          <p>&copy; {new Date().getFullYear()} Whisper Web. 保留所有权利。</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer; 