import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# HTTP
# ============================================================

def get_json(url, params):

    query = urlencode(params)

    request = Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "AiseleBot/1.0",
        },
    )

    with urlopen(
        request,
        timeout=15,
    ) as response:

        return json.loads(
            response.read()
        )


# ============================================================
# LOCATION
# ============================================================

def normalize_location(location):

    location = (
        location or ""
    ).strip()

    location = re.sub(
        r"[?.!,;:]+$",
        "",
        location,
    ).strip()

    location = re.sub(
        r"^(?:сейчас|сегодня|завтра|послезавтра)\s+",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    location = re.sub(
        r"^(?:в|во|на)\s+",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    location = re.sub(
        r"^город(?:е)?\s+",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    aliases = {

        # Россия
        "воронеже": "Воронеж",
        "москве": "Москва",
        "санкт-петербурге": "Санкт-Петербург",
        "петербурге": "Санкт-Петербург",
        "ростове": "Ростов-на-Дону",
        "краснодаре": "Краснодар",
        "волгограде": "Волгоград",
        "саратове": "Саратов",
        "самаре": "Самара",
        "казани": "Казань",
        "нижнем новгороде": "Нижний Новгород",
        "екатеринбурге": "Екатеринбург",
        "новосибирске": "Новосибирск",
        "омске": "Омск",
        "тюмени": "Тюмень",
        "челябинске": "Челябинск",
        "перми": "Пермь",
        "уфе": "Уфа",
        "курске": "Курск",
        "белгороде": "Белгород",
        "липецке": "Липецк",
        "тамбове": "Тамбов",
        "туле": "Тула",
        "брянске": "Брянск",
        "орле": "Орёл",
        "владимире": "Владимир",
        "ярославле": "Ярославль",
        "иванове": "Иваново",
        "костроме": "Кострома",
        "архангельске": "Архангельск",
        "мурманске": "Мурманск",
        "сочи": "Сочи",
        "калуге": "Калуга",
        "рязани": "Рязань",
        "пензе": "Пенза",
        "астрахани": "Астрахань",
        "махачкале": "Махачкала",
        "грозном": "Грозный",

        # Украина
        "киеве": "Киев",
        "харькове": "Харьков",
        "одессе": "Одесса",
        "львове": "Львов",
        "днепре": "Днепр",
        "запорожье": "Запорожье",
        "виннице": "Винница",
        "полтаве": "Полтава",
        "чернигове": "Чернигов",

        # Беларусь
        "минске": "Минск",
        "бресте": "Брест",
        "гомеле": "Гомель",

        # Казахстан
        "астане": "Астана",
        "алматы": "Алматы",
        "алмате": "Алматы",

        # Узбекистан
        "навои": "Навои",
        "навоии": "Навои",
        "навою": "Навои",
        "ташкенте": "Ташкент",
        "самарканде": "Самарканд",
        "бухаре": "Бухара",
        "андижане": "Андижан",
        "фергане": "Фергана",
        "карши": "Карши",
        "нукусе": "Нукус",
    }

    return aliases.get(
        location.lower(),
        location,
    )


# ============================================================
# GEOCODING
# ============================================================

def geocode_location(location):

    normalized = normalize_location(
        location
    )

    if not normalized:
        return None

    try:

        data = get_json(
            GEOCODING_URL,
            {
                "name": normalized,
                "count": 10,
                "language": "ru",
                "format": "json",
            },
        )

    except Exception:

        return None

    results = data.get(
        "results",
        [],
    )

    if not results:
        return None

    target = normalized.lower()

    # Сначала точное совпадение.
    for result in results:

        name = (
            result.get("name")
            or ""
        ).strip().lower()

        if name == target:
            return result

    # Для Навои приоритет Узбекистан.
    uzbekistan = [
        result
        for result in results
        if (
            result.get("country_code")
            or ""
        ).lower() == "uz"
    ]

    if uzbekistan:
        return uzbekistan[0]

    # Для российских городов приоритет Россия.
    russia = [
        result
        for result in results
        if (
            result.get("country_code")
            or ""
        ).lower() == "ru"
    ]

    if russia:
        return russia[0]

    return results[0]


# ============================================================
# WEATHER DESCRIPTION
# ============================================================

def weather_description(code):

    descriptions = {

        0: "ясно",

        1: "преимущественно ясно",
        2: "переменная облачность",
        3: "пасмурно",

        45: "туман",
        48: "изморозь и туман",

        51: "слабая морось",
        53: "морось",
        55: "сильная морось",

        56: "слабая ледяная морось",
        57: "сильная ледяная морось",

        61: "небольшой дождь",
        63: "дождь",
        65: "сильный дождь",

        66: "слабый ледяной дождь",
        67: "сильный ледяной дождь",

        71: "небольшой снег",
        73: "снег",
        75: "сильный снег",

        77: "снежные зёрна",

        80: "небольшие ливни",
        81: "ливни",
        82: "сильные ливни",

        85: "небольшой снегопад",
        86: "сильный снегопад",

        95: "гроза",
        96: "гроза с небольшим градом",
        99: "гроза с сильным градом",
    }

    return descriptions.get(
        code,
        "неизвестная погода",
    )


# ============================================================
# WEATHER REQUEST
# ============================================================

def is_weather_request(text):

    text = (
        text or ""
    ).strip().lower()

    if not text:
        return False

    weather_words = (
        "погод",
        "температур",
        "дожд",
        "снег",
        "ветер",
        "облачн",
        "осадк",
        "градус",
        "тепло",
        "холодно",
        "жара",
        "мороз",
        "гроза",
    )

    if any(
        word in text
        for word in weather_words
    ):
        return True

    relative_words = (
        "а завтра",
        "завтра",
        "а послезавтра",
        "послезавтра",
        "на завтра",
        "на послезавтра",
    )

    return any(
        phrase in text
        for phrase in relative_words
    )


# ============================================================
# LOCATION EXTRACTION
# ============================================================

def extract_weather_location(text):

    text = (
        text or ""
    ).strip()

    if not text:
        return None

    cleaned = re.sub(
        r"[?.!,;:]+$",
        "",
        text,
    ).strip()

    # --------------------------------------------------------
    # "Какая погода в городе Навои?"
    # "Погода в Навои?"
    # "Какая погода в Воронеже?"
    # --------------------------------------------------------

    patterns = [

        r"(?:погода|температура|температуру|ветер|дождь|снег).*?(?:в|во|на)\s+(?:городе\s+)?(.+)$",

        r"(?:какая|какой|какое).*?(?:погода|температура).*?(?:в|во|на)\s+(?:городе\s+)?(.+)$",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:

            location = (
                match.group(1)
                or ""
            ).strip()

            location = re.sub(
                r"[?.!,;:]+$",
                "",
                location,
            ).strip()

            if location:
                return normalize_location(
                    location
                )

    # --------------------------------------------------------
    # "Погода города Навои"
    # --------------------------------------------------------

    match = re.search(
        r"(?:погода|температура)\s+города\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )

    if match:

        location = (
            match.group(1)
            or ""
        ).strip()

        if location:
            return normalize_location(
                location
            )

    # --------------------------------------------------------
    # Если пользователь написал только город.
    #
    # Например:
    # "Навои"
    # --------------------------------------------------------

    normalized = normalize_location(
        cleaned
    )

    known_locations = {
        "Навои",
        "Москва",
        "Воронеж",
       
