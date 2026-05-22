import datetime as dt
import email.utils
import html
import os
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import json


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

RSS_QUERIES = [
    "global economy OR markets OR inflation when:2d",
    "geopolitics OR war OR election OR diplomacy when:2d",
    "artificial intelligence OR technology OR cybersecurity when:2d",
    "climate OR energy OR oil OR renewable when:2d",
    "health OR science OR outbreak OR space when:2d",
    "supply chain OR semiconductor OR critical minerals when:2d",
]


def require_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fetch_url(url, data=None, headers=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 daily-global-trends-bot",
            **(headers or {}),
        },
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_google_news(query):
    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    url = f"{GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"
    xml = fetch_url(url)
    root = ET.fromstring(xml)

    items = []
    for item in root.findall("./channel/item")[:12]:
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        published_raw = item.findtext("pubDate") or ""

        published = published_raw
        if published_raw:
            try:
                parsed = email.utils.parsedate_to_datetime(published_raw)
                published = parsed.astimezone(dt.timezone.utc).isoformat()
            except Exception:
                pass

        if title and link:
            items.append({
                "title": title,
                "source": source,
                "url": link,
                "published": published,
                "query": query,
            })

    return items


def collect_items():
    seen = set()
    collected = []

    for query in RSS_QUERIES:
        try:
            items = fetch_google_news(query)
        except Exception as exc:
            print(f"RSS fetch failed for {query}: {exc}")
            continue

        for item in items:
            key = item["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            collected.append(item)

    return collected[:45]


def build_prompt(items):
    today_tw = dt.datetime.now(
        dt.timezone(dt.timedelta(hours=8))
    ).strftime("%Y-%m-%d")

    source_lines = "\n".join(
        f"- [{i+1}] {item['title']} | {item['source']} | {item['published']} | {item['url']}"
        for i, item in enumerate(items)
    )

    return textwrap.dedent(f"""
    You are preparing a daily global trends briefing for a Taiwan-based reader.
    Today is {today_tw} in Asia/Taipei.

    Use the source candidates below. Select 5 to 7 genuinely important and diverse global trend items.
    Do not limit the digest to Taiwan and do not limit it to AI.
    Prefer credible, recent, internationally relevant items. Avoid duplicates and clickbait.

    Write the final answer in Traditional Chinese.
    For English or foreign-language sources, translate and summarize naturally into Traditional Chinese.

    For each item, include:
    1. Main point.
    2. Core concept or nature of the event.
    3. Relevant risks, technical issues, policy problems, implementation challenges, or likely impact when applicable.
    4. An opposing, skeptical, affected-party, or alternative viewpoint when useful.
    5. Original title, source name, and URL.

    Each item should be substantial, roughly 150 to 250 Chinese characters or more if needed.

    End with a section titled exactly:
    今日全球趨勢判讀

    Add 3 to 5 concise bullets about the most important patterns and what deserves continued tracking.

    Source candidates:
    {source_lines}
    """).strip()


def call_openai(prompt):
    api_key = require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-5.2"

    payload = {
        "model": model,
        "input": prompt,
    }

    raw = fetch_url(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    response = json.loads(raw.decode("utf-8"))

    if response.get("output_text"):
        return response["output_text"].strip()

    parts = []
    for output in response.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)

    if not parts:
        raise RuntimeError(f"OpenAI response did not contain text: {response}")

    return "\n".join(parts).strip()


def split_telegram(text, limit=3900):
    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        paragraph_len = len(paragraph) + 2
        if current and current_len + paragraph_len > limit:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = paragraph_len
        else:
            current.append(paragraph)
            current_len += paragraph_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def send_telegram(message):
    token = require_env("TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = split_telegram(message)

    for index, chunk in enumerate(chunks, start=1):
        text = chunk
        if len(chunks) > 1:
            text = f"{text}\n\n({index}/{len(chunks)})"

        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "false",
        }).encode("utf-8")

        raw = fetch_url(url, data=body)
        result = json.loads(raw.decode("utf-8"))

        if not result.get("ok"):
            raise RuntimeError(f"Telegram send failed: {result}")


def main():
    items = collect_items()
    if not items:
        raise RuntimeError("No news items collected.")

    digest = call_openai(build_prompt(items))
    send_telegram(digest)

    print("Digest sent to Telegram.")


if __name__ == "__main__":
    main()
