from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# 보안 키는 환경변수로 관리 권장
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-...")

# DEBUG는 문자열이 아니라 불리언 값으로 설정해야 합니다
DEBUG = True

# Docker 환경에서는 * 로 두는 게 편리하지만,
# 실제 배포 시에는 도메인/IP를 명시하는 게 안전합니다
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "lotto",  # ✅ 앱을 루트로 옮겼다면 이렇게 단순화
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lotto_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # 프로젝트 전역 템플릿 폴더
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lotto_site.wsgi.application"
ASGI_APPLICATION = "lotto_site.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "lotto_db"),
        "USER": os.environ.get("POSTGRES_USER", "lotto_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "lotto_pass"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인/로그아웃 리다이렉트
LOGIN_REDIRECT_URL = "/lotto/home/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
