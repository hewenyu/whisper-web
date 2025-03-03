import axios from 'axios';

const API_URL = process.env.API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  words?: Array<{
    start: number;
    end: number;
    word: string;
    probability: number;
  }>;
}

export interface TranscriptionResponse {
  success: boolean;
  message: string;
  segments: TranscriptionSegment[];
  subtitle_file?: string;
}

export const transcribeFile = async (
  file: File,
  language?: string,
  format: 'vtt' | 'srt' | 'json' = 'vtt'
): Promise<TranscriptionResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const params: Record<string, string> = {
    format,
  };
  
  if (language && language !== 'auto') {
    params.language = language;
  }
  
  try {
    const response = await api.post<TranscriptionResponse>('/transcribe', formData, {
      params,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      throw new Error(error.response.data.detail || '转录失败');
    }
    throw new Error('网络错误，请稍后重试');
  }
};

export const getSubtitleUrl = (subtitlePath: string): string => {
  return `${API_URL}/${subtitlePath}`;
};

export const healthCheck = async (): Promise<{ status: string; timestamp: number }> => {
  try {
    const response = await api.get<{ status: string; timestamp: number }>('/health');
    return response.data;
  } catch (error) {
    throw new Error('服务器连接失败');
  }
};

export default api; 