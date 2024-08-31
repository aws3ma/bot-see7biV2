import asyncio
import itertools
import os
import random
import discord
import yt_dlp
from discord.ext import commands
from MusicPlayer import MusicPlayer
from YTDLSource import YTDLSource
from custom_exceptions import InvalidVoiceChannel, VoiceConnectionError

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''
username = os.getenv("YT_USERNAME", default=None)
password = os.getenv("YT_PASSWORD", default=None)
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    # bind to ipv4 since ipv6 addresses cause issues sometimes
    'source_address': '0.0.0.0',
    'age_limit': 18,
    'u': username,
    'p': password,
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class Music(commands.Cog):
    __slots__ = ('bot', 'players')
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='join')
    async def join(self, ctx, *, channel: discord.VoiceChannel=None):
        """Joins a voice channel"""
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel(
                    'No channel to join. Please either specify a valid channel or join one.'
                )

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(
                    f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(
                    f'Connecting to channel: <{channel}> timed out.')

        await ctx.send(f'Connected to : **{channel}**', delete_after=20)

    @commands.command(name='p')
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""
        await ctx.typing()
        player = self.get_player(ctx)
        loop = asyncio.get_event_loop()
        newData = []
        if 'watch' not in url:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=url, download=False))
            if 'entries' in data:
                # take a playlist
                newData = data['entries']
        if (len(newData) != 0):
            random.shuffle(newData)
            for ghneya in newData:
                if(ghneya is not None):
                    source = await YTDLSource.from_url(url=ghneya["webpage_url"],
                                                    loop=self.bot.loop,
                                                    stream=True)
                    await player.queue.put(source)
        else:
            source = await YTDLSource.from_url(
                url=url,
                loop=self.bot.loop,
                stream=True)
            await player.queue.put(source)
    
    @commands.command(name='volume')
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @commands.command(name='pause')
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('Paused!',
                                delete_after=20)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: pauselna laghneya see7bi!')

    @commands.command(name='resume')
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Resumed!',
                                delete_after=20)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.command(name='skip')
    async def skip_(self, ctx):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Skipped!',
                                delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Skipped the song!')

    @commands.command(name='queue', aliases=['q', 'playlist'])
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Not connected!',
                                delete_after=20)

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('Queue is empty!')

        # Grab up to 5 entries from the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, 100))

        fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}',
                            description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='now_playing',
                    aliases=['np', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('Not playing!')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send(f'**Now Playing:** `{vc.source.title}` '
                                f'requested by `{vc.source.requester}`')
    # @play.before_invoke
    @join.before_invoke
    @stream.before_invoke
    @now_playing_.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError(
                    "Author not connected to a voice channel.")
        # elif ctx.voice_client.is_playing():
        #     ctx.voice_client.stop()


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='Bot by Ouss3ma',
    intents=intents,
)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

key = "DISCORD_TOKEN"

token = os.getenv(key, default=None)


async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        try:
            await bot.start(token)
        except asyncio.exceptions.CancelledError:
            print("Bot stopped")


asyncio.run(main())
