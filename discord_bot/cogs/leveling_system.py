import discord
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime, date
import random
# #- 추가된 부분: 이미지 처리 및 다운로드를 위한 라이브러리
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp

from core import check

# 경로 설정
COG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(COG_DIR, '..', 'data')
USER_DATA_FILE = os.path.join(DATA_DIR, 'user_data.json')
# 폰트 파일 경로 설정
BOLD_FONT_PATH = os.path.join(DATA_DIR, 'bold_font.ttf')
REGULAR_FONT_PATH = os.path.join(DATA_DIR, 'regular_font.ttf')


# data 디렉토리가 없으면 생성
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class LevelingSystem(commands.Cog):
    """서버 활동에 따른 레벨 및 경험치 시스템을 관리하는 Cog입니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_data = {}
        self.lock = asyncio.Lock()
        self.bot.loop.create_task(self.load_user_data())
        # #- 추가된 부분: aiohttp 세션을 봇이 관리하도록 추가
        self.session = aiohttp.ClientSession()
        
    def cog_unload(self):
        # #- 추가된 부분: Cog가 언로드될 때 세션을 닫아줌
        self.bot.loop.create_task(self.session.close())

    # --- 데이터 관리 함수 (이전과 동일) ---
    async def load_user_data(self):
        async with self.lock:
            if not os.path.exists(USER_DATA_FILE): self.user_data = {}; return
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f: self.user_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError): self.user_data = {}
    async def save_user_data(self):
        async with self.lock:
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f: json.dump(self.user_data, f, indent=4)
    async def get_user_data(self, user_id: int):
        user_id_str = str(user_id)
        if user_id_str not in self.user_data:
            self.user_data[user_id_str] = {"level": 1, "exp": 0, "last_message_timestamp": 0, "last_checkin_date": "1970-01-01"}
        return self.user_data[user_id_str]
    def get_required_exp(self, level: int):
        return 8 * (level ** 2) + (50 * level) + 100
        
    # --- 핵심 로직 (이전과 동일, grant_exp 수정) ---
    async def grant_exp(self, user: discord.Member, amount: int, channel: discord.TextChannel = None):
        if user.bot: return
        data = await self.get_user_data(user.id)
        data["exp"] += amount
        leveled_up = False
        while data["exp"] >= self.get_required_exp(data["level"]):
            required_exp = self.get_required_exp(data["level"])
            data["exp"] -= required_exp; data["level"] += 1; leveled_up = True
        if leveled_up:
            try:
                target_channel = channel if channel else user
                await target_channel.send(embed=self.bot.embeds.success("레벨 업!", f"축하합니다, {user.mention}님! **레벨 {data['level']}**을 달성하셨습니다! :tada:"))
            except discord.Forbidden: pass
        await self.save_user_data()

    # --- 이벤트 리스너 (이전과 동일) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        user_id = message.author.id; data = await self.get_user_data(user_id)
        current_time = datetime.now().timestamp()
        if current_time - data.get("last_message_timestamp", 0) > 25: # 최소 시간 간격 25초
            data["last_message_timestamp"] = current_time
            exp_to_grant = random.randint(10, 15)  # 10 ~ 15경험치
            await self.grant_exp(message.author, exp_to_grant, channel=message.channel)


    
# --- 레벨 카드 생성 함수 ---
    async def create_rank_card(self, user: discord.Member, level_data: dict, rank: int):
        # 폰트 로드
        try:
            # #- 수정된 부분: 폰트 사이즈 증가
            name_font = ImageFont.truetype(BOLD_FONT_PATH, 120)      
            level_font = ImageFont.truetype(REGULAR_FONT_PATH, 60)    
            exp_font = ImageFont.truetype(BOLD_FONT_PATH, 40)      
        except IOError: 
            name_font = ImageFont.load_default()
            level_font = ImageFont.load_default()
            exp_font = ImageFont.load_default()

        # 사용자 프로필 이미지 다운로드
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        async with self.session.get(str(avatar_url)) as response:
            if response.status == 200:
                avatar_bytes = await response.read()
                avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            else:
                avatar_image = Image.new("RGBA", (200, 200), (255, 255, 255, 0))

        # 카드 세로 길이 증가
        card = Image.new("RGBA", (934, 350), (0, 0, 0, 0))
        
        # 배경 그라데이션
        start_color = (100, 180, 160); end_color = (80, 150, 90)
        for y in range(card.height):
            r = int(start_color[0] + (end_color[0] - start_color[0]) * (y / card.height))
            g = int(start_color[1] + (end_color[1] - start_color[1]) * (y / card.height))
            b = int(start_color[2] + (end_color[2] - start_color[2]) * (y / card.height))
            ImageDraw.Draw(card).line([(0, y), (card.width, y)], fill=(r, g, b))

        # 둥근 모서리 마스크
        mask = Image.new("L", card.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, card.width, card.height), radius=20, fill=255)
        card.putalpha(mask)

        # 프로필 이미지
        avatar_image = avatar_image.resize((210, 210))
        avatar_mask = Image.new("L", avatar_image.size, 0)
        ImageDraw.Draw(avatar_mask).ellipse((0, 0) + avatar_image.size, fill=255)
        card.paste(avatar_image, (36, 60), avatar_mask)

        # 텍스트 그리기
        draw = ImageDraw.Draw(card)
        #-- 수정된 부분: 모든 텍스트에 검은색 테두리(stroke) 추가
        draw.text((290, 0), user.display_name, font=name_font, fill=(255, 255, 255), stroke_width=0, stroke_fill=(0,0,0))
        draw.text((297, 155), f"Level {level_data['level']}", font=level_font, fill=(255, 255, 255), stroke_fill=(0,0,0))
        draw.text((600, 155), f"Rank #{rank}", font=level_font, fill=(255, 255, 255), stroke_fill=(0,0,0))
        draw.text((295, 230), f"{level_data['exp']} / {self.get_required_exp(level_data['level'])} EXP", font=exp_font, fill=(255, 255, 255))

        # 둥근 모서리를 가진 그라데이션 프로그레스 바
        bar_x, bar_y = 290, 280
        bar_width, bar_height = 600, 30
        bar_radius = 15
        
        # 프로그레스 바 배경 그리기
        #-- 수정된 부분: 프로그레스 바 배경에 흰색 테두리 추가
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), 
            radius=bar_radius, 
            fill=(50, 80, 55),
            outline=(75, 99, 62), # 테두리 색상 (연한 흰색)
            width=3 # 테두리 두께
        )

        current_exp = level_data['exp']
        required_exp = self.get_required_exp(level_data['level'])
        progress_ratio = current_exp / required_exp
        
        fill_width = int(bar_width * progress_ratio)
        if fill_width > 1: # 너비가 1보다 클 때만 그리기
            # 그라데이션 채우기 이미지 생성
            fill_image = Image.new("RGBA", (fill_width, bar_height), (0, 0, 0, 0))
            fill_draw = ImageDraw.Draw(fill_image)
            
            grad_start = (105, 190, 115); grad_end = (180, 220, 130)
            for x in range(fill_width):
                r = int(grad_start[0] + (grad_end[0] - grad_start[0]) * (x / fill_width))
                g = int(grad_start[1] + (grad_end[1] - grad_start[1]) * (x / fill_width))
                b = int(grad_start[2] + (grad_end[2] - grad_start[2]) * (x / fill_width))
                fill_draw.line([(x, 0), (x, bar_height)], fill=(r, g, b))

            fill_mask = Image.new("L", fill_image.size, 0)
            draw_fill_mask = ImageDraw.Draw(fill_mask)
            draw_fill_mask.rounded_rectangle((0, 0, fill_width, bar_height), radius=bar_radius, fill=255)
            fill_image.putalpha(fill_mask)

            card.paste(fill_image, (bar_x, bar_y), fill_image)
            
            #-- 수정된 부분: 채워진 부분 위에도 테두리를 한 번 더 그려줌
            draw.rounded_rectangle(
                (bar_x, bar_y, bar_x + fill_width, bar_y + bar_height),
                radius=bar_radius,
                outline=(50, 80, 55), # 채워진 부분의 테두리
                width=2
            )

        # 결과 이미지를 바이트로 변환
        buffer = io.BytesIO()
        card.save(buffer, "PNG")
        buffer.seek(0)
        return discord.File(buffer, "rank_card.png")

    # --- 사용자 명령어 ---
    @commands.hybrid_command(name="레벨", description="자신의 레벨과 경험치를 그래픽 카드로 확인합니다.")
    async def level(self, ctx: commands.Context):
        """자신의 레벨과 경험치를 세련된 그래픽 카드로 보여줍니다."""
        await ctx.defer() # 이미지 생성에 시간이 걸릴 수 있으므로 응답 대기
        
        user = ctx.author
        data = await self.get_user_data(user.id)

        # 랭킹 계산
        sorted_users = sorted(self.user_data.items(), key=lambda item: (item[1]['level'], item[1]['exp']), reverse=True)
        rank = -1
        for i, (user_id, _) in enumerate(sorted_users):
            if int(user_id) == user.id:
                rank = i + 1
                break

        # 레벨 카드 생성
        try:
            rank_card_file = await self.create_rank_card(user, data, rank)
            await ctx.send(file=rank_card_file)
        except Exception as e:
            await ctx.send(embed=self.bot.embeds.error("이미지 생성 실패", f"레벨 카드를 만드는 중 오류가 발생했습니다: {e}"))
            
    # --- 출석 및 관리자 명령어 (이전과 동일) ---
    @commands.hybrid_command(name="출석", description="매일 한 번 출석하여 경험치를 얻습니다.")
    async def checkin(self, ctx: commands.Context):
        user = ctx.author; data = await self.get_user_data(user.id); today_str = str(date.today())
        if data["last_checkin_date"] == today_str:
            await ctx.send(embed=self.bot.embeds.error("출석 실패", "오늘은 이미 출석체크를 완료했습니다."), ephemeral=True)
        else:
            data["last_checkin_date"] = today_str; exp_to_grant = 100
            await self.grant_exp(user, exp_to_grant, channel=ctx.channel)
            await ctx.send(embed=self.bot.embeds.success("출석 완료!", f"{exp_to_grant} 경험치를 획득했습니다!"), ephemeral=True)

    @commands.hybrid_group(name="조정", description="사용자의 레벨/경험치를 조정합니다. (관리자 전용)")
    @check.is_admin()
    async def adjust(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=self.bot.embeds.error("명령어 오류", "사용할 하위 명령어를 입력해주세요. (예: `!조정 레벨설정`)"), ephemeral=True)

    @adjust.command(name="레벨설정", description="특정 사용자의 레벨을 설정합니다.")
    @check.is_admin()
    async def set_level(self, ctx: commands.Context, member: discord.Member, level: int):
        if level <= 0: await ctx.send(embed=self.bot.embeds.error("입력 오류", "레벨은 1 이상이어야 합니다."), ephemeral=True); return
        data = await self.get_user_data(member.id); data['level'] = level; data['exp'] = 0; await self.save_user_data()
        await ctx.send(embed=self.bot.embeds.success("작업 완료", f"{member.mention}님의 레벨을 **{level}** (으)로 설정했습니다."), ephemeral=True)

    @adjust.command(name="경험치설정", description="특정 사용자의 경험치를 설정합니다.")
    @check.is_admin()
    async def set_exp(self, ctx: commands.Context, member: discord.Member, exp: int):
        if exp < 0: await ctx.send(embed=self.bot.embeds.error("입력 오류", "경험치는 0 이상이어야 합니다."), ephemeral=True); return
        data = await self.get_user_data(member.id); data['exp'] = exp; await self.save_user_data()
        await self.grant_exp(member, 0, channel=ctx.channel)
        await ctx.send(embed=self.bot.embeds.success("작업 완료", f"{member.mention}님의 경험치를 **{exp}** (으)로 설정했습니다."), ephemeral=True)

    @adjust.command(name="경험치추가", description="특정 사용자에게 경험치를 추가하거나 빼줍니다.")
    @check.is_admin()
    async def add_exp(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount > 0: await self.grant_exp(member, amount, channel=ctx.channel)
        else:
            data = await self.get_user_data(member.id); data['exp'] += amount
            if data['exp'] < 0: data['exp'] = 0
            await self.save_user_data()
        await ctx.send(embed=self.bot.embeds.success("작업 완료", f"{member.mention}님에게 경험치 **{amount}**을(를) 적용했습니다."), ephemeral=True)


async def setup(bot: commands.Bot):
    """봇에 Cog를 추가합니다."""
    await bot.add_cog(LevelingSystem(bot))