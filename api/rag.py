import os

from dotenv import load_dotenv
from openai import OpenAI


OPENAI_MODEL = "gpt-4.1-mini"


def build_prompt(question, searched_docs):
    context = ""

    for idx, doc in enumerate(searched_docs, start=1):
        context += f"""
[자료 {idx}]
파일: {doc["file_name"]}
페이지: {doc["page"]}
청크: {doc["chunk"]}

내용:
{doc["text"]}
"""

    return f"""
너는 대학생의 학습을 도와주는 AI 학습 도우미야.

아래 자료만 참고해서 질문에 답해.
자료에 없는 내용은 추측하지 말고, "자료에서 확인할 수 없습니다."라고 말해.

자료
---------------
{context}

질문
---------------
{question}

답변 형식
---------------
1. 핵심 답변
2. 쉬운 설명
3. 참고한 출처
"""


def call_openai(prompt):
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    # ==============================
    # GPT에게 전달되는 Prompt 출력
    # ==============================
    print("\n" + "=" * 80)
    print("[DEBUG] GPT에 전달되는 Prompt")
    print("=" * 80)
    print(prompt)
    print("=" * 80 + "\n")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    return response.output_text
