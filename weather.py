import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ============================================================
# OPEN-METEO
# ============================================================

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
        timeout=10,
    ) as response:
        data = response.read()

    return json.loads(data)


# ============================================================
# LOCATION NORMALIZATION
# ============================================================

def normalize_location(location):
    """
    Приводит русские названия городов к форме,
    которую лучше понимает геокодер.
    """

    location = (
        location or ""
    ).strip()

    if not location:
        return ""

    # Убираем лишние слова вокруг названия города.
    location = re.sub(
        r"^(?:сейчас|сегодня|завтра)\s+",
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
        r"[?.!,;:]+$",
        "",
        location,
    ).strip()

    # Частые падежные формы.
    aliases = {
        "воронеже": "Воронеж",
        "москве": "Москва",
        "санкт-петербурге": "Санкт-Петербург",
        "петербурге": "Санкт-Петербург",
        "ленинграде": "Санкт-Петербург",

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
        "воркуте": "Воркута",

        "сочи": "Сочи",
        "адлере": "Адлер",

        "калуге": "Калуга",
        "рязані": "Рязань",
        "рязани": "Рязань",
        "пензе": "Пенза",
        "астрахани": "Астрахань",
        "махачкале": "Махачкала",
        "грозном": "Грозный",
    }

    return aliases.get(
        location.lower(),
        location,
    )


# ============================================================
# LOCATION
# ============================================================

def geocode_location(location):
    location = (
        location or ""
    ).strip()

    if not location:
        return None

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

    except (
        URLError,
        HTTPError,
        TimeoutError,
        Exception,
    ):
        return None

    results = data.get(
        "results",
        [],
    )

    if not results:
        return None

    # Сначала ищем точное совпадение.
    location_lower = normalized.lower()

    for result in results:
        name = (
            result.get("name", "")
            .strip()
            .lower()
        )

        if name == location_lower:
            return result

    # Затем предпочитаем результат из России,
    # если он есть.
    russian_results = [
        result
        for result in results
        if (
            result.get("country_code", "")
            .lower()
            == "ru"
        )
    ]

    if russian_results:
        return russian_results[0]

    return results[0]


# ============================================================
# WEATHER CODE
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
# WEATHER
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

    name = place.get(
        "name",
        location,
    )

    country = place.get(
        "country",
        "",
    )

    admin1 = place.get(
        "admin1",
        "",
    )

    timezone = place.get(
        "timezone",
        "auto",
    )

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
                    "rain,"
                    "weather_code,"
                    "cloud_cover,"
                    "wind_speed_10m,"
                    "wind_gusts_10m"
                ),

                "hourly": (
                    "temperature_2m,"
                    "precipitation_probability,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),

                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max,"
                    "precipitation_sum,"
                    "wind_speed_10m_max"
                ),

                "forecast_days": days,

                "timezone": timezone,
            },
        )

    except (
        URLError,
        HTTPError,
        TimeoutError,
        Exception,
    ):
        return {
            "success": False,
            "error": (
                "Не удалось получить "
                "данные о погоде."
            ),
        }

    return {
        "success": True,

        "location": {
            "name": name,
            "country": country,
            "region": admin1,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
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
# FORMAT WEATHER
# ============================================================

def format_weather(data):
    if not data.get("success"):
        return data.get(
            "error",
            "Не удалось получить погоду.",
        )

    location = data["location"]
    current = data["current"]
    daily = data["daily"]

    name = location["name"]

    country = location.get(
        "country",
        "",
    )

    region = location.get(
        "region",
        "",
    )

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

    precipitation = current.get(
        "precipitation"
    )

    cloud = current.get(
        "cloud_cover"
    )

    code = current.get(
        "weather_code"
    )

    description = weather_description(
        code
    )

    place_parts = [name]

    if region and region != name:
        place_parts.append(region)

    if country:
        place_parts.append(country)

    place = ", ".join(
        place_parts
    )

    result = []

    result.append(
        f"Погода в {place}"
    )

    result.append(
        f"Сейчас {description}."
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
            f"Влажность: {humidity}%."
        )

    if wind is not None:
        result.append(
            f"Ветер: {round(wind)} км/ч."
        )

    if gusts is not None:
        result.append(
            f"Порывы до {round(gusts)} км/ч."
        )

    if cloud is not None:
        result.append(
            f"Облачность: {cloud}%."
        )

    if (
        precipitation is not None
        and precipitation > 0
    ):
        result.append(
            f"Осадки сейчас: "
            f"{precipitation} мм."
        )

    # --------------------------------------------------------
    # ПРОГНОЗ
    # --------------------------------------------------------

    dates = daily.get(
        "time",
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

    precipitation_probability = daily.get(
        "precipitation_probability_max",
        [],
    )

    precipitation_sum = daily.get(
        "precipitation_sum",
        [],
    )

    codes = daily.get(
        "weather_code",
        [],
    )

    if dates:
        result.append("")
        result.append(
            "Ближайший прогноз:"
        )

    for index, date in enumerate(
        dates[:3]
    ):
        max_temp = (
            max_temps[index]
            if index < len(max_temps)
            else None
        )

        min_temp = (
            min_temps[index]
            if index < len(min_temps)
            else None
        )

        probability = (
            precipitation_probability[index]
            if index < len(
                precipitation_probability
            )
            else None
        )

        rain = (
            precipitation_sum[index]
            if index < len(
                precipitation_sum
            )
            else None
        )

        code = (
            codes[index]
            if index < len(codes)
            else None
        )

        desc = weather_description(
            code
        )

        line = (
            f"{date}: {desc}"
        )

        if min_temp is not None:
            line += (
                f", {round(min_temp)}…"
            )

        if max_temp is not None:
            line += (
                f"{round(max_temp)}°C"
            )

        if probability is not None:
            line += (
                f", вероятность осадков "
                f"{probability}%"
            )

        if (
            rain is not None
            and rain > 0
        ):
            line += (
                f", осадки около "
                f"{rain} мм"
            )

        result.append(line)

    return "\n".join(result)


# ============================================================
# WEATHER INTENT
# ============================================================

def is_weather_request(text):
    text = (
        text or ""
    ).lower()

    weather_words = (
        "погод",
        "температур",
        "дожд",
        "снег",
        "ветер",
        "прогноз",
        "жара",
        "мороз",
        "облачн",
        "осадк",
    )

    return any(
        word in text
        for word in weather_words
    )


# ============================================================
# LOCATION EXTRACTION
# ============================================================

def extract_weather_location(text):
    text = (
        text or ""
    ).strip()

    # --------------------------------------------------------
    # Важно:
    # сначала проверяем конструкции со словом "сейчас",
    # чтобы "Какая погода сейчас в Воронеже?"
    # не превращалась в "сейчас в Воронеже".
    # --------------------------------------------------------

    patterns = (

        # Какая погода сейчас в Воронеже?
        r"(?:какая|какая сейчас)\s+"
        r"погод[аы]?\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|на)\s+"
        r"(.+)$",

        # Какая сейчас погода в Воронеже?
        r"какая\s+сейчас\s+"
        r"погод[аы]?\s+"
        r"(?:в|во|на)\s+"
        r"(.+)$",

        # Погода сейчас в Воронеже
        r"погод[ауы]?\s+"
        r"сейчас\s+"
        r"(?:в|во|на)\s+"
        r"(.+)$",

        # Погода в Воронеже
        r"погод[ауы]?\s+"
        r"(?:в|во|для|на)\s+"
        r"(.+)$",

        # Температура сейчас в Воронеже
        r"температур[аы]?\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|для|на)\s+"
        r"(.+)$",

        # Прогноз в Воронеже
        r"прогноз\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|для|на)\s+"
        r"(.+)$",

        # Погода Воронеж
        r"погода\s+(.+)$",

        # Что там сейчас в Воронеже?
        r"что там\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|на)\s+"
        r"(.+)$",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        location = (
            match.group(1)
            .strip()
        )

        location = re.sub(
            r"[?.!,;:]+$",
            "",
            location,
        ).strip()

        # Дополнительная страховка.
        location = re.sub(
            r"^сейчас\s+"
            r"(?:в|во|на)\s+",
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

        if location:
            return normalize_location(
                location
            )

    return None
