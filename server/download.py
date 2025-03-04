from audio_downloader import AudioDownloader
from stream_whisper.faster_whisper import FasterWhisperStream
import os

def main():
    output_path = "temp"
    subtitles_path = "subtitles"
    audio_format = "wav"
    quality = "0"
    base_url = "https://www.bilibili.com/video/BV1ADc1e8ENF"

    audio_downloader = AudioDownloader(output_path, audio_format, quality)
    info = audio_downloader.download_audio(base_url)
    print(info)
    import asyncio
    faster_whisper = FasterWhisperStream(output_path=subtitles_path,device="cuda",compute_type="float16")
    vtt_name = asyncio.run(faster_whisper.transcribe_file(info))
    print(vtt_name)

if __name__ == "__main__":
    main()