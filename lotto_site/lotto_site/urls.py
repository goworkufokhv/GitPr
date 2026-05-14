"""
URL configuration for lotto_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("lotto/", include("lotto.urls")),  # 로또 앱 URL 연결
    path("accounts/", include("django.contrib.auth.urls")),  # 로그인/로그아웃 URL 연결
]

##/accounts/login/ → 기본 로그인 페이지
##/accounts/logout/ → 로그아웃 페이지
##/accounts/password_change/ → 비밀번호 변경 페이지 등 자동 제공