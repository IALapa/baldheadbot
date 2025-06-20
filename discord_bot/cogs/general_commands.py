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
            await message.channel.send(f"안녕하세요, {message.author.mention}님!")

    @commands.command(name="ping", help="봇의 응답 속도를 보여줍니다.")
    async def ping(self, ctx: commands.Context):
        """봇의 현재 지연 시간을 밀리초(ms) 단위로 응답합니다."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"퐁! 현재 응답 속도는 {latency}ms 입니다.")

    @commands.command(name="서버정보", aliases=["serverinfo"], help="현재 서버의 정보를 보여줍니다.")
    async def server_info(self, ctx: commands.Context):
        """현재 서버에 대한 정보를 임베드 메시지로 표시합니다."""
        embed = discord.Embed(title=f"{ctx.guild.name} 서버 정보", color=discord.Color.blue(), timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.add_field(name="서버 ID", value=ctx.guild.id, inline=False)
        embed.add_field(name="서버 주인", value=ctx.guild.owner.mention, inline=True)
        embed.add_field(name="멤버 수", value=ctx.guild.member_count, inline=True)
        embed.add_field(name="채널 수", value=f"텍스트: {len(ctx.guild.text_channels)}, 음성: {len(ctx.guild.voice_channels)}", inline=False)
        embed.add_field(name="서버 생성일", value=discord.utils.format_dt(ctx.guild.created_at, style='F'), inline=False)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """이 Cog를 봇에 추가하기 위해 discord.py가 호출하는 함수입니다."""
    await bot.add_cog(GeneralCommands(bot))
    print("GeneralCommands Cog가 로드되었습니다.")