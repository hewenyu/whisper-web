import React from 'react';
import Link from 'next/link';
import Layout from '@/components/Layout';
import { FiUpload, FiMic, FiDownload, FiGlobe } from 'react-icons/fi';

const Home: React.FC = () => {
  return (
    <Layout>
      <section className="bg-gradient-to-b from-primary-50 to-white py-16">
        <div className="container-custom">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              使用 Whisper Web 为视频添加智能字幕
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              基于 OpenAI 的 Whisper 模型，快速准确地为视频生成字幕，支持多种语言和格式。
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/upload" className="btn btn-primary px-6 py-3 text-lg">
                开始使用
              </Link>
              <Link href="/about" className="btn btn-secondary px-6 py-3 text-lg">
                了解更多
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="container-custom">
          <h2 className="text-3xl font-bold text-center mb-12">主要功能</h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="card p-6 text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FiUpload className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">上传视频</h3>
              <p className="text-gray-600">
                支持多种视频和音频格式，轻松上传本地文件进行处理。
              </p>
            </div>
            
            <div className="card p-6 text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FiMic className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">语音识别</h3>
              <p className="text-gray-600">
                使用先进的 Whisper 模型，准确识别视频中的语音内容。
              </p>
            </div>
            
            <div className="card p-6 text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FiDownload className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">导出字幕</h3>
              <p className="text-gray-600">
                支持 VTT、SRT 和 JSON 格式，方便集成到各种视频平台。
              </p>
            </div>
            
            <div className="card p-6 text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FiGlobe className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">多语言支持</h3>
              <p className="text-gray-600">
                支持中文、英语、日语等多种语言的识别和转录。
              </p>
            </div>
          </div>
        </div>
      </section>
      
      <section className="py-16 bg-gray-50">
        <div className="container-custom">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl font-bold mb-6">浏览器插件</h2>
            <p className="text-xl text-gray-600 mb-8">
              安装我们的浏览器插件，为任意网站上的视频添加实时字幕。
            </p>
            <Link href="/extension" className="btn btn-primary px-6 py-3 text-lg">
              获取插件
            </Link>
          </div>
        </div>
      </section>
    </Layout>
  );
};

export default Home; 