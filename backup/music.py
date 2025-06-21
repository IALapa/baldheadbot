import discord
from discord import app_commands # 자동완성을 위해 추가
from discord.ext import commands
import asyncio
import yt_dlp

# yt-dlp 설정
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'auto',
    'quiet': True,
}

# FFmpeg 설정
ffmpeg_opts = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vc = None
        self.queue = []

    # 봇이 혼자 남으면 자동으로 나가는 이벤트 리스너
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id:
            return
        
        if not self.vc or not self.vc.is_connected():
            return

        if len(self.vc.channel.members) == 1:
            await asyncio.sleep(60)
            if self.vc.is_connected() and len(self.vc.channel.members) == 1:
                await self.vc.channel.send("👋 아무도 없어서 채널을 나갈게요!")
                self.queue = []
                await self.vc.disconnect()
                self.vc = None
                print("음성 채널에 혼자 남아 연결을 종료합니다.")

    # 자동완성 기능을 위한 함수
    async def play_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        
        choices = []
        try:
            # ytsearch 뒤에 숫자를 붙여 검색 결과 수를 제한 (예: ytsearch5)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{current}", download=False)
                if 'entries' in info:
                    for entry in info['entries']:
                        title = entry.get('title', 'Unknown Title')
                        # 선택지의 이름(name)과 값(value)을 설정합니다.
                        # 이름이 너무 길 경우 100자 이내로 자릅니다.
                        display_title = title if len(title) <= 100 else title[:97] + "..."
                        choices.append(app_commands.Choice(name=display_title, value=title))
        except Exception as e:
            print(f"Autocomplete error: {e}")

        return choices

    @commands.hybrid_command(name="join", help="음성 채널에 봇을 연결합니다.")
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("먼저 음성 채널에 접속해주세요.")
            return
        channel = ctx.author.voice.channel
        if self.vc and self.vc.is_connected():
            await self.vc.move_to(channel)
        else:
            self.vc = await channel.connect()
        await ctx.send(f"✅ {channel.name} 채널에 연결되었습니다.")

    @commands.hybrid_command(name="leave", help="음성 채널에서 봇을 내보냅니다.")
    async def leave(self, ctx):
        if self.vc and self.vc.is_connected():
            self.queue = []
            await self.vc.disconnect()
            self.vc = None
            await ctx.send("✅ 음성 채널에서 나갔습니다.")
        else:
            await ctx.send("봇이 음성 채널에 연결되어 있지 않습니다.")

    # play 명령어에 자동완성 데코레이터 추가
    @commands.hybrid_command(name="play", description="유튜브 노래를 재생합니다. (검색 또는 URL)")
    @app_commands.autocomplete(search=play_autocomplete)
    async def play(self, ctx: commands.Context, *, search: str):
        if not self.vc or not self.vc.is_connected():
            if ctx.author.voice:
                await self.join(ctx)
            else:
                await ctx.send("음성 채널에 먼저 들어가주세요.")
                return

        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search, download=False)
                
                if 'entries' in info:
                    info = info['entries'][0]

                title = info.get('title', 'Unknown Song')
            except Exception as e:
                print(f"Error extracting info: {e}")
                return await ctx.send(f"❌ 노래 정보를 가져오는데 실패했습니다. URL 또는 검색어를 확인해주세요.")

            song = {'source': search, 'title': title, 'channel': ctx.channel}
            self.queue.append(song)
            await ctx.send(f"✅ '{title}'을(를) 대기열에 추가했습니다.")

            if not self.vc.is_playing() and not self.vc.is_paused():
                await self.play_next_song()

    async def play_next_song(self):
        if self.queue:
            song_info = self.queue.pop(0)
            source = song_info['source']
            title = song_info['title']
            channel = song_info['channel']

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(source, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    stream_url = info['url']
                
                if self.vc and self.vc.is_connected():
                    self.vc.play(discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts), after=lambda e: self.on_song_end(e))
                    self.vc.source.volume = 0.5
                    await channel.send(f"▶️ 이제 '{title}'을(를) 재생합니다.")
                else:
                    self.on_song_end(None)

            except Exception as e:
                print(f"Error playing '{title}': {e}")
                await channel.send(f"❌ '{title}' 재생 중 오류가 발생했습니다. 다음 곡으로 넘어갑니다.")
                self.on_song_end(e)
    
    def on_song_end(self, error):
        if error:
            print(f'Player error: {error}')
        asyncio.run_coroutine_threadsafe(self.play_next_song(), self.bot.loop)

    @commands.hybrid_command(name="volume", help="볼륨을 조절합니다. (0~100)")
    async def volume(self, ctx, volume: int):
        if not self.vc or not self.vc.source:
            return await ctx.send("재생 중인 노래가 없습니다.")
        if 0 <= volume <= 100:
            self.vc.source.volume = volume / 100
            await ctx.send(f"🔊 볼륨을 {volume}%로 조절했습니다.")
        else:
            await ctx.send("볼륨은 0에서 100 사이의 값으로 설정해주세요.")

    @commands.hybrid_command(name="pause", help="노래를 일시정지합니다.")
    async def pause(self, ctx):
        if self.vc and self.vc.is_playing():
            self.vc.pause()
            await ctx.send("⏸️ 노래를 일시정지했습니다.")
        else:
            await ctx.send("재생 중인 노래가 없습니다.")

    @commands.hybrid_command(name="resume", help="노래를 다시 재생합니다.")
    async def resume(self, ctx):
        if self.vc and self.vc.is_paused():
            self.vc.resume()
            await ctx.send("▶️ 노래를 다시 재생합니다.")
        else:
            await ctx.send("일시정지된 노래가 없습니다.")

    @commands.hybrid_command(name="stop", help="노래를 중지하고 대기열을 비웁니다.")
    async def stop(self, ctx):
        if self.vc:
            self.queue = []
            if self.vc.is_playing() or self.vc.is_paused():
                self.vc.stop()
            await ctx.send("⏹️ 노래를 중지하고 대기열을 초기화했습니다.")
        else:
            await ctx.send("봇이 음성 채널에 없습니다.")
            
    @commands.hybrid_command(name="skip", help="현재 노래를 건너뜁니다.")
    async def skip(self, ctx):
        if self.vc and self.vc.is_playing():
            self.vc.stop()
            await ctx.send("⏭️ 현재 곡을 건너뛰었습니다.")
        else:
            await ctx.send("재생 중인 노래가 없습니다.")
            
    @commands.hybrid_command(name="queue", help="재생 대기열을 보여줍니다.")
    async def queue_info(self, ctx):
        if not self.queue:
            return await ctx.send("대기열에 노래가 없습니다.")
        
        q_list = ""
        for i, song in enumerate(self.queue):
            q_list += f"{i+1}. {song['title']}\n"
            
        embed = discord.Embed(title="🎶 재생 대기열", description=q_list, color=discord.Color.blue())
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))