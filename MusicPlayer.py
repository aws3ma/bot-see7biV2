
import asyncio

import discord
from YTDLSource import YTDLSource
from async_timeout import timeout


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next',
                 'current', 'np', 'volume', 'player_task')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = 1.0
        self.current = None

        self.player_task = ctx.bot.loop.create_task(self.player_loop())
        self.player_task.add_done_callback(self._player_task_finished)

    def _player_task_finished(self, task):
        if task.cancelled():
            return
        error = task.exception()
        if error:
            print(f'Player task stopped: {type(error).__name__}: {error}')

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            print(f'Player received: {getattr(source, "title", "audio source")}')

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(
                        source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(
                        f'There was an error processing your song.\n'
                        f'```css\n[{e}]\n```')
                    continue

            voice_client = self._guild.voice_client
            if voice_client is None or not voice_client.is_connected():
                await self._channel.send('Playback stopped because I am not connected to voice.')
                continue

            source.volume = self.volume
            self.current = source

            def playback_finished(error):
                if error:
                    print(f'Playback error: {type(error).__name__}: {error}')
                self.bot.loop.call_soon_threadsafe(self.next.set)

            try:
                voice_client.play(source, after=playback_finished)
            except Exception as error:
                print(f'Could not start playback: {type(error).__name__}: {error}')
                await self._channel.send(
                    f'Could not start playback: `{type(error).__name__}: {error}`')
                source.cleanup()
                self.current = None
                continue

            print(f'Playback started: {source.title}')
            self.np = await self._channel.send(f'**playing :** {source.title}')
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))
