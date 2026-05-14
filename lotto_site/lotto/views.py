from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Ticket, Draw, Result
import random
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

@login_required
def buy_ticket(request):
    if request.method == "POST":
        mode = request.POST.get("mode")  # 'manual' or 'auto'
        if mode == "manual":
            numbers = request.POST.get("numbers")  # "1,2,3,4,5,6" (직접 6자리 입력)
        else:
            numbers = ",".join(map(str, random.sample(range(1, 46), 6)))#랜덤으로 6자리 지정
        Ticket.objects.create(user=request.user, numbers=numbers) ##"로그인한 사용자의 티켓을 DB에 저장"
        return redirect("lotto:my_tickets")  # ← 네임스페이스 포함
    return render(request, "lotto/buy_ticket.html") #구매 결과를 buy_ticket.html로 전달

@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(user=request.user) ##"로그인한 사용자가 구매한 티켓 목록 조회"
    return render(request, "lotto/my_tickets.html", {"tickets": tickets}) #산 티켓 정보 호출

@login_required
def check_results(request):
    latest_draw = Draw.objects.last()
    tickets = Ticket.objects.filter(user=request.user)
    results = []
    if latest_draw:
        draw_numbers = set(int(n) for n in latest_draw.numbers.split(",") if n.strip())
        for ticket in tickets:
            ticket_numbers = set(int(n) for n in ticket.numbers.split(",") if n.strip())
            matched = len(draw_numbers & ticket_numbers)
            rank = None
            if matched == 6:
                rank = 1
            elif matched == 5:
                rank = 2
            elif matched == 4:
                rank = 3
            is_winner = rank is not None

            # DB에 저장
            result, created = Result.objects.update_or_create(
                ticket=ticket,
                draw=latest_draw,
                defaults={
                    "is_winner": is_winner,
                    "rank": rank,
                },
            )
            results.append(result)
    return render(request, "lotto/check_results.html", {"results": results})

@login_required
def home(request):
    return render(request, 'lotto/home.html')

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()  # 새 사용자 계정 생성
            return redirect("login")  # 회원가입 후 로그인 페이지로 이동
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})