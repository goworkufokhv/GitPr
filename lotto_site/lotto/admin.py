from django.contrib import admin
from .models import Ticket, Draw, Result

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("user", "numbers", "purchased_at")
    search_fields = ("user__username", "numbers")

@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    list_display = ("draw_date", "numbers")
    actions = ["make_draw"]

    def make_draw(self, request, queryset):
        import random
        numbers = ",".join(map(str, random.sample(range(1, 46), 6)))
        Draw.objects.create(numbers=numbers)
        self.message_user(request, f"새 추첨 번호가 생성되었습니다: {numbers}")
    make_draw.short_description = "새 추첨 실행"

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("ticket", "draw", "rank", "is_winner")
    list_filter = ("is_winner", "rank")
