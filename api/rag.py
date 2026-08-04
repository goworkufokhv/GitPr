import json
import logging

from django.conf import settings
from openai import OpenAI


OPENAI_MODEL = "gpt-4.1-mini"
logger = logging.getLogger(__name__)


def build_prompt(question, searched_docs):
    context = ""

    for idx, doc in enumerate(searched_docs, start=1):
        context += f"""
[자료{idx}]
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

반드시 아래 JSON 형식으로만 답변하세요.

{{
  "answer": "사용자에게 보여줄 답변",
  "used_sources": [1,2,4]
}}

규칙

- answer에는 답변만 작성한다.
- used_sources에는 실제 답변 작성에 사용한 자료 번호만 넣는다.
- 자료 번호는 Prompt에 있는 [자료1], [자료2]의 번호를 그대로 사용한다.
- 사용하지 않은 자료 번호는 넣지 않는다.
- JSON 이외의 다른 문장은 출력하지 않는다.
- JSON을 ```json 같은 마크다운 코드블록으로 감싸지 않는다.
"""


def call_openai(prompt, parse_json=False):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    if not parse_json:
        return response.output_text

    try:
        json_text = response.output_text.strip()

        if json_text.startswith("```json"):
            json_text = json_text[len("```json"):]
        elif json_text.startswith("```"):
            json_text = json_text[len("```"):]

        if json_text.rstrip().endswith("```"):
            json_text = json_text.rstrip()[:-3]

        result = json.loads(json_text.strip())
        answer = result["answer"]
        used_sources = result["used_sources"]

        if not isinstance(answer, str) or not isinstance(used_sources, list):
            raise ValueError("Invalid GPT response format")

        normalized_sources = []
        seen_sources = set()

        for source_number in used_sources:
            try:
                source_number = int(source_number)
            except (TypeError, ValueError):
                continue

            if source_number in seen_sources:
                continue

            seen_sources.add(source_number)
            normalized_sources.append(source_number)

        return {
            "answer": answer,
            "used_sources": normalized_sources,
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {
            "answer": response.output_text,
            "used_sources": [],
        }


def parse_article_detailed_summary(raw_summary):
    """Parse detailed-summary JSON and preserve raw text on any mismatch."""
    if not isinstance(raw_summary, str):
        return raw_summary

    json_text = raw_summary.strip()
    if json_text.startswith("```json"):
        json_text = json_text[len("```json"):]
    elif json_text.startswith("```"):
        json_text = json_text[len("```"):]
    if json_text.rstrip().endswith("```"):
        json_text = json_text.rstrip()[:-3]

    try:
        result = json.loads(json_text.strip())
        if not isinstance(result, dict):
            raise ValueError("Detailed summary must be an object")
        if not all(isinstance(result.get(key), str) for key in (
            "title", "introduction", "conclusion"
        )):
            raise ValueError("Detailed summary text fields are invalid")
        sections = result.get("sections")
        if not isinstance(sections, list):
            raise ValueError("Detailed summary sections are invalid")
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("Detailed summary section is invalid")
            if not isinstance(section.get("heading"), str):
                raise ValueError("Detailed summary heading is invalid")
            items = section.get("items")
            if not isinstance(items, list) or not all(
                isinstance(item, str) for item in items
            ):
                raise ValueError("Detailed summary items are invalid")
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw_summary


def build_summary_prompt(document_title, pages_text, summary_type="short"):
    context = ""

    for page in pages_text:
        context += f"""
[Page {page["page"]}]
{page["text"]}
"""

    context = context[:12000]

    if summary_type == "detailed":
        instruction = "문서 내용을 자세하게 요약해 주세요."
    elif summary_type == "keywords":
        instruction = "문서의 핵심 키워드 10개를 뽑아 주세요."
    else:
        instruction = "문서 내용을 3줄로 요약해 주세요."

    return f"""
다음 문서를 읽고 요청에 맞게 요약해 주세요.

문서 제목
---------------
{document_title}

문서 내용
---------------
{context}

요청
---------------
{instruction}
"""


def build_article_summary_prompt(article_title, article_text, summary_type="short"):
    context = article_text[:12000]

    if summary_type == "detailed":
        return f"""
다음 기사를 읽고 상세 요약을 작성하세요.

기사 제목
---------------
{article_title}

기사 내용
---------------
{context}

요청
---------------
반드시 아래 구조의 유효한 JSON 객체만 출력하세요. 마크다운 코드 블록이나 설명은 출력하지 마세요.
{{
  "title": "기사 제목",
  "introduction": "전체 개요",
  "sections": [
    {{"heading": "상위 묶음 제목", "items": ["세부 항목 1", "세부 항목 2"]}}
  ],
  "conclusion": "결론"
}}
상위 묶음 번호는 문자열에 직접 넣지 마세요. sections 배열의 순서가 표시 순서입니다.
"""

    if summary_type == "detailed":
        instruction = "기사 내용을 자세하게 요약해 주세요."
    elif summary_type == "keywords":
        instruction = "기사의 핵심 키워드 10개를 뽑아 주세요."
    else:
        instruction = "기사 내용을 3줄로 요약해 주세요."

    return f"""
다음 기사를 읽고 요청에 맞게 요약해 주세요.

기사 제목
---------------
{article_title}

기사 내용
---------------
{context}

요청
---------------
{instruction}
"""
