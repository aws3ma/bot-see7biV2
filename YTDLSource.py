import asyncio
from urllib.parse import urlparse, parse_qs
import shutil
import discord
from yt_dlp import YoutubeDL
import yt_dlp.utils
import traceback
# yt_dlp.utils.bug_reports_message = lambda: ''

FFMPEG_EXECUTABLE = shutil.which('ffmpeg.exe') or shutil.which('ffmpeg') or './ffmpeg.exe'
if not FFMPEG_EXECUTABLE:
    print('Warning: ffmpeg executable not found. Place ffmpeg.exe in the project root or on PATH.')

ytdl_format_options = {
    'format': 'bestaudio/best',
    # 'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'sleep_interval': 15,
    'extractor_args': {
      'youtube': {
        'player_client': ['android'],
      },
    },
}
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
          data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=url, download=not stream))
        except yt_dlp.utils.ExtractorError as e:
          if "this content isn't available" in str(e).lower():
            print("Rate limit hit, retrying after 30 seconds...")
            await asyncio.sleep(30)
            try:
              data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=url, download=not stream))
            except Exception as e2:
              traceback.print_exc()
              print(e2)
              return None
          else:
            traceback.print_exc()
            print(e)
            return None
        except Exception as e:
          traceback.print_exc()
          print(e)
          return None
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(executable=FFMPEG_EXECUTABLE, source=filename, **ffmpeg_options), data=data)

    @classmethod
    async def from_id(cls, id, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: sp.track(id))
        data['webpage_url']=data['preview_url']
        data['url']=data['preview_url']
        data['title']=data['name']
        return cls(discord.FFmpegPCMAudio(executable=FFMPEG_EXECUTABLE, source=data['preview_url'], **ffmpeg_options), data=data)
    
    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        try:
          data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=data['webpage_url'],download=False))
        except yt_dlp.utils.ExtractorError as e:
          if "this content isn't available" in str(e).lower():
            print("Rate limit hit in regather, retrying after 30 seconds...")
            await asyncio.sleep(30)
            try:
              data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=data['webpage_url'],download=False))
            except Exception as e2:
              traceback.print_exc()
              print(e2)
              return None
          else:
            traceback.print_exc()
            print(e)
            return None
        except Exception as e:
          traceback.print_exc()
          print(e)
          return None
        return cls(discord.FFmpegPCMAudio(executable=FFMPEG_EXECUTABLE, source=data['url'], **ffmpeg_options),
                   data=data)
    @classmethod
    async def getData(cls,url,*,loop, stream=True):
      try:
        return await loop.run_in_executor(None, lambda: ytdl.extract_info(url=url, download=not stream))
      except yt_dlp.utils.ExtractorError as e:
        if "this content isn't available" in str(e).lower():
          print("Rate limit hit in getData, retrying after 30 seconds...")
          await asyncio.sleep(30)
          try:
            return await loop.run_in_executor(None, lambda: ytdl.extract_info(url=url, download=not stream))
          except Exception as e2:
            traceback.print_exc()
            print(e2)
            return None
        else:
          traceback.print_exc()
          print(e)
          return None
      except Exception as e:
        traceback.print_exc()
        print(e)
        return None
    
    @classmethod
    async def from_filename(cls, filename):
        return cls(discord.FFmpegPCMAudio(executable='./ffmpeg.exe', source=filename, **ffmpeg_options))
      
    @classmethod
    def extract_first_video_url(cls, playlist_url):
        parsed = urlparse(playlist_url)
        print(parsed)
        qs = parse_qs(parsed.query)
        video_id = qs.get('v', [None])[0]
        if video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"
            return link
        return None