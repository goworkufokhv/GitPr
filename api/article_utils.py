import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class ArticleExtractionError(Exception):
    """Base exception for failures that should be hidden from API clients."""


class InvalidArticleUrlError(ArticleExtractionError):
    pass


class ArticleNetworkError(ArticleExtractionError):
    pass


class EmptyArticleBodyError(ArticleExtractionError):
    pass


class ArticleParseError(ArticleExtractionError):
    pass


def _is_valid_article_url(url):
    if not isinstance(url, str):
        return False

    try:
        parsed_url = urlparse(url)
        return (
            parsed_url.scheme in {"http", "https"}
            and bool(parsed_url.netloc)
            and bool(parsed_url.hostname)
        )
    except ValueError:
        return False


def extract_article_text(url):
    if not _is_valid_article_url(url):
        logger.warning("[Article Error] Invalid URL")
        raise InvalidArticleUrlError

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
        logger.warning("[Article Error] Network Error")
        raise ArticleNetworkError from exc

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        paragraphs = [
            paragraph.get_text(" ", strip=True)
            for paragraph in soup.find_all("p")
        ]
        text = "\n".join(paragraph for paragraph in paragraphs if paragraph)
    except Exception as exc:
        raise ArticleParseError from exc

    if not text:
        logger.warning("[Article Error] Empty Article Body")
        raise EmptyArticleBodyError

    return {
        "title": title,
        "text": text
    }
