import React, { useState, useEffect, useRef } from 'react';
import ReactPlayer from 'react-player';
import { FiPlay, FiPause, FiVolume2, FiVolumeX, FiMaximize } from 'react-icons/fi';

interface VideoPlayerProps {
  url: string;
  subtitles?: string;
  title?: string;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ url, subtitles, title }) => {
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(0.8);
  const [muted, setMuted] = useState(false);
  const [played, setPlayed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seeking, setSeeking] = useState(false);
  
  const playerRef = useRef<ReactPlayer>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  
  const handlePlayPause = () => {
    setPlaying(!playing);
  };
  
  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setVolume(parseFloat(e.target.value));
  };
  
  const handleToggleMute = () => {
    setMuted(!muted);
  };
  
  const handleProgress = (state: { played: number; playedSeconds: number; loaded: number; loadedSeconds: number }) => {
    if (!seeking) {
      setPlayed(state.played);
    }
  };
  
  const handleSeekMouseDown = () => {
    setSeeking(true);
  };
  
  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPlayed(parseFloat(e.target.value));
  };
  
  const handleSeekMouseUp = (e: React.MouseEvent<HTMLInputElement>) => {
    setSeeking(false);
    if (playerRef.current) {
      playerRef.current.seekTo(parseFloat((e.target as HTMLInputElement).value));
    }
  };
  
  const handleDuration = (duration: number) => {
    setDuration(duration);
  };
  
  const handleFullscreen = () => {
    if (playerContainerRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        playerContainerRef.current.requestFullscreen();
      }
    }
  };
  
  const formatTime = (seconds: number) => {
    const date = new Date(seconds * 1000);
    const hh = date.getUTCHours();
    const mm = date.getUTCMinutes();
    const ss = date.getUTCSeconds().toString().padStart(2, '0');
    
    if (hh) {
      return `${hh}:${mm.toString().padStart(2, '0')}:${ss}`;
    }
    
    return `${mm}:${ss}`;
  };
  
  return (
    <div className="card overflow-hidden">
      {title && (
        <div className="p-3 border-b">
          <h3 className="text-lg font-medium">{title}</h3>
        </div>
      )}
      
      <div className="relative bg-black" ref={playerContainerRef}>
        <ReactPlayer
          ref={playerRef}
          url={url}
          width="100%"
          height="auto"
          playing={playing}
          volume={volume}
          muted={muted}
          onProgress={handleProgress}
          onDuration={handleDuration}
          config={{
            file: {
              attributes: {
                crossOrigin: "anonymous",
              },
              tracks: subtitles
                ? [
                    {
                      kind: "subtitles",
                      src: subtitles,
                      srcLang: "zh",
                      default: true,
                    },
                  ]
                : undefined,
            },
          }}
        />
        
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
          <div className="flex items-center mb-2">
            <input
              type="range"
              min={0}
              max={1}
              step="any"
              value={played}
              onMouseDown={handleSeekMouseDown}
              onChange={handleSeekChange}
              onMouseUp={handleSeekMouseUp}
              className="w-full h-1 bg-gray-400 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #0ea5e9 0%, #0ea5e9 ${played * 100}%, #9ca3af ${played * 100}%, #9ca3af 100%)`,
              }}
            />
          </div>
          
          <div className="flex items-center justify-between text-white">
            <div className="flex items-center space-x-4">
              <button
                onClick={handlePlayPause}
                className="p-1 rounded-full hover:bg-white/20"
              >
                {playing ? (
                  <FiPause className="w-5 h-5" />
                ) : (
                  <FiPlay className="w-5 h-5" />
                )}
              </button>
              
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleToggleMute}
                  className="p-1 rounded-full hover:bg-white/20"
                >
                  {muted ? (
                    <FiVolumeX className="w-5 h-5" />
                  ) : (
                    <FiVolume2 className="w-5 h-5" />
                  )}
                </button>
                
                <input
                  type="range"
                  min={0}
                  max={1}
                  step="any"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 bg-gray-400 rounded-full appearance-none cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, #0ea5e9 0%, #0ea5e9 ${volume * 100}%, #9ca3af ${volume * 100}%, #9ca3af 100%)`,
                  }}
                />
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <span className="text-sm">
                {formatTime(played * duration)} / {formatTime(duration)}
              </span>
              
              <button
                onClick={handleFullscreen}
                className="p-1 rounded-full hover:bg-white/20"
              >
                <FiMaximize className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer; 