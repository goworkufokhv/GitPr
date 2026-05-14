from django.db import models
from django.contrib.auth.models import User
import random

# 사용자가 구매한 로또 티켓을 저장하는 모델
class Ticket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  
    # 티켓을 구매한 사용자 (User 모델과 연결, 유저가 삭제되면 티켓도 함께 삭제됨)

    numbers = models.CharField(max_length=50)  
    # 선택한 번호들을 문자열로 저장 (예: "1,5,12,23,34,45")

    purchased_at = models.DateTimeField(auto_now_add=True)  
    # 티켓 구매 시각을 자동으로 기록

    def __str__(self):
        # 관리자 페이지 등에서 티켓을 "사용자명 - 번호" 형태로 표시
        return f"{self.user.username} - {self.numbers}"


# 로또 추첨 결과(당첨 번호)를 저장하는 모델
class Draw(models.Model):
    draw_date = models.DateTimeField(auto_now_add=True)  
    # 추첨이 생성된 날짜/시간을 자동 기록

    numbers = models.CharField(max_length=50)  
    # 추첨된 번호들을 문자열로 저장 (예: "3,12,19,25,33,41")

    @staticmethod
    def generate_numbers():
        # 1~45 사이에서 랜덤으로 6개 번호를 뽑아 문자열로 반환
        return ",".join(map(str, random.sample(range(1, 46), 6)))

    def __str__(self):
        # 관리자 페이지 등에서 "추첨날짜 - 번호" 형태로 표시
        return f"Draw {self.draw_date} - {self.numbers}"


# 티켓과 추첨 결과를 연결해 당첨 여부를 기록하는 모델
class Result(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)  
    # 어떤 티켓의 결과인지 연결 (티켓 삭제 시 결과도 삭제됨)

    draw = models.ForeignKey(Draw, on_delete=models.CASCADE)  
    # 어떤 추첨과 연결된 결과인지 지정

    rank = models.IntegerField(null=True, blank=True)  
    # 당첨 등수 (1등, 2등, 3등 등). 당첨이 없으면 null

    is_winner = models.BooleanField(default=False)  
    # 당첨 여부 (True: 당첨, False: 꽝)

    def __str__(self):
        # 관리자 페이지 등에서 "사용자명 - 등수" 또는 "No Win"으로 표시
        return f"{self.ticket.user.username} - {self.rank if self.is_winner else 'No Win'}"
