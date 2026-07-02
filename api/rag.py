from dotenv import load_dotenv
from openai import OpenAI
import os
from pdf_to_chroma import search_chroma

# ------------------------------------
# API Key 읽기
# ------------------------------------
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

masked = api_key[:10] + "*" * (len(api_key) - 10)

print(masked)

client = OpenAI(api_key=api_key)

def build_prompt(question,searched_docs):

    context=""

    for idx, doc in enumerate(searched_docs, start=1): #enumerate가 객체를 순서대로 출력하는 거였나?
        context += f"""
[자료 {idx}]
파일 : {doc["file_name"]}
페이지 : {doc["page"]}

내용:
{doc["text"]}
        """

    prompt=f"""
너는 대학생을 도와주는 AI 학습 도우미이다.

아래 자료만 참고해서 질문에 답변해라.
자료에 없는 내용은 추측하지 말고, "자료에서 확인할 수 없습니다."라고 말해라.

자료
---------------
{context}

질문
---------------
{question}

답변 형식
-----------------
1. 핵심 답변
2. 쉬운 설명
3. 참고한 출처
"""
    
    return prompt

def call_openai(prompt):
    response=client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text

if __name__ == "__main__":
    question="Kubernetes의 특징은 뭐야?"

    searched_docs=search_chroma(question)

    prompt=build_prompt(question, searched_docs)

    answer=call_openai(prompt)

    print("\n===== GPT 답변 =====")
    print(answer)