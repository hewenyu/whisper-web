import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

const Header: React.FC = () => {
  const router = useRouter();
  
  const isActive = (path: string) => {
    return router.pathname === path ? 'text-primary-600 border-b-2 border-primary-600' : 'text-gray-600 hover:text-primary-600';
  };
  
  return (
    <header className="bg-white shadow-sm">
      <div className="container-custom">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="flex items-center">
              <span className="text-2xl font-bold text-primary-600">Whisper Web</span>
            </Link>
          </div>
          
          <nav className="flex space-x-8">
            <Link href="/" className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${isActive('/')}`}>
              首页
            </Link>
            <Link href="/upload" className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${isActive('/upload')}`}>
              上传视频
            </Link>
            <Link href="/transcribe" className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${isActive('/transcribe')}`}>
              在线转录
            </Link>
            <Link href="/about" className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${isActive('/about')}`}>
              关于
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header; 