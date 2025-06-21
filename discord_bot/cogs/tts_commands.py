import discord
from discord.ext import commands
from gtts import gTTS
from io import BytesIO
import asyncio
import functools

# core 폴더의 유틸리티들을 임포트
from core import embed

class TTSCommands(commands.Cog):
    """사용자별 TTS 기능을 관리하는 Cog입니다."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # TTS가 활성화된 사용자의 ID를 저장하는 집합(set)
        self.tts_enabled_users = set()

    # --- TTS 기능을 켜고 끄는 명령어 그룹 ---
    @commands.hybrid_group(name="tts", description="TTS 기능을 켜거나 끕니다.")
    async def tts(self, ctx: commands.Context):
        """TTS 기능의 메인 명령어 그룹입니다. 서브 커맨드를 사용해주세요."""
        # 서브 커맨드 없이 호출될 경우 간단한 안내 메시지 전송
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=self.bot.embeds.info(
                "TTS 명령어 안내",
                f"TTS 기능을 사용하려면 `{ctx.prefix}tts 켜기` 또는 `{ctx.prefix}tts 끄기`를 입력해주세요."
            ))

    @tts.command(name="켜기", description="당신의 메시지를 음성으로 읽어주는 TTS 기능을 활성화합니다.")
    async def tts_on(self, ctx: commands.Context):
        author = ctx.author

        if author.id in self.tts_enabled_users:
            return await ctx.send(embed=self.bot.embeds.error("오류", "TTS 기능이 이미 켜져 있습니다."), ephemeral=True)
        
        if not author.voice or not author.voice.channel:
            return await ctx.send(embed=self.bot.embeds.error("오류", "먼저 음성 채널에 접속해주세요."), ephemeral=True)

        # 봇이 음성 채널에 없으면 사용자의 채널로 접속
        if not ctx.voice_client:
            await author.voice.channel.connect()

        self.tts_enabled_users.add(author.id)
        await ctx.send(embed=self.bot.embeds.success("TTS 활성화", f"{author.mention}님의 메시지를 이제부터 읽어줍니다."), ephemeral=True)

    @tts.command(name="끄기", description="TTS 기능을 비활성화합니다.")
    async def tts_off(self, ctx: commands.Context):
        author = ctx.author

        if author.id not in self.tts_enabled_users:
            return await ctx.send(embed=self.bot.embeds.error("오류", "TTS 기능이 이미 꺼져 있습니다."), ephemeral=True)

        self.tts_enabled_users.remove(author.id)
        await ctx.send(embed=self.bot.embeds.success("TTS 비활성화", f"{author.mention}님의 TTS 기능이 꺼졌습니다."), ephemeral=True)


    # --- 메시지를 감지하여 TTS를 실행하는 리스너 ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 봇 자신의 메시지, DM, 명령어는 무시
        if message.author.bot or not message.guild or message.content.startswith(('!', '/', '?', '.')): # 사용중인 접두사들
            return

        # TTS가 활성화된 사용자의 메시지인지 확인
        if message.author.id not in self.tts_enabled_users:
            return

        # 봇이 음성 채널에 연결되어 있는지 확인
        voice_client = message.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            # 사용자가 음성 채널에 있는데 봇이 없다면, 다시 접속 시도
            if message.author.voice:
                try:
                    voice_client = await message.author.voice.channel.connect()
                except Exception as e:
                    print(f"TTS 자동 재접속 실패: {e}")
                    return
            else:
                return

        # --- 음악 재생과의 충돌 방지 ---
        # 현재 음악을 재생 중이거나, 일시정지 중이면 TTS를 실행하지 않음
        if voice_client.is_playing() or voice_client.is_paused():
            return

        # gTTS를 사용하여 텍스트를 음성으로 변환 (메모리 상에서 처리)
        try:
            # gTTS가 너무 긴 텍스트는 처리하지 못할 수 있으므로 200자로 제한
            text_to_read = message.content[:200]
            
            # gTTS 실행은 동기 함수이므로, run_in_executor로 비동기 처리
            tts = gTTS(text=text_to_read, lang='ko')
            fp = BytesIO()
            
            loop = asyncio.get_running_loop()
            blocking_task = functools.partial(tts.write_to_fp, fp)
            await loop.run_in_executor(None, blocking_task)
            
            fp.seek(0)
            
            # 변환된 음성 데이터를 FFmpeg으로 재생
            source = discord.FFmpegPCMAudio(fp, pipe=True)
            voice_client.play(source)

            # --- TTS 기본 볼륨을 50%로 설정합니다. ---
            if voice_client.source:
                voice_client.source.volume = 0.5
            # --------------------------------------

        except Exception as e:
            print(f"TTS 생성 또는 재생 중 오류 발생: {e}")


async def setup(bot: commands.Bot):
    """이 Cog를 봇에 추가하기 위해 discord.py가 호출하는 함수입니다."""
    await bot.add_cog(TTSCommands(bot))
    print("TTSCommands Cog가 로드되었습니다.")