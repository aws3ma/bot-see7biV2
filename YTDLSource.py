import asyncio
from functools import partial
import discord
import yt_dlp

yt_dlp.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    # bind to ipv4 since ipv6 addresses cause issues sometimes
    'source_address': '0.0.0.0',
}
ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


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
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(executable='./ffmpeg.exe', source=filename, **ffmpeg_options), data=data)

    @classmethod
    async def from_id(cls, id, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: sp.track(id))
        data['webpage_url']=data['preview_url']
        data['url']=data['preview_url']
        data['title']=data['name']
        return cls(discord.FFmpegPCMAudio(executable='./ffmpeg.exe', source=data['preview_url'], **ffmpeg_options),data=data)
    
    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=data['webpage_url'],download=False))
        return cls(discord.FFmpegPCMAudio(executable='./ffmpeg.exe', source=data['url'], **ffmpeg_options),
                   data=data)
