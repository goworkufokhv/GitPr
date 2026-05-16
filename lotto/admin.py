from django.contrib import admin
from .models import Ticket, Draw, Result
import random

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("user", "numbers", "purchased_at")
    search_fields = ("user__username", "numbers")


@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    list_display = ("draw_date", "winning_numbers")
    actions = ["make_draw"]

    def make_draw(self, request, queryset):
        # 당첨 번호 6개 뽑기
        winning_set = random.sample(range(1, 46), 6)
        draw = Draw.objects.create(winning_numbers=",".join(map(str, winning_set)))

        # 모든 티켓을 가져와서 결과 판정
        tickets = Ticket.objects.all()
        for ticket in tickets:
            ticket_nums = set(map(int, ticket.numbers.split(",")))
            match_count = len(ticket_nums.intersection(set(winning_set)))

            if match_count == 6:
                rank = "1등"; is_winner = True
            elif match_count == 5:
                rank = "2등"; is_winner = True
            elif match_count == 4:
                rank = "3등"; is_winner = True
            elif match_count == 3:
                rank = "4등"; is_winner = True
            else:
                rank = "꽝"; is_winner = False

            Result.objects.create(ticket=ticket, draw=draw, rank=rank, is_winner=is_winner)

        self.message_user(
            request,
            f"새 추첨 번호: {winning_set} | 결과가 자동 판정되었습니다."
        )

    make_draw.short_description = "새 추첨 실행 (자동 채점)"


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("ticket", "draw", "rank", "is_winner")
    list_filter = ("is_winner", "rank")
