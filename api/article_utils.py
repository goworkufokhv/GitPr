import requests
from bs4 import BeautifulSoup


def extract_article_text(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError("Failed to fetch article.") from exc

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in soup.find_all("p")
    ]
    text = "\n".join(paragraph for paragraph in paragraphs if paragraph)

    if not text:
        raise ValueError("Article text is empty.")

    return {
        "title": title,
        "text": text
    }
