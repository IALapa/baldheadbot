import discord
from discord.ext import commands
import os
import json
import sys
from dotenv import load_dotenv

# --- 시스템 경로 설정 ---

# 프로젝트의 최상위 디렉토리를 Python 경로에 추가하여,
# 어떤 위치에서 파일을 실행하더라도 core, cogs 등의 모듈을 안정적으로 불러올 수 있게 합니다.

# 이 코드 파일(bot.py)의 상위 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from core.embed import EmbedGenerator


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
    except (json.JSONDecodeError, FileNotFoundError):
        print("Warning: config.json 파일을 읽는 중 오류가 발생했습니다. 기본 접두사 '!'를 사용합니다.")
        return "!"
    

# 봇에 필요한 Intents 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- bot 객체 생성 및 설정 (오류 수정) ---
# bot 객체를 한 번만 생성하고, 필요한 모든 설정을 여기에 포함합니다.
bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)
# core.embed 모듈의 EmbedGenerator 클래스를 사용하여 인스턴스 생성
bot.embeds = EmbedGenerator(bot)


@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행되는 이벤트입니다."""
    print(f'봇 이름: {bot.user.name}')
    print(f'봇 ID: {bot.user.id}')
    print(f'연결된 서버 수: {len(bot.guilds)}')
    print('봇이 성공적으로 시작되었습니다!')
    
    # Cogs 로드
    await load_all_cogs()

    # 슬래시 명령어는 모든 Cog가 로드된 후에 동기화하는 것이 더 안정적일 수 있습니다.
    # 필요시 `!sync` 명령어로 수동 동기화하는 것을 권장합니다.
    # await bot.tree.sync() 

    # --- 상태 메시지 설정 로직 개선 ---
    # get_prefix 함수와 동일한 방식으로 config 파일을 찾아 일관성을 유지합니다.
    config_path = find_config_file(os.getcwd())
    current_prefix = "!" # 기본값
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            current_prefix = config_data.get("prefix", "!")
        except (FileNotFoundError, json.JSONDecodeError):
            pass # 오류 발생 시 기본값 사용

    activity = discord.Game(name=f"{current_prefix}help | 열심히 일하는 중")
    await bot.change_presence(status=discord.Status.online, activity=activity)

async def load_all_cogs():
    """cogs 폴더에 있는 모든 Cog를 로드합니다."""
    # cogs 폴더는 bot.py와 같은 디렉토리 레벨에 있는 my_discord_bot/cogs 에 위치
    cogs_path = "cogs" # import 경로를 직접 지정하는 것이 더 안정적입니다.
    
    # os.path.join을 사용하여 cogs 폴더의 실제 파일 시스템 경로를 얻습니다.
    # 이 경로는 파일 목록을 읽는 데 사용됩니다.
    try:
        # sys.path[0]는 스크립트가 실행되는 디렉토리를 가리킵니다.
        # 이 경로를 기준으로 cogs 폴더의 실제 위치를 찾습니다.
        cogs_dir_path = os.path.join(sys.path[0], "cogs")
        for filename in os.listdir(cogs_dir_path):
            if filename.endswith('.py') and not filename.startswith('__'):
                extension_name = filename[:-3]
                extension_path = f"{cogs_path}.{extension_name}"
                if extension_path not in bot.extensions:
                    try:
                        await bot.load_extension(extension_path)
                        print(f"Cog '{extension_name}' 로드 성공")
                    except Exception as e:
                        print(f"Cog '{extension_name}' 로드 실패: {type(e).__name__} - {e}")
    except FileNotFoundError:
        print(f"'{cogs_dir_path}' 디렉토리를 찾을 수 없습니다. Cog를 로드할 수 없습니다.")


# --- `sync` 명령어 강화: 특정 서버에 즉시 동기화 기능 추가 ---
@bot.hybrid_command(name="sync", help="슬래시 명령어를 동기화합니다. (봇 소유자만 가능)")
@commands.is_owner()
async def sync_command(ctx, guild_id: str = None):
    """
    특정 서버 또는 모든 서버에 슬래시 명령어를 동기화합니다.
    사용법: !sync [서버_ID] (서버 ID 없으면 전역 동기화)
    """
    if guild_id:
        try:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            await ctx.send(embed=bot.embeds.success("서버 동기화 성공", f"서버 ID `{guild_id}`에 {len(synced)}개의 명령어를 동기화했습니다. (즉시 반영)"))
        except ValueError:
            await ctx.send(embed=bot.embeds.error("오류", "잘못된 서버 ID입니다. 숫자만 입력해주세요."))
        except Exception as e:
            await ctx.send(embed=bot.embeds.error("서버 동기화 실패", f"해당 서버에 동기화 중 오류 발생: {e}"))
    else:
        await ctx.send(embed=bot.embeds.info("전역 동기화", "모든 서버에 전역으로 동기화를 시작합니다..."))
        try:
            synced = await bot.tree.sync()
            await ctx.send(embed=bot.embeds.success("전역 동기화 성공", f"{len(synced)}개의 명령어가 전역으로 동기화되었습니다. (최대 1시간 소요)"))
        except Exception as e:
            await ctx.send(embed=bot.embeds.error("전역 동기화 실패", f"동기화 중 오류 발생: {e}"))


@bot.hybrid_command(name="reload_cogs", help="모든 Cog를 다시 로드합니다. (봇 소유자만 가능)")
@commands.is_owner()
async def reload_cogs_command(ctx):
    """모든 Cog를 다시 로드하는 명령어입니다."""
    print("모든 Cog를 다시 로드합니다...")
    loaded_extensions = list(bot.extensions.keys())
    for extension_name in loaded_extensions:
        try:
            await bot.unload_extension(extension_name)
            print(f"Cog 언로드: {extension_name}")
        except Exception as e:
            print(f"Cog 언로드 실패: {extension_name} - {e}")
    
    await load_all_cogs()
    await ctx.send(embed=bot.embeds.success("Cog 리로드", "모든 Cog를 성공적으로 다시 로드했습니다!\n변경된 슬래시 명령어는 `!sync`로 별도 동기화해주세요."))

if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("오류: .env 파일에서 DISCORD_BOT_TOKEN을 찾을 수 없습니다.")