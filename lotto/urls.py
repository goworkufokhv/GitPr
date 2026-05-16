from django.urls import path
from . import views

app_name='lotto'

urlpatterns = [
    path("buy/", views.buy_ticket, name="buy_ticket"), #사용자가 티켓을 구매할 때 buy_ticket 뷰 실행
    path("tickets/", views.my_tickets, name="my_tickets"),#로그인한 사용자의 티켓 목록을 보여주는 my_tickets 뷰 실행
    path("results/", views.check_results, name="check_results"),# 최근 추첨 결과와 사용자의 티켓을 비교하는 check_results 뷰 실행
    path('home/', views.home, name='home'),
    path("signup/", views.signup, name="signup"), #회원가입 추가
]
