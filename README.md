🎵 머머리봇 (BaldheadBot) - 다기능 디스코드 봇
Gemini와 함께 개발한 파이썬 기반의 다기능 디스코드 봇입니다. 모듈화된 Cog 구조를 통해 음악, TTS, 관리, 일반 명령어 등 다양한 기능을 체계적으로 관리하고 확장할 수 있도록 설계되었습니다.

✨ 주요 기능 (Key Features)
🎶 음악 기능
유튜브 검색 및 재생: /play 또는 /검색 명령어로 노래를 검색하고, 드롭다운 메뉴를 통해 원하는 곡을 선택하여 재생합니다.
정교한 볼륨 조절: 서버 관리자가 설정하는 '기본 볼륨'과 사용자가 설정하는 '볼륨 배율'을 곱하여 최종 볼륨을 조절하는 2단계 볼륨 시스템을 갖추고 있습니다.
다양한 플레이어 컨트롤: 대기열(queue), 건너뛰기(skip), 일시정지(pause), 다시재생(resume), 정지(stop) 등 필수적인 모든 기능을 지원합니다.
자동 퇴장: 음성 채널에 봇만 혼자 남을 경우, 60초 후에 자동으로 채널을 나갑니다.
🔊 TTS (Text-to-Speech) 기능
개인별 TTS 토글: /tts 켜기, /tts 끄기 명령어로 사용자 본인의 TTS 기능만 선택적으로 활성화/비활성화할 수 있습니다.
음악 재생과 충돌 방지: 음악이 재생 중일 때는 TTS가 작동하지 않아 오디오가 겹치는 현상을 방지합니다.
기본 볼륨 조절: TTS 목소리의 기본 볼륨이 50%로 설정되어 있어 사용자의 청각을 보호합니다.
🛠️ 관리 기능
멤버 관리: /밴, /킥 명령어를 통해 서버 멤버를 추방하거나 내보낼 수 있습니다. (관리자 권한 필요)
메시지 청소: /청소 <개수> 명령어로 채팅 채널의 메시지를 한 번에 삭제할 수 있습니다. (메시지 관리 권한 필요)
⚙️ 일반 및 편의 기능
서버 및 봇 정보: /ping으로 봇의 응답 속도를, /서버정보로 현재 서버의 상세 정보를 확인할 수 있습니다.
이모지 확대: 서버 커스텀 이모지만 채팅에 입력 시, 봇이 해당 이모지를 확대해서 보여줍니다. (메시지 관리 권한이 있으면 원본 메시지는 삭제됩니다.)
외부 이모지 검색: /이모지 <이름> 명령어로 봇이 속한 다른 서버의 이모지를 불러와 사용할 수 있습니다.
🛠️ 설치 및 설정 방법 (Installation & Setup)
1. 사전 요구사항
Python 3.10 이상
FFmpeg: 음악 및 TTS 재생을 위해 반드시 설치되어 있어야 합니다. 시스템 환경 변수(PATH)에 등록하는 것을 권장합니다.
FFmpeg 공식 홈페이지
2. 설치 과정
저장소 복제 (Clone Repository)
Bash

git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
가상 환경 생성 및 활성화
Bash

# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
필요한 라이브러리 설치
Bash

pip install -r requirements.txt
3. 환경 설정
프로젝트 최상위 폴더에 아래의 두 파일을 생성하고 내용을 채워주세요.

.env 파일 (봇 토큰 관리)

DISCORD_BOT_TOKEN="여기에_디스코드_봇_토큰을_입력하세요"
my_discord_bot/data/config.json 파일 (봇 설정 관리)

JSON

{
  "prefix": "!",
  "admin_role_id": 123456789012345678,
  "vip_role_id": 123456789012345679
}
prefix: 봇의 접두사 명령어를 설정합니다.
admin_role_id, vip_role_id: core/check.py에서 커스텀 권한 체크를 구현할 경우 사용할 역할 ID입니다. (선택 사항)
4. requirements.txt 파일 생성
프로젝트에 필요한 라이브러리 목록입니다. 아래 내용을 requirements.txt 파일에 저장하세요.

discord.py>=2.3.2
python-dotenv>=1.0.0
yt-dlp>=2023.12.30
gTTS>=2.5.1
PyNaCl>=1.5.0
🚀 봇 실행 (Running the Bot)
모든 설정이 완료되었으면, 최상위 폴더(my_discord_bot/)에서 아래 명령어를 실행하여 봇을 시작합니다.

Bash

python my_discord_bot/bot.py
🏛️ 프로젝트 구조 (Project Structure)
이 봇은 기능별 모듈화(Cog)와 핵심 로직 분리(core)를 통해 높은 유지보수성과 확장성을 지향합니다.

my_discord_bot/
├── .venv/
├── my_discord_bot/
│   ├── bot.py              # 봇 메인 실행 파일
│   ├── cogs/               # 기능별 명령어 그룹 (Cogs)
│   │   ├── __init__.py
│   │   ├── general_commands.py
│   │   ├── admin_commands.py
│   │   ├── music.py
│   │   ├── tts_commands.py
│   │   └── emoji_commands.py
│   ├── core/               # 핵심 로직, 유틸리티, 커스텀 클래스
│   │   ├── __init__.py
│   │   ├── check.py        # 커스텀 권한 체크
│   │   ├── embed.py        # 표준 임베드 생성기
│   │   └── exceptions.py   # 커스텀 에러
│   └── data/               # 설정 파일 등 데이터 보관
│       └── config.json
├── .env                    # 봇 토큰 등 민감 정보
├── .gitignore
└── requirements.txt
📄 라이선스 (License)
이 프로젝트는 MIT 라이선스를 따릅니다.
