from django.db import models
from django.contrib.auth.models import User
import random

# 사용자가 구매한 로또 티켓을 저장하는 모델
class Ticket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    numbers = models.CharField(max_length=50)  # "1,5,12,23,34,45"
    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.numbers}"


def generate_numbers():
    # 1~45 사이에서 랜덤으로 6개 번호를 뽑아 문자열로 반환
    return ",".join(map(str, random.sample(range(1, 46), 6)))


# 로또 추첨 결과(당첨 번호)를 저장하는 모델
class Draw(models.Model):
    draw_date = models.DateTimeField(auto_now_add=True)
    winning_numbers = models.CharField(max_length=50, default=generate_numbers)  # 당첨 번호 6개

    def __str__(self):
        return f"Draw {self.id} - {self.draw_date}"


# 티켓과 추첨 결과를 연결해 당첨 여부를 기록하는 모델
class Result(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    draw = models.ForeignKey(Draw, on_delete=models.CASCADE)
    rank = models.IntegerField(null=True, blank=True)  # 1~4등, 없으면 null
    is_winner = models.BooleanField(default=False)

    def __str__(self):
        if self.is_winner:
            return f"{self.ticket.user.username} - {self.rank}등"
        return f"{self.ticket.user.username} - No Win"
