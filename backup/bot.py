import discord
from discord.ext import commands
import os
import json
import sys
from dotenv import load_dotenv



# 현재 작업 디렉토리를 기준으로 .env 파일 경로 설정
current_dir = os.getcwd()
dotenv_path = os.path.join(current_dir, '.env')

# .env 파일 로드 및 BOT_TOKEN 설정
load_dotenv(dotenv_path=dotenv_path)
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


def find_config_file(start_path):
    """주어진 경로에서 'config.json' 파일을 찾습니다."""
    for root, _, files in os.walk(start_path):
        for filename in files:
            if filename.lower() == "config.json":
                return os.path.join(root, filename)
    return None

# 설정 파일 로드 함수
def get_prefix(client, message):
    """설정 파일에서 접두사를 가져오거나 기본값을 반환합니다."""
    current_dir = os.getcwd()
    config_path = find_config_file(current_dir)

    if not config_path:
        print("Warning: config.json 파일을 찾을 수 없습니다. 기본 접두사 '!'를 사용합니다.")
        return "!"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            prefix = config.get("prefix")
            if prefix:
                return prefix
            else:
                print("Warning: config.json 파일에 'prefix' 설정이 없습니다. 기본 접두사 '!'를 사용합니다.")
                return "!"
    except json.JSONDecodeError:
        print("Warning: config.json 파일 형식이 잘못되었습니다. 기본 접두사 '!'를 사용합니다.")
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
    
    # 슬래시 명령어 등록
    await bot.tree.sync()

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
    current_dir = os.getcwd()
    cogs_path = find_cogs_folder(current_dir)

    if not cogs_path:
        print("'cogs' 디렉토리를 찾을 수 없습니다. Cog를 로드할 수 없습니다.")
        return

    # 봇 파일 기준으로 cogs 폴더 경로 설정 (상대 경로)
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    relative_cogs_path = os.path.relpath(cogs_path, bot_dir).replace(os.sep, ".")
    for filename in os.listdir(cogs_path):
        if filename.endswith('.py') and filename != '__init__.py':
            extension_name = filename[:-3]  # 확장자 제거
            extension_path = relative_cogs_path + "." + extension_name  # Cog 모듈 경로
            if extension_path not in bot.extensions:  # 이미 로드되지 않았다면
                try:
                    await bot.load_extension(extension_path)
                    print(f"Cog '{extension_name}' 로드 성공 from {cogs_path}")
                except Exception as e:
                    print(f"Cog 로드 실패: {type(e).__name__}: {e}")

def find_cogs_folder(start_path):
    """주어진 경로에서 'cogs' 폴더를 재귀적으로 찾습니다."""
    for root, dirs, _ in os.walk(start_path, followlinks=True):  # followlinks 추가
        for dir_name in dirs:
            if dir_name.lower() == "cogs":  # 대소문자 구분 없이 비교
                cogs_path = os.path.join(root, dir_name)
                print(f"'cogs' 폴더를 찾았습니다: {cogs_path}")  # 찾은 경로 로깅
                return cogs_path
    return None



@bot.command(name="sync", help="슬래시 명령어를 강제로 동기화합니다. (봇 소유자만 가능)")
@commands.is_owner()
async def sync_command(ctx):
    """모든 슬래시 명령어를 디스코드 서버와 강제로 동기화합니다."""
    await ctx.send("🔄 슬래시 명령어 동기화를 시작합니다...")
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ {len(synced)}개의 슬래시 명령어가 성공적으로 동기화되었습니다.")
    except Exception as e:
        await ctx.send(f"❌ 동기화 중 오류가 발생했습니다: {e}")



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
    
    await load_all_cogs()  # Cog 다시 로드
    await bot.tree.sync()  # 슬래시 명령어 다시 등록
    await ctx.send("모든 Cog를 성공적으로 다시 로드했습니다!")

if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("오류: .env 파일에서 DISCORD_BOT_TOKEN을 찾을 수 없습니다.")
