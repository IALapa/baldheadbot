import discord
from discord.ext import commands
from typing import Optional

class AdminCommands(commands.Cog):
    """서버 관리를 위한 관리자 전용 명령어들을 포함하는 Cog입니다."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Cog 내에서 발생하는 특정 에러를 처리하는 리스너
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 권한이 부족하여 명령어를 실행할 수 없을 때 사용자에게 알림
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"❌ {ctx.author.mention}님, 이 명령어를 사용할 권한이 없습니다.", delete_after=10)
        # 봇에 권한이 부족할 때
        elif isinstance(error, commands.BotMissingPermissions):
            # error.missing_permissions 리스트에서 권한 이름을 추출하여 메시지 생성
            missing_perms = ", ".join(perm.replace('_', ' ').title() for perm in error.missing_permissions)
            await ctx.send(f"❌ 봇에게 다음 권한이 없어 명령어를 실행할 수 없습니다: `{missing_perms}`", delete_after=10)
        # 그 외의 경우, 터미널에 에러를 출력 (디버깅용)
        else:
            print(f"{ctx.command.name} 명령어 처리 중 오류 발생: {error}")

    @commands.hybrid_command(name="밴", description="서버에서 멤버를 영구적으로 추방합니다.")
    @commands.has_permissions(ban_members=True) # '멤버 추방' 권한이 있는 사용자만 사용 가능
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "별도의 사유 없음"):
        """지정한 멤버를 서버에서 밴(추방)합니다. 봇과 명령어 사용자 모두에게 '멤버 추방' 권한이 필요합니다."""
        if member == ctx.author:
            await ctx.send("자기 자신을 밴할 수 없습니다.", ephemeral=True)
            return
        if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
            await ctx.send("자신보다 역할이 높거나 같은 멤버를 밴할 수 없습니다.", ephemeral=True)
            return
            
        await member.ban(reason=reason)
        
        embed = discord.Embed(title="멤버 밴", color=discord.Color.red())
        embed.add_field(name="대상", value=member.mention, inline=True)
        embed.add_field(name="실행자", value=ctx.author.mention, inline=True)
        embed.add_field(name="사유", value=reason, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="킥", description="서버에서 멤버를 일시적으로 내보냅니다.")
    @commands.has_permissions(kick_members=True) # '멤버 내보내기' 권한이 있는 사용자만 사용 가능
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "별도의 사유 없음"):
        """지정한 멤버를 서버에서 킥(내보내기)합니다. 재초대 시 다시 들어올 수 있습니다."""
        if member == ctx.author:
            await ctx.send("자기 자신을 킥할 수 없습니다.", ephemeral=True)
            return
        if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
            await ctx.send("자신보다 역할이 높거나 같은 멤버를 킥할 수 없습니다.", ephemeral=True)
            return

        await member.kick(reason=reason)

        embed = discord.Embed(title="멤버 킥", color=discord.Color.orange())
        embed.add_field(name="대상", value=member.mention, inline=True)
        embed.add_field(name="실행자", value=ctx.author.mention, inline=True)
        embed.add_field(name="사유", value=reason, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="청소", description="채팅 채널의 메시지를 지정한 수만큼 삭제합니다.")
    @commands.has_permissions(manage_messages=True) # '메시지 관리' 권한이 있는 사용자만 사용 가능
    async def clear(self, ctx: commands.Context, amount: commands.Range[int, 1, 100]):
    # --- 핵심 수정 부분: defer와 followup을 사용하도록 변경 ---

        # 1. 슬래시 명령어로 호출되었는지 확인하고, 맞다면 defer()로 응답을 지연시킵니다.
        # ephemeral=True로 설정하여 "생각 중..." 메시지가 명령어 사용자에게만 보이게 합니다.
        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        # 2. 메시지 삭제 작업을 수행합니다. 이 작업은 몇 초가 걸릴 수 있습니다.
        # 명령어 자체 메시지도 삭제되므로 +1 하지 않습니다. defer 응답은 별개입니다.
        deleted = await ctx.channel.purge(limit=amount)

        # 3. 최종 결과를 상황에 맞는 응답 방식으로 보냅니다.
        final_message = f"✅ {len(deleted)}개의 메시지를 성공적으로 삭제했습니다."
        
        if ctx.interaction:
            # defer에 대한 후속 응답으로, 사용자에게만 보이는 메시지를 보냅니다.
            await ctx.interaction.followup.send(embed=self.bot.embeds.success("청소 완료", final_message), ephemeral=True)
        else:
            # 접두사 명령어의 경우, 5초 뒤에 사라지는 메시지를 보냅니다.
            await ctx.send(embed=self.bot.embeds.success("청소 완료", final_message), delete_after=5)


async def setup(bot: commands.Bot):
    """이 Cog를 봇에 추가하기 위해 discord.py가 호출하는 함수입니다."""
    await bot.add_cog(AdminCommands(bot))