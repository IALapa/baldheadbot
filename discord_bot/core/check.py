# baldheadbot/core/checks.py

from discord.ext import commands
from . import exceptions

def is_admin():
    """관리자 역할을 가진 사용자만 사용할 수 있는지 확인하는 체크 함수"""
    async def predicate(ctx):
        # 'Admin' 또는 '관리자' 역할을 가지고 있는지 확인
        admin_roles = ['Admin', '관리자']
        return any(role.name in admin_roles for role in ctx.author.roles)
    return commands.check(predicate)

def is_in_specific_channel(channel_id):
    """특정 채널에서만 사용할 수 있는지 확인하는 체크 함수"""
    async def predicate(ctx):
        return ctx.channel.id == channel_id
    return commands.check(predicate)

def is_owner():
    """봇 소유자만 사용할 수 있는지 확인하는 체크 함수 (discord.py에 이미 내장되어 있음)"""
    return commands.is_owner()

def is_vip_user():
    """설정 파일에 지정된 VIP 역할을 가진 사용자인지 확인하는 체크"""
    async def predicate(ctx: commands.Context) -> bool:
        # 실제로는 config.json 파일에서 VIP 역할 ID를 불러오는 로직이 필요합니다.
        # 이 예시에서는 임의의 ID를 사용합니다.
        try:
            # 여기서는 간단하게 12345 라는 임시 ID를 사용합니다.
            # 실제 구현 시에는 config 파일에서 ID를 읽어오세요.
            vip_role_id = 12345 # config.get('vip_role_id')
            vip_role = ctx.guild.get_role(vip_role_id)

            if vip_role and vip_role in ctx.author.roles:
                return True
            else:
                # VIP 역할이 없으면 UserNotVip 예외 발생
                raise exceptions.UserNotVip()
        except Exception:
            # 설정 파일 오류 등 다른 문제가 있을 경우에도 예외 발생
            raise exceptions.UserNotVip()
            
    return commands.check(predicate)

def is_bot_playing():
    """봇이 음성 채널에 있고, 무언가를 재생 중인지 확인하는 체크 함수"""
    async def predicate(ctx: commands.Context) -> bool:
        # 봇의 음성 클라이언트(vc)가 없거나, 연결되어 있지 않으면 에러 발생
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            raise exceptions.BotNotConnected()

        # 봇이 무언가를 재생하고 있지 않으면 에러 발생
        if not ctx.voice_client.is_playing():
            raise exceptions.NotPlayingMusic()
            
        return True
    return commands.check(predicate)

def is_bot_connected():
    """봇이 음성 채널에 연결되어 있는지 확인하는 체크 함수"""
    async def predicate(ctx: commands.Context) -> bool:
        # 봇의 음성 클라이언트(vc)가 없거나, 연결되어 있지 않으면 에러 발생
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            raise exceptions.BotNotConnected()
        return True
    return commands.check(predicate)

# 다른 유용한 체크 함수들을 추가할 수 있습니다.

'''

**코드 설명:**

*   **`is_admin()`**:  사용자가 'Admin' 또는 '관리자' 역할을 가지고 있는지 확인하는 체크 함수입니다. `any()` 함수와 역할 이름을 비교하여 하나라도 일치하는 역할이 있으면 `True`를 반환합니다.
*   **`is_in_specific_channel(channel_id)`**: 명령어가 특정 `channel_id`를 가진 채널에서 실행되었는지 확인하는 체크 함수입니다. 함수 인자로 채널 ID를 받아, 해당 ID와 현재 메시지가 보내진 채널의 ID를 비교합니다.
*   **`is_owner()`**: 봇 소유자만 사용할 수 있는지 확인하는 체크 함수입니다. `discord.py`에 이미 내장된 `commands.is_owner()`를 그대로 사용합니다.

'''
