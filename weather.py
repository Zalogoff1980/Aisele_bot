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
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=15) as response:
        data = response.read()

    return json.loads(data)


# ============================================================
# CLEAN LOCATION
# ============================================================

def clean_location(location):
    location = (location or "").strip()

    # Убираем знаки препинания в конце
    location = re.sub(
        r"[?.!,;:]+$",
        "",
        location,
    ).strip()

    # Убираем типичные слова из голосовых запросов
    location = re.sub(
        r"^(сейчас|сегодня|на данный момент)\s+",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    # Убираем фразы, которые иногда остаются после
    # распознавания естественной речи
    location = re.sub(
        r"\s+(сейчас|сегодня|на данный момент)$",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    return location


# ============================================================
# LOCATION
# ============================================================

def geocode_location(location):
    location = clean_location(location)

    if not location:
        return None

    # Сначала обычный поиск.
    # Если пользователь указал регион/страну,
    # Open-Meteo сам умеет использовать это как уточнение.
    attempts = [
        location,
    ]

    # Дополнительные варианты для русских окончаний.
    # Например: "в Воронеже" уже должен быть очищен,
    # но иногда распознавание голоса оставляет лишние слова.
    simplified = re.sub(
        r"^(в|во|на|из|для)\s+",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip()

    if simplified and simplified.lower() != location.lower():
        attempts.append(simplified)

    for query_location in attempts:

        try:
            data = get_json(
                GEOCODING_URL,
                {
                    "name": query_location,
                    "count": 10,
                    "language": "ru",
                    "format": "json",
                },
            )

        except (
            URLError,
            HTTPError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        if not isinstance(data, dict):
            continue

        results = data.get(
            "results",
            [],
        )

        if not results:
            continue

        target = query_location.lower().strip()

        # ----------------------------------------------------
        # 1. Точное совпадение названия
        # ----------------------------------------------------

        for result in results:

            name = str(
                result.get("name", "")
            ).strip().lower()

            if name == target:
                return result

        # ----------------------------------------------------
        # 2. Совпадение без диакритики/лишних пробелов
        # ----------------------------------------------------

        normalized_target = re.sub(
            r"\s+",
            " ",
            target,
        )

        for result in results:

            name = str(
                result.get("name", "")
            ).strip().lower()

            name = re.sub(
                r"\s+",
                " ",
                name,
            )

            if name == normalized_target:
                return result

        # ----------------------------------------------------
        # 3. Если точного совпадения нет —
        #    выбираем наиболее населённый вариант.
        # ----------------------------------------------------

        results_with_population = [
            result
            for result in results
            if result.get("population") is not None
        ]

        if results_with_population:

            results_with_population.sort(
                key=lambda item: (
                    item.get("population") or 0
                ),
                reverse=True,
            )

            return results_with_population[0]

        # ----------------------------------------------------
        # 4. Последний вариант — первый результат.
        # ----------------------------------------------------

        return results[0]

    return None


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

def get_weather(location, days=3):

    location = clean_location(location)

    if not location:
        return {
            "success": False,
            "error": "Не удалось определить место.",
        }

    place = geocode_location(location)

    if not place:
        return {
            "success": False,
            "error": (
                f"Не удалось найти место: {location}"
            ),
        }

    latitude = place.get("latitude")
    longitude = place.get("longitude")

    if latitude is None or longitude is None:
        return {
            "success": False,
            "error": (
                f"Не удалось определить координаты "
                f"места: {location}"
            ),
        }

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

                "forecast_days": max(
                    1,
                    min(int(days), 7),
                ),

                "timezone": timezone,
            },
        )

    except (
        URLError,
        HTTPError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:

        return {
            "success": False,
            "error": (
                "Не удалось получить "
                "данные о погоде."
            ),
        }

    if not isinstance(weather, dict):
        return {
            "success": False,
            "error": (
                "Сервис погоды вернул "
                "неверный ответ."
            ),
        }

    if weather.get("error"):
        return {
            "success": False,
            "error": (
                weather.get(
                    "reason",
                    "Сервис погоды вернул ошибку.",
                )
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
# FORMAT
# ============================================================

def format_weather(data):

    if not data.get("success"):
        return data.get(
            "error",
            "Не удалось получить погоду.",
        )

    location = data.get(
        "location",
        {},
    )

    current = data.get(
        "current",
        {},
    )

    daily = data.get(
        "daily",
        {},
    )

    name = location.get(
        "name",
        "неизвестном месте",
    )

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
            f"Влажность: {round(humidity)}%."
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
            f"Облачность: {round(cloud)}%."
        )

    if precipitation is not None and precipitation > 0:
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

        line = f"{date}: {desc}"

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
                f"{round(probability)}%"
            )

        if rain is not None and rain > 0:
            line += (
                f", осадки около "
                f"{round(rain, 1)} мм"
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
        "жарко",
        "мороз",
        "морозн",
        "облачн",
        "осадк",
        "ливн",
        "гроза",
        "туман",
        "холодно",
        "тепло",
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

    if not text:
        return None

    # --------------------------------------------------------
    # Нормализация
    # --------------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # --------------------------------------------------------
    # Убираем типичные вводные слова
    # --------------------------------------------------------

    cleaned = re.sub(
        r"^(скажи|подскажи|расскажи|покажи|можешь|можно)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # --------------------------------------------------------
    # Основные конструкции
    # --------------------------------------------------------

    patterns = (

        r"(?:какая|какая сейчас|какая сегодня)\s+"
        r"погод[аы]?\s+(?:сейчас\s+)?"
        r"(?:в|во|на|для)\s+(.+)$",

        r"погод[аы]?\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|на|для)\s+(.+)$",

        r"температур[аы]?\s+"
        r"(?:сейчас\s+)?"
        r"(?:в|во|на|для)\s+(.+)$",

        r"прогноз\s+"
        r"(?:погод[ыа]\s+)?"
        r"(?:сейчас\s+)?"
        r"(?:в|во|на|для)\s+(.+)$",

        r"что там\s+"
        r"(?:с погодой\s+)?"
        r"(?:в|во|на)\s+(.+)$",

        r"как там\s+"
        r"(?:с погодой\s+)?"
        r"(?:в|во|на)\s+(.+)$",

        r"будет ли\s+"
        r"(?:дождь|снег|гроза)\s+"
        r"(?:в|во|на)\s+(.+)$",

        r"(?:дождь|снег|гроза)\s+"
        r"(?:в|во|на)\s+(.+)$",

        r"погода\s+(.+)$",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            cleaned,
            re.IGNORECASE,
        )

        if match:

            location = match.group(1).strip()

            location = clean_location(
                location
            )

            if location:
                return location

    # --------------------------------------------------------
    # Фолбэк:
    # если есть погодное слово, а явного "в/на" нет,
    # пробуем взять всё после него.
    #
    # Например:
    # "погода Воронеж"
    # "температура Москва"
    # --------------------------------------------------------

    fallback_patterns = (

        r"погод[аы]?\s+(.+)$",

        r"температур[аы]?\s+(.+)$",

        r"прогноз\s+(.+)$",
    )

    for pattern in fallback_patterns:

        match = re.search(
            pattern,
            cleaned,
            re.IGNORECASE,
        )

        if match:

            location = clean_location(
                match.group(1)
            )

            if location:
                return location

    return None
