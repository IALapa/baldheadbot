import discord
from discord.ext import commands
import os
import json
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
# .env 파일 로드 (프로젝트 루트 디렉토리에 위치)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv()

# 설정 파일 로드 함수
def get_prefix(client, message):
    """설정 파일에서 접두사를 가져오거나 기본값을 반환합니다."""
    try:
        with open("data/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("prefix", "!")  # 기본 접두사는 "!"
    except (FileNotFoundError, json.JSONDecodeError):
        print("Warning: data/config.json 파일을 찾을 수 없거나 형식이 잘못되었습니다. 기본 접두사 '!'를 사용합니다.")
        return "!"

# 봇에 필요한 Intents 설정
# 서버 멤버 목록, 메시지 내용 등 특정 이벤트 수신을 위해 필요합니다.
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용을 읽기 위한 Intent
intents.members = True          # 서버 멤버 관련 이벤트를 위한 Intent (필요시 활성화)

# commands.Bot 인스턴스 생성
bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None) # 기본 help 명령어 비활성화

@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행되는 이벤트입니다."""
    print(f'봇 이름: {bot.user.name}')
    print(f'봇 ID: {bot.user.id}')
    print(f'연결된 서버 수: {len(bot.guilds)}')
    print('봇이 성공적으로 시작되었습니다!')
    
    # Cogs 로드
    await load_all_cogs()

    # 상태 메시지 설정 (예: "!help를 입력하세요")
    # command_prefix가 함수일 경우, 첫 번째 서버의 접두사를 사용하거나 고정된 값을 사용
    # 여기서는 간단하게 고정된 메시지를 사용합니다.
    current_prefix = "!" # 실제 사용될 접_prefix를 동적으로 가져오는 로직이 필요할 수 있음
    if isinstance(bot.command_prefix, str):
        current_prefix = bot.command_prefix
    elif callable(bot.command_prefix):
        # 첫번째 서버의 접두사를 가져오거나, 기본 접두사를 사용
        # 이 예제에서는 간단히 '!'를 사용합니다. 실제 구현 시에는 더 정교한 방법이 필요할 수 있습니다.
        # 예를 들어, 봇이 처음 연결된 서버의 접두사를 사용하거나, config에서 기본값을 가져올 수 있습니다.
        try:
            with open("data/config.json", "r", encoding="utf-8") as f:
                config_data = json.load(f)
            current_prefix = config_data.get("prefix", "!")
        except:
            current_prefix = "!" # Fallback

    activity = discord.Game(name=f"{current_prefix}help | 열심히 일하는 중")
    await bot.change_presence(status=discord.Status.online, activity=activity)

async def load_all_cogs():
    """cogs 폴더에 있는 모든 Cog를 로드합니다."""
    cogs_dir = "cogs"
    if not os.path.exists(cogs_dir):
        print(f"'{cogs_dir}' 디렉토리가 존재하지 않습니다. Cog를 로드할 수 없습니다.")
        return

    for filename in os.listdir(f'./{cogs_dir}'):
        if filename.endswith('.py') and filename != '__init__.py':
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'{cogs_dir}.{cog_name}')
                print(f"성공적으로 Cog 로드: {cog_name}")
            except commands.ExtensionAlreadyLoaded:
                print(f"이미 로드된 Cog입니다: {cog_name}")
            except Exception as e:
                print(f"Cog 로드 실패: {cog_name} - {type(e).__name__}: {e}")

@bot.command(name="reload_cogs", help="모든 Cog를 다시 로드합니다. (봇 소유자만 가능)")
@commands.is_owner() # 봇 소유자만 이 명령어를 사용할 수 있도록 제한
async def reload_cogs_command(ctx):
    """모든 Cog를 다시 로드하는 명령어입니다."""
    print("모든 Cog를 다시 로드합니다...")
    # 기존 Cog 언로드
    loaded_extensions = list(bot.extensions.keys()) # 현재 로드된 Cog 목록 복사
    for extension_name in loaded_extensions:
        try:
            await bot.unload_extension(extension_name)
            print(f"Cog 언로드: {extension_name}")
        except Exception as e:
            print(f"Cog 언로드 실패: {extension_name} - {e}")
    
    await load_all_cogs() # Cog 다시 로드
    await ctx.send("모든 Cog를 성공적으로 다시 로드했습니다!")

if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("오류: .env 파일에서 DISCORD_BOT_TOKEN을 찾을 수 없습니다.")

