# baldheadbot/core/exceptions.py

from discord.ext import commands

# 모든 커스텀 체크 실패 에러의 기본 클래스
class CustomCheckFailure(commands.CheckFailure):
    pass

# checks.py 에서 사용할 구체적인 에러들
class BotNotConnected(CustomCheckFailure):
    """봇이 음성 채널에 연결되어 있지 않을 때 발생하는 에러입니다."""
    pass

class NotPlayingMusic(CustomCheckFailure):
    """봇이 노래를 재생하고 있지 않을 때 발생하는 에러입니다."""
    pass

class UserNotVip(CustomCheckFailure):
    """사용자가 VIP가 아닐 때 발생하는 에러입니다."""
    pass