# baldhead/core/embed.py

import discord
import datetime
from discord.ext import commands # bot 객체의 타입을 명시하기 위해 import

class EmbedGenerator:
    """
    봇의 정보를 사용하여 표준화된 임베드를 생성하는 클래스입니다.
    봇의 이름과 프로필 사진을 모든 임베드의 푸터에 자동으로 추가합니다.
    """
    def __init__(self, bot: commands.Bot):
        # 클래스가 생성될 때 bot 객체를 받아 내부에 저장
        self.bot = bot

    def success(self, title: str, description: str = "") -> discord.Embed:
        """성공 상황에 사용할 표준 초록색 임베드를 생성합니다."""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # 봇의 이름과 프로필 사진을 푸터에 설정
        if self.bot.user and self.bot.user.avatar:
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar.url)
        return embed

    def error(self, title: str, description: str = "") -> discord.Embed:
        """오류 상황에 사용할 표준 빨간색 임베드를 생성합니다."""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # 봇의 이름과 프로필 사진을 푸터에 설정
        if self.bot.user and self.bot.user.avatar:
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar.url)
        return embed

    def info(self, title: str, description: str = "") -> discord.Embed:
        """정보 전달에 사용할 표준 파란색 임베드를 생성합니다."""
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # 봇의 이름과 프로필 사진을 푸터에 설정
        if self.bot.user and self.bot.user.avatar:
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar.url)
        return embed