import asyncio
import itertools
import os
import random
from shlex import join
import discord
from discord.ext import commands
from MusicPlayer import MusicPlayer
from YTDLSource import YTDLSource, ytdl
from custom_exceptions import InvalidVoiceChannel, VoiceConnectionError

# Suppress noise about console usage from errors


class Music(commands.Cog):
    __slots__ = ('bot', 'players', 'playlist_tasks')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.playlist_tasks = {}

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

    @commands.command(name='test')
    async def test(self, ctx):
        """Test command to verify bot is receiving commands"""
        await ctx.send(f'✅ Command received by {ctx.author}!')

    @commands.command(name='join')
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        if not channel:
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
            else:
                await ctx.send('❌ You must specify a voice channel or join one first.')
                return

        vc = ctx.voice_client

        try:
            if vc:
                if vc.channel.id == channel.id:
                    await ctx.send(f'Already in {channel}.', delete_after=20)
                    return
                await vc.move_to(channel)
            else:
                await channel.connect()

            await ctx.send(f'Connected to : **{channel}**', delete_after=20)

        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to connect/speak in that channel.')
        except discord.HTTPException as exc:
            await ctx.send(f'❌ Failed to connect/move: {exc}')
        except asyncio.TimeoutError:
            await ctx.send('❌ Connection timed out.')
        except Exception as exc:
            print(f'join failed: {type(exc).__name__}: {exc}')
            await ctx.send(f'❌ Unexpected join error: {type(exc).__name__}: {exc}')

    @commands.command(name='p')
    async def stream(self, ctx, *, query):
        """Streams from a URL or searches YouTube for a song"""
        await ctx.send(f'✅ Processing: `{query}`')
        try:
            await ctx.typing()
            player = self.get_player(ctx)
            loop = asyncio.get_event_loop()
            newData = []
            
            # Check if it's a URL or a search query
            is_url = 'http' in query or 'youtube.com' in query or 'youtu.be' in query
            
            if not is_url:
                # It's a search query, do flat search first
                search_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=f"ytsearch:{query}", download=False))
                
                if not search_data or 'entries' not in search_data or len(search_data['entries']) == 0:
                    await ctx.send(f"❌ No results for `{query}`")
                    return
                
                # Get the first result's URL
                first_result = search_data['entries'][0]
                query = first_result.get('url') or f"https://www.youtube.com/watch?v={first_result.get('id')}"

            if 'list' in query:
                if 'watch' in query:
                    first_ghneya = YTDLSource.extract_first_video_url(playlist_url=query)
                    source = await YTDLSource.from_url(
                        url=first_ghneya,
                        loop=self.bot.loop,
                        stream=True
                    )
                    if source:
                        await player.queue.put(source)

                data = await YTDLSource.getData(url=query,
                                                loop=self.bot.loop,
                                                stream=True)
                if 'entries' in data:
                    newData = data['entries']

            if (len(newData) != 0):
                random.shuffle(newData)

                async def queue_rest(entries):
                    for ghneya in entries[1:]:
                        if ghneya is not None:
                            source = await YTDLSource.getData(
                                url=ghneya["url"],
                                loop=self.bot.loop,
                                stream=True
                            )
                            await player.queue.put(source)
                self.bot.loop.create_task(queue_rest(newData))

            else:
                source = await YTDLSource.from_url(
                    url=query,
                    loop=self.bot.loop,
                    stream=True
                )
                if source:
                    await player.queue.put(source)
                    title = source.title if source.title else query
                    await ctx.send(f'✅ Queued: `{title}`')
                else:
                    await ctx.send("❌ Could not find that video/playlist.")
        except Exception as e:
            print(f"Error in stream command: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Error: {type(e).__name__}: {e}")

    @commands.command(name='volume')
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
        if ctx.voice_client.source is None:
            return await ctx.send("Nothing is playing right now.")
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
    @stream.before_invoke
    @now_playing_.before_invoke
    async def ensure_voice(self, ctx):
        print(f"ensure_voice called for {ctx.author}")
        if ctx.voice_client is None:
            print(f"No voice client, checking if author is in voice...")
            if ctx.author.voice:
                print(f"Author is in voice channel: {ctx.author.voice.channel}")
                await ctx.author.voice.channel.connect()
                print(f"Connected to voice channel")
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError(
                    "Author not connected to a voice channel.")
        else:
            print(f"Already have voice client in {ctx.voice_client.channel}")


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

@bot.event
async def on_command_error(ctx, error):
    print(f'Command error in {ctx.command}: {type(error).__name__}: {error}')
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f'❌ Command error: {type(error).__name__}: {error}')

key = "DISCORD_TOKEN"

token = os.getenv(key, default=None)


async def main():
    print(f"Starting bot with token: {token}")
    async with bot:
        await bot.add_cog(Music(bot))
        try:
            await bot.start(token)
        except asyncio.exceptions.CancelledError:
            print("Bot stopped")


asyncio.run(main())
