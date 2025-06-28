import discord
from discord.ext import commands
import re
from core.embed import EmbedGenerator

class EmojiCommands(commands.Cog):
    """이모지 확대 및 검색과 관련된 명령어들을 포함하는 Cog입니다."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.embed_generator = EmbedGenerator(bot) # EmbedGenerator 인스턴스 초기화

    # --- 자동 이모지 확대 기능 (명령어 없음) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 봇 자신의 메시지이거나, 서버가 아닌 DM 등에서는 무시
        if message.author.bot or not message.guild:
            return

        # 메시지에서 커스텀 이모지 정보들을 추출 (예: <a:name:id> 또는 <:name:id>)
        # group 1: 'a' (animated) or empty, group 2: name, group 3: id
        custom_emojis_info = re.findall(r'<(a?):(\w+):(\d+)>', message.content)

        # 메시지에 커스텀 이모지가 하나라도 포함되어 있다면 실행
        if custom_emojis_info:
            # 원본 메시지를 삭제하기 위해 봇에게 '메시지 관리' 권한이 필요합니다.
            try:
                await message.delete()
            except discord.Forbidden:
                pass # 권한이 없을 경우, 그냥 원본 메시지를 놔둡니다.
            except discord.NotFound:
                pass # 메시지가 이미 삭제된 경우 등
            except Exception:
                pass # 기타 삭제 오류

            # 각 이모지를 확대해서 전송
            for animated, name, emoji_id in custom_emojis_info:
                # 이모지 URL 직접 구성
                extension = "gif" if animated else "png"
                emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"
                
                # EmbedGenerator의 info 메소드를 사용하여 임베드 생성
                embed = self.embed_generator.info(title=f"'{name}' 이모지")
                embed.set_author(name=f"{message.author.display_name} 님의 이모지", icon_url=message.author.avatar.url if message.author.avatar else discord.Embed.Empty)
                # embed.set_image(url=emoji_url)
                
                try:
                    await message.channel.send(embed=embed)
                except Exception:
                    pass # 임베드 전송 중 오류 발생 시 무시 (예: 권한 없음)
            return

    # --- 외부 서버 이모지 불러오기 기능 (명령어) ---
    @commands.hybrid_command(name="이모지", description="다른 서버의 커스텀 이모지를 이름으로 찾아 보여줍니다.")
    async def get_emoji(self, ctx: commands.Context, 이름: str):
        """봇이 접속한 모든 서버에서 이름이 일치하는 커스텀 이모지를 찾아 보여줍니다."""
        found_emoji = None
        # 봇이 속한 모든 서버를 순회하며 이모지 검색
        for guild in self.bot.guilds:
            for emoji in guild.emojis:
                if emoji.name.lower() == 이름.lower():
                    found_emoji = emoji
                    break
            if found_emoji:
                break
        
        if found_emoji:
            # EmbedGenerator의 success 메소드를 사용하여 임베드 생성
            embed = self.embed_generator.success(
                title=f"'{found_emoji.name}' 이모지 발견!",
                description=f"**서버:** {found_emoji.guild.name}"
            )
            embed.set_image(url=found_emoji.url)
            await ctx.send(embed=embed)
        else:
            # EmbedGenerator의 error 메소드를 사용하여 임베드 생성
            embed = self.embed_generator.error(
                title="이모지를 찾을 수 없어요",
                description=f"❌ '{이름}' 이라는 이름의 이모지를 제가 속한 서버들에서 찾을 수 없어요."
            )
            await ctx.send(embed=embed, ephemeral=True) # ephemeral=True는 명령어를 사용한 사용자에게만 메시지를 보냅니다.


async def setup(bot: commands.Bot):
    """이 Cog를 봇에 추가하기 위해 discord.py가 호출하는 함수입니다."""
    await bot.add_cog(EmojiCommands(bot))
    print("EmojiCommands Cog가 로드되었습니다.")