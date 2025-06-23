import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import functools
from typing import List
import os

# --- core 폴더의 유틸리티들을 임포트합니다. ---
from core import check, embed, exceptions



# yt-dlp 설정
ydl_opts = {
    # opus 포맷을 최우선으로, 없으면 webm, 그 다음으로 bestaudio 순으로 선택
    'format': 'bestaudio[ext=opus]/bestaudio[ext=webm]/bestaudio/best',
    'noplaylist': True,
    'default_search': 'scsearch', # 사운드클라우드
    'no_warnings': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus', # 최종 코덱을 opus로 지정
        'preferredquality': '128', # 비트레이트 품질
    }],
    # ...
}


# FFmpeg 설정
ffmpeg_opts = {
    'options': '-vn -b:a 128k', # 오디오 비트레이트를 128kbps로 고정 (선택 사항)
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
        if self.view: # view가 None이 아닐 때만 stop 및 edit 실행
            self.view.stop()
            if self.view.message:
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
        send_kwargs = {'ephemeral': True} if interaction else {}

        try:
            loop = asyncio.get_running_loop()
            
            # 사운드클라우드는 라이브 스트림 구분이 필요 없으므로 로직을 간소화합니다.
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                blocking_task = functools.partial(ydl.extract_info, search_term, download=False)
                info = await loop.run_in_executor(None, blocking_task)
            
            if 'entries' in info: info = info['entries'][0]
            title = info.get('title', 'Unknown Song')
            source_url = info.get('webpage_url', search_term) # webpage_url을 사용

        except Exception as e:
            print(f"Error extracting info: {e}")
            embed = self.bot.embeds.error("정보 추출 실패", "노래의 상세 정보를 가져오는데 실패했습니다.")
            return await send_method(embed=embed, **send_kwargs)

        # 사운드클라우드는 is_live 개념이 없으므로 항상 False로 처리
        song = {'source': source_url, 'title': title, 'channel': ctx.channel, 'requester': ctx.author, 'is_live': False}
        self.queue.append(song)
        
        embed = self.bot.embeds.success("대기열 추가", f"'{title}'을(를) 대기열에 추가했습니다.")
        await send_method(embed=embed, **send_kwargs)

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await self.play_next_song(ctx)

    @commands.hybrid_command(name="참가", help="음성 채널에 봇을 연결합니다.")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send(embed=self.bot.embeds.error("오류", "먼저 음성 채널에 접속해주세요."))
        
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(embed=self.bot.embeds.success("연결 성공", f"{channel.name} 채널에 연결되었습니다."))

    @commands.hybrid_command(name="빠빠이", help="음성 채널에서 봇을 내보냅니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def leave(self, ctx):
        self.queue = []
        await ctx.voice_client.disconnect()
        await ctx.send(embed=self.bot.embeds.info("연결 종료", "음성 채널에서 나갔습니다."))

    # --- play 명령어: 자동완성 기능 제거 후 간소화 ---
    @commands.hybrid_command(name="재생", description="노래를 추가하거나, 대기열의 특정 노래를 재생합니다.")
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
    @commands.hybrid_command(name="검색", aliases=["search"], description="사운드클라우드에서 노래를 검색하고 목록에서 선택하여 재생합니다.")
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
                # 검색 대상을 ytsearch10 -> scsearch10 으로 변경
                blocking_task = functools.partial(ydl.extract_info, f"scsearch10:{query}", download=False, process=False)
                info = await loop.run_in_executor(None, blocking_task)

            if not info or not info.get('entries'):
                return await send_method(embed=self.bot.embeds.error("검색 실패", "검색 결과가 없습니다."), ephemeral=True if ctx.interaction else False)

            entries = list(info['entries'])

        except Exception as e:
            return await send_method(embed=self.bot.embeds.error("검색 오류", str(e)), ephemeral=True if ctx.interaction else False)

        # --- SearchView와 SongSelect는 사운드클라우드에서도 재사용 가능합니다 ---
        # 다만, SelectOption에 들어갈 데이터를 사운드클라우드에 맞게 수정합니다.
        
        # 1. SearchView 클래스의 _create_select_options 메서드 수정
        #    재생 횟수(view_count) -> 재생 시간(duration_string)으로 변경하거나 둘 다 표시
        #    (이 부분은 Music(commands.Cog) 클래스 안에 있는 SearchView 클래스를 직접 수정해야 합니다)
        
        # 2. 이 search 함수 내에서 options를 만드는 로직 수정
        options = []
        for i, entry in enumerate(entries):
            title = entry.get('title', '이름 없는 항목')
            uploader = entry.get('uploader', 'Unknown Artist')
            duration = entry.get('duration', 0)
            # 초 단위의 duration을 '분:초' 형태로 변환
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "N/A"

            # [핵심] URL을 직접 사용. 유튜브처럼 ID로 조립하지 않습니다.
            url = entry.get('webpage_url')
            if not url:
                continue
            
            label = f"{i+1}. {title}"
            
            # discord.SelectOption: 드롭다운의 각 항목
            options.append(discord.SelectOption(
                label=label[:100],
                description=f"아티스트: {uploader} | 길이: {duration_str}"[:100],
                value=url # Select의 값으로 사운드클라우드 URL을 직접 사용
            ))

        if not options:
            return await send_method(embed=self.bot.embeds.error("검색 실패", "재생 가능한 트랙이 검색 결과에 없습니다."), ephemeral=True if ctx.interaction else False)

        options = options[:25]

        view = discord.ui.View(timeout=60.0)
        # SongSelect 클래스는 수정 없이 재사용 가능
        view.add_item(SongSelect(ctx=ctx, options=options))
        
        # (이하 View 관련 로직은 기존 코드와 거의 동일하게 사용)
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
            description += f"**{i+1}.** {option.label.split('. ', 1)[1]}\n"
        
        initial_embed = self.bot.embeds.info("사운드클라우드 검색 결과", description)
        
        first_playable_entry = next((e for e in entries if e.get('id')), None)
        if first_playable_entry and first_playable_entry.get('thumbnail'):
            initial_embed.set_image(url=first_playable_entry['thumbnail'])
        
        initial_embed.set_footer(text="아래 메뉴에서 재생할 트랙을 선택하세요.")

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

                    embed = self.bot.embeds.info("재생 시작", f"▶️ 이제 '{title}'을(를) 재생합니다.")
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

    @commands.hybrid_group(name="볼륨", aliases=["volume"], description="봇의 볼륨 관련 설정을 관리합니다.")
    async def volume(self, ctx: commands.Context):
        """볼륨 명령어 그룹입니다. 서브 커맨드가 없으면 현재 상태를 보여줍니다."""
        if ctx.invoked_subcommand is None:
            await self.status(ctx)

    @volume.command(name="설정", description="개인별 볼륨 배율을 조절합니다 (기본값 100).")
    async def volume_set(self, ctx: commands.Context, 배율: commands.Range[int, 0, 200]):
        """기본 볼륨에 대한 배율을 조절합니다. (0~200%)"""
        guild_id = ctx.guild.id
        multiplier = 배율 / 100.0
        self.user_volume_multipliers[guild_id] = multiplier
        
        # 현재 재생 중인 노래가 있다면, 새 배율을 즉시 적용
        if ctx.voice_client and ctx.voice_client.source:
            base_volume = self.base_volumes.get(guild_id, self.DEFAULT_BASE_VOLUME)
            final_volume = base_volume * multiplier
            ctx.voice_client.source.volume = final_volume
            
        await ctx.send(embed=self.bot.embeds.success("배율 설정 완료", f"🔊 개인 볼륨 배율을 **{배율}%**로 조절했습니다."), ephemeral=True)

    @volume.command(name="기본", description="이 서버의 기본 볼륨을 조절합니다 (0~100).")
    @commands.has_permissions(manage_guild=True) # '서버 관리' 권한이 있는 사람만 사용 가능
    async def volume_base(self, ctx: commands.Context, 기본볼륨: commands.Range[int, 0, 100]):
        """서버의 기본 시작 볼륨을 조절합니다. 모든 유저에게 적용됩니다."""
        guild_id = ctx.guild.id
        base_volume = 기본볼륨 / 100.0
        self.base_volumes[guild_id] = base_volume
        
        # 현재 재생 중인 노래가 있다면, 새 기본 볼륨을 즉시 적용
        if ctx.voice_client and ctx.voice_client.source:
            user_multiplier = self.user_volume_multipliers.get(guild_id, 1.0)
            final_volume = base_volume * user_multiplier
            ctx.voice_client.source.volume = final_volume
            
        await ctx.send(embed=self.bot.embeds.success("기본 볼륨 설정 완료", f"🔊 이 서버의 기본 볼륨을 **{기본볼륨}%**로 조절했습니다."))

    @volume.command(name="상태", description="현재 볼륨 설정을 확인합니다.")
    async def status(self, ctx: commands.Context):
        """현재 서버의 기본 볼륨과 개인 배율, 최종 볼륨을 보여줍니다."""
        guild_id = ctx.guild.id
        base_volume = self.base_volumes.get(guild_id, self.DEFAULT_BASE_VOLUME)
        user_multiplier = self.user_volume_multipliers.get(guild_id, 1.0)
        final_volume = base_volume * user_multiplier
        
        description = (
            f"**기본 볼륨:** `{int(base_volume * 100)}%`\n"
            f"**개인 배율:** `{int(user_multiplier * 100)}%`\n"
            f"--------------------\n"
            f"**최종 적용 볼륨:** `{int(final_volume * 100)}%`"
        )
        await ctx.send(embed=self.bot.embeds.info("현재 볼륨 설정", description))

    # pause 명령어는 '재생 중'일 때만 일시정지하는 것이 맞으므로, is_bot_playing()을 유지합니다.
    @commands.hybrid_command(name="일시정지", help="노래를 일시정지합니다.")
    @check.is_bot_playing() 
    async def pause(self, ctx):
        if ctx.voice_client.is_paused():
            return await ctx.send(embed=self.bot.embeds.error("오류", "이미 일시정지된 상태입니다."))
        ctx.voice_client.pause()
        await ctx.send(embed=self.bot.embeds.info("일시정지", "⏸️ 노래를 일시정지했습니다."))

    @commands.hybrid_command(name="계속", help="노래를 다시 재생합니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def resume(self, ctx):
        # 명령어 내부에서 is_paused() 상태를 직접 확인
        if not ctx.voice_client.is_paused():
            return await ctx.send(embed=self.bot.embeds.error("오류", "일시정지된 노래가 없습니다."))
        ctx.voice_client.resume()
        await ctx.send(embed=self.bot.embeds.info("다시 재생", "▶️ 노래를 다시 재생합니다."))
            
    @commands.hybrid_command(name="중지", help="노래를 중지하고 대기열을 비웁니다.")
    @check.is_bot_connected() # 수정: is_bot_playing -> is_bot_connected
    async def stop(self, ctx):
        self.queue = []
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        await ctx.send(embed=self.bot.embeds.info("재생 중지", "⏹️ 노래를 중지하고 대기열을 초기화했습니다."))

    # skip 명령어는 '재생 중'인 곡을 건너뛰는 것이므로, is_bot_playing()을 유지합니다.
    @commands.hybrid_command(name="스킵", help="현재 노래를 건너뜁니다.")
    @check.is_bot_playing() 
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await ctx.send(embed=self.bot.embeds.info("건너뛰기", "⏭️ 현재 곡을 건너뛰었습니다."))
            
    
    @commands.hybrid_command(name="대기열", help="재생 대기열을 보여줍니다.")
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
