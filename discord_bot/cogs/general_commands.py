import discord
from discord.ext import commands
import datetime

class GeneralCommands(commands.Cog):
    """일반 사용자를 위한 명령어들을 포함하는 Cog입니다."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 봇 자신의 메시지는 무시
        if message.author == self.bot.user:
            return

        # 간단한 응답 예시
        if "안녕" in message.content.lower() and self.bot.user.mentioned_in(message):
            # 이 부분도 원한다면 self.bot.embeds.info() 를 사용할 수 있습니다.
            await message.channel.send(f"안녕하세요, {message.author.mention}님!")

    # --- ping 명령어 수정 ---
    @commands.hybrid_command(name="ping", help="봇의 응답 속도를 보여줍니다.")
    async def ping(self, ctx: commands.Context):
        """봇의 현재 지연 시간을 밀리초(ms) 단위로 응답합니다."""
        latency = round(self.bot.latency * 1000)
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # self.bot.embeds를 사용하여 표준 정보 임베드를 생성합니다.
        embed = self.bot.embeds.info(
            title="퐁! 🏓",
            description=f"현재 시각 **{time}** , 봇의 응답 속도는 **{latency}ms** 입니당!"
        )
        await ctx.send(embed=embed)

    # --- 서버정보 명령어 수정 ---
    @commands.hybrid_command(name="서버정보", aliases=["serverinfo"], help="현재 서버의 정보를 보여줍니다.")
    async def server_info(self, ctx: commands.Context):
        """현재 서버에 대한 정보를 임베드 메시지로 표시합니다."""
        # self.bot.embeds를 사용하여 표준 정보 임베드의 '기본 틀'을 생성합니다.
        # 제목만 설정하고, 설명은 비워둡니다.
        embed = self.bot.embeds.info(
            title=f"{ctx.guild.name} 서버 정보"
        )
        
        # 썸네일 설정
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
            
        # .add_field()를 사용하여 필요한 정보들을 '기본 틀'에 추가합니다.
        embed.add_field(name="서버 ID", value=f"`{ctx.guild.id}`", inline=False)
        embed.add_field(name="서버 주인", value=ctx.guild.owner.mention, inline=True)
        embed.add_field(name="멤버 수", value=f"{ctx.guild.member_count} 명", inline=True)
        embed.add_field(name="채널 수", value=f"텍스트: {len(ctx.guild.text_channels)}개 / 음성: {len(ctx.guild.voice_channels)}개", inline=False)
        
        # discord.utils.format_dt를 사용하여 시간을 사용자의 지역에 맞게 표시
        embed.add_field(name="서버 생성일", value=discord.utils.format_dt(ctx.guild.created_at, style='F'), inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """이 Cog를 봇에 추가하기 위해 discord.py가 호출하는 함수입니다."""
    await bot.add_cog(GeneralCommands(bot))
    print("GeneralCommands Cog가 로드되었습니다.")