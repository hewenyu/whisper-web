import React, { useState } from 'react';
import Layout from '@/components/Layout';
import FileUpload from '@/components/FileUpload';
import VideoPlayer from '@/components/VideoPlayer';
import { transcribeFile, getSubtitleUrl, TranscriptionSegment } from '@/services/api';
import { FiDownload, FiLoader } from 'react-icons/fi';

const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [subtitleUrl, setSubtitleUrl] = useState<string>('');
  const [segments, setSegments] = useState<TranscriptionSegment[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<string>('auto');
  const [format, setFormat] = useState<'vtt' | 'srt' | 'json'>('vtt');
  const [success, setSuccess] = useState<boolean>(false);
  
  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile);
    setVideoUrl(URL.createObjectURL(selectedFile));
    setSubtitleUrl('');
    setSegments([]);
    setSuccess(false);
    setError(null);
  };
  
  const handleTranscribe = async () => {
    if (!file) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await transcribeFile(file, language === 'auto' ? undefined : language, format);
      
      if (result.success && result.subtitle_file) {
        setSubtitleUrl(getSubtitleUrl(result.subtitle_file));
        setSegments(result.segments);
        setSuccess(true);
      } else {
        setError('转录失败，请重试');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '转录失败，请重试');
    } finally {
      setLoading(false);
    }
  };
  
  const handleDownload = () => {
    if (subtitleUrl) {
      const a = document.createElement('a');
      a.href = subtitleUrl;
      a.download = `subtitles.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };
  
  return (
    <Layout title="上传视频 - Whisper Web">
      <div className="container-custom py-8">
        <h1 className="text-3xl font-bold mb-8">上传视频</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            {videoUrl ? (
              <VideoPlayer url={videoUrl} subtitles={subtitleUrl} title={file?.name} />
            ) : (
              <div className="card p-8">
                <FileUpload onFileSelect={handleFileSelect} />
              </div>
            )}
            
            {videoUrl && (
              <div className="mt-6">
                <h2 className="text-xl font-semibold mb-4">字幕设置</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label htmlFor="language" className="block text-sm font-medium text-gray-700 mb-1">
                      语言
                    </label>
                    <select
                      id="language"
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="input"
                    >
                      <option value="auto">自动检测</option>
                      <option value="zh">中文</option>
                      <option value="en">英文</option>
                      <option value="ja">日语</option>
                      <option value="ko">韩语</option>
                      <option value="fr">法语</option>
                      <option value="de">德语</option>
                      <option value="es">西班牙语</option>
                      <option value="ru">俄语</option>
                    </select>
                  </div>
                  
                  <div>
                    <label htmlFor="format" className="block text-sm font-medium text-gray-700 mb-1">
                      字幕格式
                    </label>
                    <select
                      id="format"
                      value={format}
                      onChange={(e) => setFormat(e.target.value as 'vtt' | 'srt' | 'json')}
                      className="input"
                    >
                      <option value="vtt">WebVTT (.vtt)</option>
                      <option value="srt">SubRip (.srt)</option>
                      <option value="json">JSON (.json)</option>
                    </select>
                  </div>
                </div>
                
                <div className="flex space-x-4">
                  <button
                    onClick={handleTranscribe}
                    disabled={loading}
                    className={`btn ${loading ? 'bg-gray-400 cursor-not-allowed' : 'btn-primary'} flex items-center`}
                  >
                    {loading && <FiLoader className="animate-spin mr-2" />}
                    {loading ? '处理中...' : '生成字幕'}
                  </button>
                  
                  {success && (
                    <button
                      onClick={handleDownload}
                      className="btn btn-secondary flex items-center"
                    >
                      <FiDownload className="mr-2" />
                      下载字幕
                    </button>
                  )}
                </div>
                
                {error && (
                  <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-md">
                    {error}
                  </div>
                )}
              </div>
            )}
          </div>
          
          <div>
            <div className="card p-6">
              <h2 className="text-xl font-semibold mb-4">字幕预览</h2>
              
              {loading ? (
                <div className="flex items-center justify-center p-8">
                  <FiLoader className="animate-spin text-primary-500 w-8 h-8" />
                  <span className="ml-2 text-gray-600">处理中...</span>
                </div>
              ) : segments.length > 0 ? (
                <div className="max-h-[500px] overflow-y-auto">
                  {segments.map((segment) => (
                    <div key={segment.id} className="mb-4 p-3 bg-gray-50 rounded-md">
                      <div className="text-sm text-gray-500 mb-1">
                        {formatTime(segment.start)} - {formatTime(segment.end)}
                      </div>
                      <div className="text-gray-800">{segment.text}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center p-8 text-gray-500">
                  {videoUrl ? '上传视频后点击"生成字幕"按钮' : '请先上传视频'}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

// 格式化时间为 00:00:00 格式
const formatTime = (seconds: number): string => {
  const date = new Date(seconds * 1000);
  const hh = date.getUTCHours().toString().padStart(2, '0');
  const mm = date.getUTCMinutes().toString().padStart(2, '0');
  const ss = date.getUTCSeconds().toString().padStart(2, '0');
  const ms = date.getUTCMilliseconds().toString().padStart(3, '0').substring(0, 2);
  
  return `${hh}:${mm}:${ss}.${ms}`;
};

export default UploadPage; 