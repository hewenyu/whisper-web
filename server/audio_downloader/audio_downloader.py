#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to download audio from videos using yt_dlp
Created by: hewenyu
Date: 2025-03-04
"""

from yt_dlp import YoutubeDL
import os
import uuid

class AudioDownloader:
    """
    Class for downloading audio from videos using yt_dlp
    """
    
    def __init__(self, output_path=None, audio_format='wav', quality='0'):
        """
        Initialize the AudioDownloader
        
        Args:
            output_path (str, optional): Directory to save the audio file
            audio_format (str, optional): Audio format (mp3, m4a, etc.)
            quality (str, optional): Audio quality in kbps
        """
        self.output_path = output_path
        self.audio_format = audio_format
        self.quality = quality
        
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
    
    def download_audio(self, url) -> str:
        """
        Download audio from a specified video URL.
        
        Args:
            url (str): URL of the video
        
        Returns:
            str: Path to the downloaded audio file or None if download failed
        """
        file_uuid = str(uuid.uuid4())
            
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.audio_format,
                'preferredquality': self.quality,
            }],
            'outtmpl': f'{file_uuid}.%(ext)s' if not self.output_path else os.path.join(self.output_path, f'{file_uuid}.%(ext)s'),
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # output filepath
                output_filepath = f'{file_uuid}.{self.audio_format}'
                print(f"Successfully downloaded audio: {output_filepath}")
                # print(f"Successfully downloaded audio: {info.get('title', 'Unknown Title')}")
                return os.path.join(self.output_path, output_filepath)
        except Exception as e:
            print(f"Error downloading audio: {str(e)}")
            return None

