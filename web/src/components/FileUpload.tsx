import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FiUpload, FiFile, FiX } from 'react-icons/fi';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  maxSize?: number;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelect,
  accept = 'video/*,audio/*',
  maxSize = 1024 * 1024 * 500 // 500MB
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    setError(null);
    
    if (rejectedFiles.length > 0) {
      const { code } = rejectedFiles[0].errors[0];
      if (code === 'file-too-large') {
        setError(`文件过大，最大支持 ${Math.round(maxSize / (1024 * 1024))}MB`);
      } else if (code === 'file-invalid-type') {
        setError('不支持的文件类型，请上传视频或音频文件');
      } else {
        setError('文件上传失败，请重试');
      }
      return;
    }
    
    if (acceptedFiles.length > 0) {
      const selectedFile = acceptedFiles[0];
      setFile(selectedFile);
      onFileSelect(selectedFile);
    }
  }, [maxSize, onFileSelect]);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: accept.split(',').reduce((acc, curr) => {
      acc[curr] = [];
      return acc;
    }, {} as Record<string, string[]>),
    maxSize,
    multiple: false
  });
  
  const removeFile = () => {
    setFile(null);
  };
  
  return (
    <div className="w-full">
      {!file ? (
        <div 
          {...getRootProps()} 
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive 
              ? 'border-primary-500 bg-primary-50' 
              : 'border-gray-300 hover:border-primary-500 hover:bg-gray-50'
          }`}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center justify-center">
            <FiUpload className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-700">
              {isDragActive ? '放开以上传文件' : '拖放文件到此处，或点击选择文件'}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              支持视频和音频文件，最大 {Math.round(maxSize / (1024 * 1024))}MB
            </p>
            {error && <p className="text-red-500 mt-2">{error}</p>}
          </div>
        </div>
      ) : (
        <div className="border rounded-lg p-4 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <FiFile className="w-8 h-8 text-primary-500 mr-3" />
              <div>
                <p className="font-medium text-gray-800">{file.name}</p>
                <p className="text-sm text-gray-500">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </div>
            <button 
              type="button" 
              onClick={removeFile}
              className="p-1 rounded-full hover:bg-gray-200"
            >
              <FiX className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload; 