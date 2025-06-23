# 1. 베이스 이미지 설정
# 안정적인 최신 파이썬 3.12 슬림 버전을 기반으로 이미지를 만듭니다.
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
# 컨테이너 내에서 명령어가 실행될 기본 경로를 /app 으로 설정합니다.
WORKDIR /app

# 3. 의존성 설치 (캐시 활용 최적화)
# 먼저 requirements.txt 파일만 복사하여 라이브러리를 설치합니다.
# 이렇게 하면 봇 코드만 변경되었을 때, 매번 라이브러리를 새로 설치하지 않고 캐시를 사용하여 빌드 속도가 빨라집니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 복사
# 프로젝트의 소스 코드 폴더(안쪽 discord_bot)를 컨테이너의 /app 디렉토리로 복사합니다.
COPY ./discord_bot/ .

# 5. 봇 실행 명령어 설정
# 컨테이너가 시작될 때 실행할 명령어를 지정합니다.
CMD ["python", "bot.py"]