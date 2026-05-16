FROM python:3.14-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 전체 복사
COPY . .

# Gunicorn으로 Django 실행
CMD ["gunicorn", "lotto_site.wsgi:application", "--bind", "0.0.0.0:8000"]

