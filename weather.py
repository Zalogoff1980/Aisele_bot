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
            "User-Agent": "AiseleBot/1.0"
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
# LOCATION NORMALIZATION
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

        # Russia
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

        # Ukraine
        "киеве": "Киев",
        "харькове": "Харьков",
        "одессе": "Одесса",
        "львове": "Львов",
        "днепре": "Днепр",
        "запорожье": "Запорожье",
        "виннице": "Винница",
        "полтаве": "Полтава",
        "чернигове": "Чернигов",

        # Belarus
        "минске": "Минск",
        "бресте": "Брест",
        "гомеле": "Гомель",

        # Kazakhstan
        "астане": "Астана",
        "алматы": "Алматы",
        "алмате": "Алматы",

        # Uzbekistan
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

    # Сначала точное совпадение
    for result in results:

        name = (
            result.get("name")
            or ""
        ).strip().lower()

        if name == target:
            return result

    # Для Навои и других узбекских городов
    # предпочитаем Узбекистан
    uzbekistan = [
        result
        for result in results
        if (
            result.get(
                "country_code"
            )
            or ""
        ).lower() == "uz"
    ]

    if uzbekistan:
        return uzbekistan[0]

    # Затем Россия
    russia = [
        result
        for result in results
        if (
            result.get(
                "country_code"
            )
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

        77: "снежные зерна",

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
# WEATHER REQUEST DETECTION
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
        "а сегодня",
        "сегодня",
        "на сегодня",
    )

    if any(
        phrase in text
        for phrase in relative_words
    ):
        return True

    # ========================================================
    # ВАЖНО:
    #
    # Теперь:
    #
    # "А в Воронеже?"
    # "В Москве?"
    # "А в Самаре?"
    #
    # тоже считаются запросом погоды.
    # ========================================================

    city_request = re.match(
        r"^\s*"
        r"(?:а\s+)?"
        r"(?:в|во|на)\s+"
        r".+?"
        r"\s*[?!.,]*"
        r"\s*$",
        text,
        flags=re.IGNORECASE,
    )

    if city_request:
        return True

    return False


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

    # ========================================================
    # "А в Воронеже?"
    # "В Москве?"
    # "А в Самаре?"
    # ========================================================

    match = re.match(
        r"^\s*"
        r"(?:а\s+)?"
        r"(?:в|во|на)\s+"
        r"(?:городе\s+)?"
        r"(.+?)"
        r"\s*$",
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

    # ========================================================
    # Обычные запросы
    # ========================================================

    patterns = (

        r"(?:погода|температура|температуру|ветер|дождь|снег)"
        r".*?"
        r"(?:в|во|на)\s+"
        r"(?:городе\s+)?"
        r"(.+)$",

        r"(?:какая|какой|какое)"
        r".*?"
        r"(?:погода|температура)"
        r".*?"
        r"(?:в|во|на)\s+"
        r"(?:городе\s+)?"
        r"(.+)$",
    )

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

    # ========================================================
    # "погода города Воронеж"
    # ========================================================

    match = re.search(
        r"(?:погода|температура)"
        r"\s+города\s+(.+)$",
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

    return None


# ============================================================
# GET WEATHER
# ============================================================

def get_weather(
    location,
    days=3,
):

    place = geocode_location(
        location
    )

    if not place:

        return {
            "success": False,
            "error": (
                f"Не удалось найти место: "
                f"{location}"
            ),
        }

    latitude = place.get(
        "latitude"
    )

    longitude = place.get(
        "longitude"
    )

    if (
        latitude is None
        or longitude is None
    ):

        return {
            "success": False,
            "error": (
                f"Не удалось определить "
                f"координаты {location}."
            ),
        }

    try:

        weather = get_json(
            WEATHER_URL,
            {

                "latitude": latitude,

                "longitude": longitude,

                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "cloud_cover,"
                    "wind_speed_10m,"
                    "wind_gusts_10m"
                ),

                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max,"
                    "precipitation_sum,"
                    "wind_speed_10m_max"
                ),

                "forecast_days": max(
                    3,
                    min(
                        int(days),
                        7,
                    ),
                ),

                "timezone": "auto",
            },
        )

    except Exception:

        return {
            "success": False,
            "error": (
                "Не удалось получить "
                "данные о погоде прямо сейчас."
            ),
        }

    return {

        "success": True,

        "location": {

            "name": place.get(
                "name",
                location,
            ),

            "country": place.get(
                "country",
                "",
            ),

            "region": place.get(
                "admin1",
                "",
            ),

            "latitude": latitude,

            "longitude": longitude,

            "timezone": place.get(
                "timezone",
                "auto",
            ),
        },

        "current": weather.get(
            "current",
            {},
        ),

        "daily": weather.get(
            "daily",
            {},
        ),

        "hourly": weather.get(
            "hourly",
            {},
        ),
    }


# ============================================================
# FORMAT CURRENT WEATHER
# ============================================================

def format_weather(data):

    if not data.get(
        "success"
    ):

        return data.get(
            "error",
            "Не удалось получить погоду.",
        )

    location = data[
        "location"
    ]

    current = data[
        "current"
    ]

    daily = data[
        "daily"
    ]

    name = location.get(
        "name",
        "Неизвестно",
    )

    country = location.get(
        "country",
        "",
    )

    region = location.get(
        "region",
        "",
    )

    place_parts = [
        name
    ]

    if (
        region
        and region != name
    ):

        place_parts.append(
            region
        )

    if country:

        place_parts.append(
            country
        )

    place = ", ".join(
        place_parts
    )

    result = [

        f"Погода в {place}",

        (
            "Сейчас "
            + weather_description(
                current.get(
                    "weather_code"
                )
            )
            + "."
        ),
    ]

    temperature = current.get(
        "temperature_2m"
    )

    feels = current.get(
        "apparent_temperature"
    )

    humidity = current.get(
        "relative_humidity_2m"
    )

    wind = current.get(
        "wind_speed_10m"
    )

    gusts = current.get(
        "wind_gusts_10m"
    )

    cloud = current.get(
        "cloud_cover"
    )

    if temperature is not None:

        result.append(
            f"Температура: "
            f"{round(temperature)}°C."
        )

    if feels is not None:

        result.append(
            f"Ощущается как "
            f"{round(feels)}°C."
        )

    if humidity is not None:

        result.append(
            f"Влажность: "
            f"{round(humidity)}%."
        )

    if wind is not None:

        result.append(
            f"Ветер: "
            f"{round(wind)} км/ч."
        )

    if gusts is not None:

        result.append(
            f"Порывы до "
            f"{round(gusts)} км/ч."
        )

    if cloud is not None:

        result.append(
            f"Облачность: "
            f"{round(cloud)}%."
        )

    # ========================================================
    # DAILY
    # ========================================================

    dates = daily.get(
        "time",
        [],
    )

    codes = daily.get(
        "weather_code",
        [],
    )

    max_temps = daily.get(
        "temperature_2m_max",
        [],
    )

    min_temps = daily.get(
        "temperature_2m_min",
        [],
    )

    probabilities = daily.get(
        "precipitation_probability_max",
        [],
    )

    precipitation = daily.get(
        "precipitation_sum",
        [],
    )

    result.append("")
    result.append(
        "Ближайший прогноз:"
    )

    for i, date in enumerate(
        dates[:7]
    ):

        description = ""

        if i < len(codes):

            description = (
                weather_description(
                    codes[i]
                )
            )

        minimum = None

        if i < len(
            min_temps
        ):

            minimum = min_temps[i]

        maximum = None

        if i < len(
            max_temps
        ):

            maximum = max_temps[i]

        probability = None

        if i < len(
            probabilities
        ):

            probability = (
                probabilities[i]
            )

        rain = None

        if i < len(
            precipitation
        ):

            rain = (
                precipitation[i]
            )

        line = (
            f"{date}: "
            f"{description}"
        )

        if (
            minimum is not None
            and maximum is not None
        ):

            line += (
                f", "
                f"{round(minimum)}…"
                f"{round(maximum)}°C"
            )

        if probability is not None:

            line += (
                f", вероятность "
                f"осадков "
                f"{round(probability)}%"
            )

        if rain is not None:

            line += (
                f", осадки около "
                f"{round(float(rain), 1)} мм"
            )

        result.append(
            line
        )

    return "\n".join(
        result
        )
