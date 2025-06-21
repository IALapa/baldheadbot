import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import time
import asyncio

from core import check

# 경로 설정
COG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(COG_DIR, '..', 'data')
SENTENCES_FILE = os.path.join(DATA_DIR, 'taja_sentences.json')

class TajaGame(commands.Cog):
    """자동 분류와 차등 시간 제한을 지원하는 타자 연습 게임 Cog입니다."""
    
    SHORT_SENTENCE_BYTE_LIMIT = 70

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games = {}
        self.sentences = {"short": [], "long": [], "next_id": 1}
        self.lock = asyncio.Lock()
        self.bot.loop.create_task(self.load_sentences())

    async def load_sentences(self):
        async with self.lock:
            if not os.path.exists(SENTENCES_FILE):
                self.sentences = {"short": [], "long": [], "next_id": 1}
                return
            try:
                with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
                    self.sentences = json.load(f)
                    if 'next_id' not in self.sentences:
                        all_ids = [s['id'] for s in self.sentences.get('short', [])] + [s['id'] for s in self.sentences.get('long', [])]
                        self.sentences['next_id'] = max(all_ids) + 1 if all_ids else 1
            except (json.JSONDecodeError, FileNotFoundError):
                self.sentences = {"short": [], "long": [], "next_id": 1}

    async def save_sentences(self):
        async with self.lock:
            with open(SENTENCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentences, f, indent=4, ensure_ascii=False)

    #-- 공통으로 사용할 선택지 목록
    sentence_type_choices = [
        app_commands.Choice(name='단문', value='short'),
        app_commands.Choice(name='장문', value='long')
    ]
    
    @commands.hybrid_group(name="문장관리", description="타자 연습 문장을 관리합니다. (관리자 전용)")
    @check.is_admin()
    async def manage_sentences(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=self.bot.embeds.error("명령어 오류", "사용할 하위 명령어를 입력해주세요."), ephemeral=True)

    @manage_sentences.command(name="추가", description="새로운 타자 연습 문장을 추가합니다. 길이에 따라 자동 분류됩니다.")
    @app_commands.describe(내용="추가할 문장의 내용 (최대 550자)")
    async def add_sentence(self, ctx: commands.Context, 내용: str):
        if len(내용) > 550:
            await ctx.send(embed=self.bot.embeds.error("글자 수 초과", "문장의 길이는 550자를 초과할 수 없습니다."), ephemeral=True)
            return
        byte_length = len(내용.encode('utf-8'))
        sentence_type = "short" if byte_length <= self.SHORT_SENTENCE_BYTE_LIMIT else "long"
        new_id = self.sentences['next_id']
        new_sentence = {"id": new_id, "text": 내용}
        self.sentences[sentence_type].append(new_sentence)
        self.sentences['next_id'] += 1
        await self.save_sentences()
        type_korean = "단문" if sentence_type == "short" else "장문"
        await ctx.send(embed=self.bot.embeds.success("자동 분류 및 추가 완료", f"해당 문장은 **'{type_korean}'**(으)로 자동 분류되었습니다.\n**ID:{new_id}**로 추가 완료!\n> {내용}"), ephemeral=True)

    @manage_sentences.command(name="목록", description="저장된 타자 연습 문장 목록을 확인합니다.")
    @app_commands.describe(유형="확인할 문장의 유형 (단문/장문)")
    @app_commands.choices(유형=sentence_type_choices) #- 수정된 부분: 데코레이터로 선택지 직접 설정
    async def list_sentences(self, ctx: commands.Context, 유형: str): #- 수정된 부분: 타입 힌트 str로 변경
        sentence_list = self.sentences.get(유형, [])
        if not sentence_list:
            await ctx.send(embed=self.bot.embeds.info(f"'{유형}' 문장 목록", "저장된 문장이 없습니다."), ephemeral=True)
            return
        description = "".join([f"**ID:{s['id']}** - {s['text']}\n" for s in sentence_list])
        if len(description) > 4000: description = description[:4000] + "\n... (내용이 너무 많아 일부만 표시)"
        embed = self.bot.embeds.info(f"'{유형.capitalize()}' 문장 목록", description)
        await ctx.send(embed=embed, ephemeral=True)

    @manage_sentences.command(name="삭제", description="ID로 특정 타자 연습 문장을 삭제합니다.")
    @app_commands.describe(유형="삭제할 문장이 속한 유형", 문장id="삭제할 문장의 ID 번호")
    @app_commands.choices(유형=sentence_type_choices) #- 수정된 부분: 데코레이터로 선택지 직접 설정
    async def delete_sentence(self, ctx: commands.Context, 유형: str, 문장id: int): #- 수정된 부분: 타입 힌트 str로 변경
        sentence_list = self.sentences.get(유형, [])
        target_sentence = next((s for s in sentence_list if s['id'] == 문장id), None)
        if target_sentence:
            self.sentences[유형].remove(target_sentence)
            await self.save_sentences()
            await ctx.send(embed=self.bot.embeds.success("삭제 완료", f"**ID:{문장id}** 문장을 삭제했습니다."), ephemeral=True)
        else:
            await ctx.send(embed=self.bot.embeds.error("삭제 실패", f"**ID:{문장id}**에 해당하는 문장을 찾을 수 없습니다."), ephemeral=True)

    @commands.hybrid_command(name="타자연습", description="단문(15초)/장문(3분) 타자 연습 미니게임을 시작합니다.")
    @app_commands.describe(유형="플레이할 게임의 유형을 선택하세요.")
    @app_commands.choices(유형=sentence_type_choices) #- 수정된 부분: 데코레이터로 선택지 직접 설정
    async def start_taja_game(self, ctx: commands.Context, 유형: str): #- 수정된 부분: 타입 힌트 str로 변경
        channel_id = ctx.channel.id
        if channel_id in self.games:
            await ctx.send(embed=self.bot.embeds.error("게임 진행 중", "이 채널에서는 이미 타자 연습 게임이 진행 중입니다."), ephemeral=True)
            return
        
        sentence_list = self.sentences.get(유형, [])
        if not sentence_list:
            await ctx.send(embed=self.bot.embeds.error("게임 시작 불가", f"'{유형.capitalize()}' 유형에 등록된 문장이 없습니다."), ephemeral=True)
            return

        time_limit = 15 if 유형 == "short" else 180
        sentence_data = random.choice(sentence_list)
        sentence = sentence_data['text']
        self.games[channel_id] = {"sentence": sentence, "start_time": time.time()}
        embed = self.bot.embeds.info(f"{유형.capitalize()} 타자 연습 시작!", f"아래 문장을 그대로 입력해주세요! (**{time_limit}초 제한**)")
        embed.add_field(name="제시어", value=f"**{sentence}**", inline=False)
        await ctx.send(embed=embed)
        self.bot.loop.create_task(self.timeout_game(channel_id, time_limit))

    async def timeout_game(self, channel_id: int, delay: int):
        await asyncio.sleep(delay)
        if channel_id in self.games:
            del self.games[channel_id]
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=self.bot.embeds.error("시간 초과", "아쉽지만 시간이 초과되었습니다. 게임을 종료합니다."))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id not in self.games:
            return
        game = self.games[message.channel.id]
        if message.content == game["sentence"]:
            end_time = time.time()
            elapsed_time = end_time - game["start_time"]
            cpm = (len(game["sentence"].encode('utf-8')) / elapsed_time) * 60
            embed = self.bot.embeds.success("정답입니다!", f"{message.author.mention}님이 성공적으로 입력했습니다! :trophy:")
            embed.add_field(name="소요 시간", value=f"{elapsed_time:.2f}초", inline=True)
            embed.add_field(name="타수", value=f"약 {cpm:.0f}타/분", inline=True)
            await message.channel.send(embed=embed)
            leveling_cog = self.bot.get_cog("LevelingSystem")
            if leveling_cog:
                exp_to_grant = 70 if len(game["sentence"].encode('utf-8')) > self.SHORT_SENTENCE_BYTE_LIMIT else 50
                await leveling_cog.grant_exp(message.author, exp_to_grant, channel=message.channel)
                await message.channel.send(embed=self.bot.embeds.info("게임 보상", f"타자 연습을 완료하여 경험치 **{exp_to_grant}**을 획득했습니다!"), ephemeral=True)
            del self.games[message.channel.id]

async def setup(bot: commands.Bot):
    #-- 수정된 부분: setup 함수를 원래의 간단한 형태로 되돌림
    await bot.add_cog(TajaGame(bot))