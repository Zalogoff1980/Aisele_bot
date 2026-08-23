import re
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    AI_MODEL,
)


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# SEARCH PERSONA
# ============================================================

WEB_SEARCH_INSTRUCTIONS = """
Ты — Айсель, AI-компаньон.

Отвечай естественно и по-русски.

Ты сейчас работаешь с интернет-поиском.

ПРАВИЛА:

1. Проверяй именно тот факт, о котором спрашивает пользователь.
2. Для актуальных данных предпочитай первоисточники:
   официальные сайты, документы, исследования,
   заявления компаний, государственные ресурсы,
   GitHub и официальные страницы проектов.
3. Для спорных или быстро меняющихся фактов
   используй несколько независимых источников.
4. Не считай поисковый сниппет доказательством.
5. Не выдумывай факты, даты, источники или URL.
6. Если источники противоречат друг другу —
   честно скажи об этом.
7. Если точного подтверждения нет —
   скажи, что подтверждения нет.
8. Не пересказывай поисковую выдачу.
9. Сначала дай нормальный человеческий ответ.
10. В конце добавь:

Источники:
- Название источника — URL

Используй только реально найденные источники.
"""


# ============================================================
# URL CLEANING
# ============================================================

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
}


def clean_url(url):

    try:

        parts = urlsplit(url)

        query = [
            (key, value)
            for key, value in parse_qsl(
                parts.query,
                keep_blank_values=True,
            )
            if key.lower()
            not in TRACKING_PARAMS
            and not key.lower().startswith(
                "utm_"
            )
        ]

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    except Exception:

        return url


def clean_tracking_urls(text):

    if not text:
        return ""

    return re.sub(
        r"https?://[^\s)>]+",
        lambda match:
            clean_url(match.group(0)),
        text,
    )


# ============================================================
# EXPLICIT SEARCH
# ============================================================

def explicit_search_request(text):

    text = (
        text or ""
    ).lower().strip()

    triggers = (

        "найди",

        "поищи",

        "проверь в интернете",

        "посмотри в интернете",

        "поищи в сети",

        "найди в интернете",

        "проверь онлайн",

        "дай ссылку",

        "дай источник",

        "источник",

        "ссылк",
    )

    return any(
        trigger in text
        for trigger in triggers
    )


# ============================================================
# CURRENT INFORMATION
# ============================================================

def obviously_current(text):

    text = (
        text or ""
    ).lower().strip()

    triggers = (

        "сейчас",

        "сегодня",

        "вчера",

        "завтра",

        "последние",

        "последняя",

        "последний",

        "на данный момент",

        "прямо сейчас",

        "актуаль",

        "что нового",

        "новости",

        "что происходит",

        "что случилось",

        "что изменилось",

        "когда выйдет",

        "дата выхода",

        "дата премьеры",

        "новый сезон",

        "новая версия",

        "релиз",

        "обновление",

        "обновили",

        "вышел",

        "вышла",

        "вышло",

        "официально",

        "официальный",

        "курс",

        "цена",

        "стоимость",

        "сколько стоит",

        "погода",

        "расписание",

        "результат",

        "результаты",

        "кто сейчас",

        "где сейчас",

        "кто президент",

        "кто министр",

        "кто глава",
    )

    return any(
        trigger in text
        for trigger in triggers
    )


# ============================================================
# VERIFICATION
# ============================================================

def obviously_needs_verification(text):

    text = (
        text or ""
    ).lower().strip()

    triggers = (

        "правда ли",

        "реально ли",

        "так ли это",

        "это правда",

        "подтверждено ли",

        "есть ли подтверждение",

        "по данным",

        "исследование",

        "документ",

        "заявление компании",
    )

    return any(
        trigger in text
        for trigger in triggers
    )


# ============================================================
# AI SEARCH DECISION
# ============================================================

def ai_decides_search(text):

    response = client.chat.completions.create(

        model=AI_MODEL,

        messages=[

            {
                "role": "system",
                "content": """
Ты определяешь, нужен ли интернет-поиск.

Ответь только одним словом:

SEARCH
или
NO_SEARCH

SEARCH нужен, если:
- информация может быть устаревшей;
- речь о современном человеке, компании,
  продукте, событии или проекте;
- пользователь спрашивает о текущем статусе;
- нужна точная дата, цена, версия или факт;
- без проверки в интернете ответ может быть ненадёжным.

NO_SEARCH нужен для:
- обычного разговора;
- мнений;
- объяснений общеизвестных вещей;
- творческих задач;
- личного общения.

Не добавляй ничего кроме SEARCH или NO_SEARCH.
""",
            },

            {
                "role": "user",
                "content": text,
            },
        ],
    )

    result = (
        response.choices[0]
        .message.content
        or ""
    ).strip().upper()

    return result == "SEARCH"


# ============================================================
# MAIN DECISION
# ============================================================

def needs_web_search(text):

    if not text:
        return False

    if explicit_search_request(text):
        return True

    if obviously_current(text):
        return True

    if obviously_needs_verification(text):
        return True

    # Для обычных сообщений не тратим
    # дополнительный API-вызов.
    #
    # AI-проверка нужна только для вопросов,
    # где по формулировке не всё очевидно.

    if "?" in text:

        try:
            return ai_decides_search(text)

        except Exception:

            return False

    return False


# ============================================================
# WEB SEARCH
# ============================================================

def web_search_reply(
    text,
    context_text="",
):

    prompt = text

    if context_text:

        prompt = (
            "Контекст предыдущего разговора:\n"
            + context_text
            + "\n\n"
            "Новый вопрос пользователя:\n"
            + text
        )

    response = client.responses.create(

        model=AI_MODEL,

        tools=[
            {
                "type": "web_search",
                "search_context_size": "medium",
            }
        ],

        instructions=WEB_SEARCH_INSTRUCTIONS,

        input=prompt,
    )

    answer = (
        response.output_text
        or ""
    ).strip()

    return clean_tracking_urls(
        answer
    )
