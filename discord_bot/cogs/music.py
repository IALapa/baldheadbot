import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import functools
from typing import List

# --- core 폴더의 유틸리티들을 임포트합니다. ---
from core import check, embed, exceptions

# yt-dlp 설정
ydl_opts = {
    # opus 포맷을 최우선으로, 없으면 webm, 그 다음으로 bestaudio 순으로 선택
    'format': 'bestaudio[ext=opus]/bestaudio[ext=webm]/bestaudio/best',
    'noplaylist': True,
    'default_search': 'auto',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus', # 최종 코덱을 opus로 지정
        'preferredquality': '192', # 비트레이트 품질
    }],
    # ...
}

# FFmpeg 설정
ffmpeg_opts = {
    'options': '-vn -b:a 192k', # 오디오 비트레이트를 96kbps로 고정 (선택 사항)
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 15M',
}

'''
수정된 옵션 설명:

-probesize 20M -analyzeduration 15M: FFmpeg가 스트림의 형식을 분석하기 위해 더 많은 데이터를 미리 읽도록 설정합니다. 불안정한 인터넷 스트림을 처리할 때 분석 오류를 줄이고 안정성을 높여줍니다.
-b:a 192k (선택 사항): 오디오 비트레이트(bitrate)를 192kbps로 고정합니다. 음질을 일정 수준으로 유지하면서 데이터 전송량을 안정시키는 데 도움이 될 수 있습니다.
'''

# --- 검색 결과를 표시하고 상호작용을 처리할 View 클래스 ---
class SearchView(discord.ui.View):
    def __init__(self, *, ctx: commands.Context, search_results: List[dict]):
        super().__init__(timeout=60.0) # 60초 후 타임아웃
        self.ctx = ctx
        self.bot = ctx.bot
        self.search_results = search_results

        # 검색 결과를 바탕으로 드롭다운 메뉴를 생성하여 View에 추가
        self.add_item(SongSelect(ctx=ctx, options=self._create_select_options()))

    def _create_select_options(self) -> List[discord.SelectOption]:
        """검색 결과로 SelectOption 목록을 생성합니다."""
        options = []
        for i, entry in enumerate(self.search_results):
            # discord.SelectOption: 드롭다운의 각 항목
            options.append(discord.SelectOption(
                label=f"{i+1}. {entry['title']}"[:100], # 라벨은 최대 100자
                description=f"D: {entry.get('duration_string', 'N/A')} | V: {entry.get('view_count', 0):,}"[:100],
                value=str(i) # 값으로는 리스트의 인덱스를 사용
            ))
        return options

    async def on_timeout(self):
        """View가 시간 초과되었을 때 호출됩니다."""
        if self.message:
            # 시간 초과 시 메시지 내용을 수정하고 모든 UI를 비활성화
            timeout_embed = self.bot.embeds.error("시간 초과", "60초가 지나 선택이 취소되었습니다.")
            await self.message.edit(embed=timeout_embed, view=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """이 View와 상호작용할 수 있는 사용자인지 확인합니다."""
        # 명령어를 실행한 사용자만 이 View를 조작할 수 있도록 제한
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("명령어를 실행한 사용자만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True


# --- 드롭다운 메뉴 자체를 정의하는 Select 클래스 ---
class SongSelect(discord.ui.Select):
    def __init__(self, *, ctx: commands.Context, options: List[discord.SelectOption]):
        super().__init__(placeholder="재생할 노래를 선택하세요...", min_values=1, max_values=1, options=options)
        self.ctx = ctx
        self.bot = ctx.bot

    async def callback(self, interaction: discord.Interaction):
        """사용자가 드롭다운 메뉴에서 옵션을 선택했을 때 호출됩니다."""
        # 선택된 값 (이제는 영상의 URL)을 가져옴
        selected_url = self.values[0]
        
        # 원본 검색 결과 메시지를 수정하여 로딩 중임을 알림
        await interaction.response.defer()

        # music_cog를 찾아서 내부 함수 호출
        music_cog = self.bot.get_cog('Music')
        if music_cog:
            # 선택된 노래의 URL을 사용하여 재생 큐에 추가
            # _queue_and_play 함수가 상세 정보 로딩을 처리해 줄 것임
            await music_cog._queue_and_play(self.ctx, selected_url, interaction)
        
        # _queue_and_play에서 후속 응답을 처리하므로 여기서는 view만 비활성화
        self.view.stop()
        await self.view.message.edit(view=None)

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.vc는 더 이상 클래스 변수로 사용하지 않고, ctx.voice_client를 통해 접근합니다.
        self.queue = []
        self.current_song_info = None

        # 서버(Guild) ID를 키로, 볼륨 배율을 값으로 저장하는 딕셔너리
        self.user_volume_multipliers = {}
        # 서버(Guild) ID를 키로, 기본 볼륨을 값으로 저장
        self.base_volumes = {}
        # 기본 볼륨을 상수로 정의하여 관리 용이성을 높임
        self.DEFAULT_BASE_VOLUME = 0.2

    # --- Cog 전용 에러 핸들러를 추가하여 커스텀 에러를 처리합니다. ---
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 이 Cog 내에서 발생하는 명령어 에러만 처리
        if ctx.cog is not self:
            return
            
        # 우리가 정의한 커스텀 에러들을 여기서 처리
        if isinstance(error, exceptions.BotNotConnected):
            await ctx.send(embed=self.bot.embeds.error("오류", "봇이 음성 채널에 먼저 참여해야 해요."))
        elif isinstance(error, exceptions.NotPlayingMusic):
            await ctx.send(embed=self.bot.embeds.error("오류", "현재 재생 중인 노래가 없어요."))
        else:
            # 처리되지 않은 다른 에러는 터미널에 출력
            print(f"{ctx.command.name} 명령어 처리 중 오류 발생: {error}")

    # cogs/music.py 의 on_voice_state_update 함수를 아래 코드로 교체
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # 봇 자신의 상태 변경은 무시
        if member.id == self.bot.user.id:
            return
        
        # 봇의 음성 클라이언트(voice_client)를 가져옴
        voice_client = member.guild.voice_client
        
        # 봇이 음성 채널에 없으면 아무것도 하지 않음
        if not voice_client:
            return

        # --- 핵심 개선 로직 ---
        # before.channel: 유저가 '이전'에 있던 채널
        # after.channel: 유저가 '이후'에 있는 채널
        # 누군가가 봇이 있는 채널에서 나갔을 경우 (다른 채널로 이동했거나, 연결을 끊었을 때)
        if before.channel == voice_client.channel and after.channel != voice_client.channel:
            # 채널에 봇 혼자 남았는지 확인
            if len(voice_client.channel.members) == 1:
                # 60초 대기 후에도 여전히 혼자인지 최종 확인
                await asyncio.sleep(60)
                if voice_client.is_connected() and len(voice_client.channel.members) == 1:
                    await voice_client.channel.send(embed=self.bot.embeds.info("자동 퇴장", "아무도 없어서 채널을 나갈게요! 👋"))
                    self.queue = [] # 대기열 초기화
                    await voice_client.disconnect()

    # --- 큐 추가 및 재생 시작을 위한 내부 헬퍼 함수 ---
    async def _queue_and_play(self, ctx: commands.Context, search_term: str, interaction: discord.Interaction = None):
        """노래 정보를 추출하고, 큐에 추가한 뒤, 필요하면 재생을 시작하는 내부 함수"""
        send_method = interaction.followup.send if interaction else ctx.send
        # 슬래시 명령어일 경우에만 ephemeral 옵션을 사용
        send_kwargs = {'ephemeral': True} if interaction else {}

        try:
            loop = asyncio.get_running_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                blocking_task = functools.partial(ydl.extract_info, search_term, download=False)
                info = await loop.run_in_executor(None, blocking_task)
            
            if 'entries' in info: info = info['entries'][0]
            title = info.get('title', 'Unknown Song')

        except Exception as e:
            print(f"Error extracting info: {e}")
            embed = self.bot.embeds.error("정보 추출 실패", "노래의 상세 정보를 가져오는데 실패했습니다.")
            return await send_method(embed=embed, **send_kwargs)

        song = {'source': info['webpage_url'], 'title': title, 'channel': ctx.channel, 'requester': ctx.author}
        self.queue.append(song)
        embed = self.bot.embeds.success("대기열 추가", f"'{title}'을(를) 대기열에 추가했습니다.")
        await send_method(embed=embed, **send_kwargs)

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await self.play_next_song(ctx)

    @commands.hybrid_command(name="join", help="음성 채널에 봇을 연결합니다.")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send(embed=self.bot.embeds.error("오류", "먼저 음성 채널에 접속해주세요."))
        
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(embed=self.bot.embeds.success("연결 성공", f"{channel.name} 채널에 연결되었습니다."))

    @commands.hybrid_command(name="leave", help="음성 채널에서 봇을 내보냅니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def leave(self, ctx):
        self.queue = []
        await ctx.voice_client.disconnect()
        await ctx.send(embed=self.bot.embeds.info("연결 종료", "음성 채널에서 나갔습니다."))

    # --- play 명령어: 자동완성 기능 제거 후 간소화 ---
    @commands.hybrid_command(name="play", description="노래를 추가하거나, 대기열의 특정 노래를 재생합니다.")
    async def play(self, ctx: commands.Context, *, search: str):
        """
        검색어 입력 시: 첫 결과를 대기열에 추가합니다.
        숫자 입력 시: 대기열의 해당 번호 노래를 즉시 재생합니다.
        """
        if not ctx.voice_client:
            if ctx.author.voice:
                # 사용자가 음성 채널에 있으면 자동으로 join
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send(embed=self.bot.embeds.error("오류", "음성 채널에 먼저 들어가주세요."))

        # --- 대기열 번호로 재생하는 기능 추가 ---
        if search.isdigit():
            index = int(search)
            if not self.queue:
                return await ctx.send(embed=self.bot.embeds.error("오류", "대기열이 비어있습니다."))
            if not 1 <= index <= len(self.queue):
                return await ctx.send(embed=self.bot.embeds.error("입력 오류", f"1에서 {len(self.queue)} 사이의 번호를 입력해주세요."))

            # 사용자가 선택한 노래를 대기열에서 꺼냄
            song_to_play = self.queue.pop(index - 1)
            # 대기열의 가장 맨 앞에 다시 삽입
            self.queue.insert(0, song_to_play)

            # 현재 재생 중인 노래를 멈춰서 다음 곡(방금 맨 앞에 넣은 곡)으로 넘어감
            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                ctx.voice_client.stop()
            else:
                # 만약 아무것도 재생 중이 아니었다면 바로 재생 시작
                await self.play_next_song(ctx)
            
            await ctx.send(embed=self.bot.embeds.success("재생 목록 변경", f"대기열의 {index}번째 노래 '{song_to_play['title']}'을(를) 바로 재생합니다."))
            return # 번호 재생 로직은 여기서 종료

        # --- 기존의 새 노래 추가 로직 ---
        # defer()가 필요하므로 슬래시/접두사 구분이 필요
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        
        await self._queue_and_play(ctx, search, interaction=ctx.interaction)

        if ctx.interaction:
            # defer에 대한 후속 응답이 _queue_and_play에서 처리되므로 여기선 응답하지 않음
            # 단, "생각 중..." 메시지를 삭제하고 싶다면 아래 코드를 활성화
            await ctx.interaction.delete_original_response()


    # --- 검색(search) 명령어: UI View를 사용하도록 대폭 수정 ---
    @commands.hybrid_command(name="검색", aliases=["search"], description="노래를 검색하고 목록에서 선택하여 재생합니다.")
    async def search(self, ctx: commands.Context, *, query: str):
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send(embed=self.bot.embeds.error("오류", "음성 채널에 먼저 들어가주세요."))

        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            send_method = ctx.interaction.followup.send
        else:
            send_method = ctx.send

        try:
            loop = asyncio.get_running_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                blocking_task = functools.partial(ydl.extract_info, f"ytsearch10:{query}", download=False, process=False)
                info = await loop.run_in_executor(None, blocking_task)

            if not info or not info.get('entries'):
                return await send_method(embed=self.bot.embeds.error("검색 실패", "검색 결과가 없습니다."), ephemeral=True if ctx.interaction else False)

            entries = list(info['entries'])

        except Exception as e:
            return await send_method(embed=self.bot.embeds.error("검색 오류", str(e)), ephemeral=True if ctx.interaction else False)

        options = []
        for i, entry in enumerate(entries):
            video_id = entry.get('id')
            title = entry.get('title', '이름 없는 항목')
            if not video_id:
                continue
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # --- 핵심 수정 부분: 선택지(Option) 라벨에 번호를 추가하고 길이를 조절합니다. ---
            prefix = f"{i+1}. "
            # 100자 제한에 맞춰 제목 길이를 동적으로 계산
            remaining_len = 100 - len(prefix)
            
            # 제목이 남은 공간보다 길면 '...'으로 축약
            if len(title) > remaining_len:
                truncated_title = title[:remaining_len - 3] + "..."
            else:
                truncated_title = title
            
            final_label = f"{prefix}{truncated_title}"
            # -------------------------------------------------------------------------

            options.append(discord.SelectOption(
                label=final_label, # 번호가 포함된 최종 라벨을 사용
                value=url,
                description=f"ID: {video_id}"[:100]
            ))

        if not options:
            return await send_method(embed=self.bot.embeds.error("검색 실패", "재생 가능한 영상이 검색 결과에 없습니다."), ephemeral=True if ctx.interaction else False)

        options = options[:25]

        view = discord.ui.View(timeout=60.0)
        # SongSelect 클래스에 수정된 options를 전달합니다. SongSelect 클래스는 수정할 필요 없습니다.
        view.add_item(SongSelect(ctx=ctx, options=options))
        
        # --- (이하 View 관련 로직은 이전과 동일) ---
        async def interaction_check(interaction: discord.Interaction) -> bool:
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("명령어를 실행한 사용자만 선택할 수 있습니다.", ephemeral=True)
                return False
            return True
        view.interaction_check = interaction_check
        
        async def on_timeout():
            if hasattr(view, 'message') and view.message:
                timeout_embed = self.bot.embeds.error("시간 초과", "60초가 지나 선택이 취소되었습니다.")
                await view.message.edit(embed=timeout_embed, view=None)
        view.on_timeout = on_timeout

        description = ""
        for i, option in enumerate(options):
            description += f"**{i+1}.** {option.label.split('. ', 1)[1]}\n" # 번호를 제외한 제목만 가져오기
        
        initial_embed = self.bot.embeds.info("노래 검색 결과", description)
        
        first_playable_entry = next((e for e in entries if e.get('id')), None)
        if first_playable_entry and first_playable_entry.get('thumbnail'):
            initial_embed.set_image(url=first_playable_entry['thumbnail'])
        
        initial_embed.set_footer(text="아래 메뉴에서 재생할 노래를 선택하세요.")

        message = await send_method(embed=initial_embed, view=view, ephemeral=True if ctx.interaction else False)
        
        if message:
            view.message = message



    # play_next_song 함수 (수정된 버전)
    async def play_next_song(self, ctx: commands.Context):
        if self.queue:
            song_info = self.queue[0]
            source, title, channel, requester = song_info['source'], song_info['title'], song_info['channel'], song_info['requester']

            try:
                loop = asyncio.get_running_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    blocking_task = functools.partial(ydl.extract_info, source, download=False)
                    info = await loop.run_in_executor(None, blocking_task)

                if 'entries' in info: info = info['entries'][0]
                stream_url = info.get('url')

                if not stream_url:
                    raise ValueError("스트림 URL을 찾을 수 없습니다.")
                
                self.queue.pop(0)

                if ctx.voice_client and ctx.voice_client.is_connected():
                    # --- 핵심 수정 부분: 두 종류의 볼륨을 모두 계산 ---
                    # 1. 이 서버에 설정된 기본 볼륨을 가져옴. 없으면 전역 기본값 사용
                    base_volume = self.base_volumes.get(ctx.guild.id, self.DEFAULT_BASE_VOLUME)
                    # 2. 이 서버에 설정된 사용자 배율을 가져옴. 없으면 기본값 1.0
                    user_multiplier = self.user_volume_multipliers.get(ctx.guild.id, 1.0)
                    # 3. 최종 시작 볼륨을 계산
                    initial_volume = base_volume * user_multiplier

                    base_source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts)
                    # 4. 계산된 최종 볼륨으로 PCMVolumeTransformer를 생성
                    volume_controlled_source = discord.PCMVolumeTransformer(base_source, volume=initial_volume)
                    
                    ctx.voice_client.play(volume_controlled_source, after=lambda e: self.on_song_end(ctx, e))
                    # ---------------------------------------------------------

                    embed = self.bot.embed_generator.info("재생 시작", f"▶️ 이제 '{title}'을(를) 재생합니다.")
                    embed.set_footer(text=f"요청: {requester.display_name}", icon_url=requester.avatar)
                    await channel.send(embed=embed)

            except Exception as e:
                print(f"Error playing '{title}': {e}")
                await channel.send(embed=self.bot.embeds.error("재생 오류", f"'{title}'을(를) 재생하는 중 오류가 발생했습니다."))
                # 오류 발생 시 해당 곡을 큐에서 제거해야 다음 곡으로 넘어갈 수 있음
                if self.queue and self.queue[0]['source'] == source:
                    self.queue.pop(0)
                self.on_song_end(ctx, e)
    
    def on_song_end(self, ctx: commands.Context, error):
        if error: print(f'Player error: {error}')
        if self.queue:
            asyncio.run_coroutine_threadsafe(self.play_next_song(ctx), self.bot.loop)

    @commands.hybrid_command(name="volume", help="볼륨을 조절합니다. (0~100)")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def volume(self, ctx, volume: int):
        # 봇이 연결은 되어있지만, 소스(재생 파일)가 없는 경우를 확인
        if not ctx.voice_client.source:
             return await ctx.send(embed=self.bot.embeds.error("오류", "현재 재생 중인 노래가 없습니다."))

        if not (0 <= volume <= 100):
            return await ctx.send(embed=self.bot.embeds.error("입력 오류", "볼륨은 0에서 100 사이의 값으로 설정해주세요."))
        
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(embed=self.bot.embeds.info("볼륨 조절", f"🔊 볼륨을 {volume}%로 조절했습니다."))

    # pause 명령어는 '재생 중'일 때만 일시정지하는 것이 맞으므로, is_bot_playing()을 유지합니다.
    @commands.hybrid_command(name="pause", help="노래를 일시정지합니다.")
    @check.is_bot_playing() 
    async def pause(self, ctx):
        if ctx.voice_client.is_paused():
            return await ctx.send(embed=self.bot.embeds.error("오류", "이미 일시정지된 상태입니다."))
        ctx.voice_client.pause()
        await ctx.send(embed=self.bot.embeds.info("일시정지", "⏸️ 노래를 일시정지했습니다."))

    @commands.hybrid_command(name="resume", help="노래를 다시 재생합니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def resume(self, ctx):
        # 명령어 내부에서 is_paused() 상태를 직접 확인
        if not ctx.voice_client.is_paused():
            return await ctx.send(embed=self.bot.embeds.error("오류", "일시정지된 노래가 없습니다."))
        ctx.voice_client.resume()
        await ctx.send(embed=self.bot.embeds.info("다시 재생", "▶️ 노래를 다시 재생합니다."))

    @commands.hybrid_command(name="stop", help="노래를 중지하고 대기열을 비웁니다.")
    @check.is_bot_playing() # --- @checks 데코레이터로 중복 코드를 제거합니다. ---
    async def stop(self, ctx):
        self.queue = []
        ctx.voice_client.stop()
        await ctx.send(embed=self.bot.embeds.info("재생 중지", "⏹️ 노래를 중지하고 대기열을 초기화했습니다."))
            
    @commands.hybrid_command(name="stop", help="노래를 중지하고 대기열을 비웁니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def stop(self, ctx):
        self.queue = []
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        await ctx.send(embed=self.bot.embed_s.info("재생 중지", "⏹️ 노래를 중지하고 대기열을 초기화했습니다."))

    # skip 명령어는 '재생 중'인 곡을 건너뛰는 것이므로, is_bot_playing()을 유지합니다.
    @commands.hybrid_command(name="skip", help="현재 노래를 건너뜁니다.")
    @check.is_bot_playing() 
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await ctx.send(embed=self.bot.embeds.info("건너뛰기", "⏭️ 현재 곡을 건너뛰었습니다."))
            
    
    @commands.hybrid_command(name="queue", help="재생 대기열을 보여줍니다.")
    async def queue_info(self, ctx: commands.Context):
        """현재 재생 중인 노래와 재생 대기열을 번호와 함께 보여줍니다."""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()) and not self.queue:
             return await ctx.send(embed=self.bot.embeds.info("대기열", "현재 재생 중인 노래와 대기열에 노래가 없습니다."))

        embed = self.bot.embeds.info("재생 대기열")
        
        # 현재 재생 중인 노래 표시
        if ctx.voice_client.source:
            # 현재 재생 중인 노래의 제목을 찾기 (조금 복잡한 로직)
            # 이 예제에서는 간단하게 표시, 실제로는 현재 곡 정보를 저장하는 변수가 필요할 수 있음
            embed.add_field(name="현재 재생 중", value="▶️ ... (현재 곡 정보)", inline=False)
        
        # 다음 대기열 목록 표시
        if not self.queue:
            embed.description = "다음 대기열에 노래가 없습니다."
        else:
            song_list = ""
            for i, song in enumerate(self.queue):
                # 사용자가 !play 에서 사용할 번호(i+1)를 명확하게 보여줌
                song_list += f"**{i+1}.** {song['title']}\n"
            embed.add_field(name="다음 곡 목록", value=song_list, inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))