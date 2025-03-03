import React from 'react';
import Layout from '@/components/Layout';
import Link from 'next/link';

const AboutPage: React.FC = () => {
  return (
    <Layout title="关于 - Whisper Web">
      <div className="container-custom py-12">
        <h1 className="text-3xl font-bold mb-8">关于 Whisper Web</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="md:col-span-2">
            <div className="card p-6 mb-8">
              <h2 className="text-2xl font-semibold mb-4">项目介绍</h2>
              <p className="text-gray-700 mb-4">
                Whisper Web 是一个基于 OpenAI 的 Whisper 模型的在线视频字幕生成工具，使用 faster-whisper 作为后端引擎，
                提供了简单易用的 Web 界面和浏览器插件，让用户可以轻松为视频添加高质量的字幕。
              </p>
              <p className="text-gray-700 mb-4">
                本项目包含三个主要部分：
              </p>
              <ul className="list-disc pl-6 mb-4 text-gray-700 space-y-2">
                <li>
                  <strong>后端服务</strong>：基于 FastAPI 和 faster-whisper 的 API 服务，负责处理视频/音频文件并生成字幕。
                </li>
                <li>
                  <strong>Web 应用</strong>：基于 Next.js 的前端应用，提供用户界面，允许用户上传视频并获取字幕。
                </li>
                <li>
                  <strong>浏览器插件</strong>：Chrome/Firefox 扩展，可以为任意网站上的视频添加实时字幕。
                </li>
              </ul>
            </div>
            
            <div className="card p-6 mb-8">
              <h2 className="text-2xl font-semibold mb-4">技术栈</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-xl font-medium mb-2">后端</h3>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1">
                    <li>Python</li>
                    <li>FastAPI</li>
                    <li>faster-whisper</li>
                    <li>FFmpeg</li>
                    <li>WebSockets</li>
                  </ul>
                </div>
                <div>
                  <h3 className="text-xl font-medium mb-2">前端</h3>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1">
                    <li>Next.js</li>
                    <li>React</li>
                    <li>TypeScript</li>
                    <li>Tailwind CSS</li>
                    <li>Axios</li>
                  </ul>
                </div>
              </div>
            </div>
            
            <div className="card p-6">
              <h2 className="text-2xl font-semibold mb-4">关于 Whisper</h2>
              <p className="text-gray-700 mb-4">
                Whisper 是 OpenAI 开发的一个自动语音识别系统，它经过了大量多语言和多任务数据的训练，
                能够实现强大的语音识别、语言识别和翻译功能。Whisper 模型在各种语音处理任务上表现出色，
                尤其是在嘈杂环境下的语音识别和多语言支持方面。
              </p>
              <p className="text-gray-700 mb-4">
                faster-whisper 是 Whisper 模型的一个优化实现，使用 CTranslate2 引擎，提供更快的推理速度和更低的内存占用。
              </p>
              <div className="mt-4">
                <a 
                  href="https://github.com/openai/whisper" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:underline"
                >
                  了解更多关于 Whisper
                </a>
              </div>
            </div>
          </div>
          
          <div>
            <div className="card p-6 mb-8">
              <h2 className="text-2xl font-semibold mb-4">快速链接</h2>
              <ul className="space-y-3">
                <li>
                  <Link href="/" className="text-primary-600 hover:underline">
                    首页
                  </Link>
                </li>
                <li>
                  <Link href="/upload" className="text-primary-600 hover:underline">
                    上传视频
                  </Link>
                </li>
                <li>
                  <Link href="/transcribe" className="text-primary-600 hover:underline">
                    在线转录
                  </Link>
                </li>
                <li>
                  <Link href="/extension" className="text-primary-600 hover:underline">
                    浏览器插件
                  </Link>
                </li>
              </ul>
            </div>
            
            <div className="card p-6">
              <h2 className="text-2xl font-semibold mb-4">联系我们</h2>
              <p className="text-gray-700 mb-4">
                如果您有任何问题、建议或反馈，请通过以下方式联系我们：
              </p>
              <ul className="space-y-2 text-gray-700">
                <li>
                  <strong>GitHub</strong>: 
                  <a 
                    href="https://github.com/your-username/whisper-web" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="ml-1 text-primary-600 hover:underline"
                  >
                    whisper-web
                  </a>
                </li>
                <li>
                  <strong>Email</strong>: 
                  <a 
                    href="mailto:your-email@example.com" 
                    className="ml-1 text-primary-600 hover:underline"
                  >
                    your-email@example.com
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default AboutPage; 