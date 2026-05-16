from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Ticket, Draw, Result
import random
from django.contrib.auth.forms import UserCreationForm

@login_required
def buy_ticket(request):
    if request.method == "POST":
        mode = request.POST.get("mode")  # 'manual' or 'auto'
        if mode == "manual":
            numbers = request.POST.get("numbers")  # "1,2,3,4,5,6"
        else:
            numbers = ",".join(map(str, random.sample(range(1, 46), 6)))
        Ticket.objects.create(user=request.user, numbers=numbers)
        return redirect("lotto:my_tickets")
    return render(request, "lotto/buy_ticket.html")

@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(user=request.user)
    return render(request, "lotto/my_tickets.html", {"tickets": tickets})

@login_required
def check_results(request):
    latest_draw = Draw.objects.last()
    tickets = Ticket.objects.filter(user=request.user)
    results = []
    if latest_draw:
        draw_numbers = set(int(n) for n in latest_draw.winning_numbers.split(",") if n.strip())
        for ticket in tickets:
            ticket_numbers = set(int(n) for n in ticket.numbers.split(",") if n.strip())
            matched = len(draw_numbers & ticket_numbers)

            # 규칙: 6개=1등, 5개=2등, 4개=3등, 3개=4등, 나머지=꽝
            rank = None
            if matched == 6:
                rank = 1
            elif matched == 5:
                rank = 2
            elif matched == 4:
                rank = 3
            elif matched == 3:
                rank = 4

            is_winner = rank is not None

            result, created = Result.objects.update_or_create(
                ticket=ticket,
                draw=latest_draw,
                defaults={
                    "is_winner": is_winner,
                    "rank": rank,
                },
            )
            # ✅ matched 개수를 템플릿에서 쓸 수 있도록 임시 속성으로 추가
            result.matched = matched
            results.append(result)
    return render(request, "lotto/check_results.html", {"results": results})

@login_required
def home(request):
    return render(request, 'lotto/home.html')

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
