import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COMMONS_API = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = (
    "AiseleBot/1.0 "
    "(Telegram weather assistant)"
)

logger = logging.getLogger(__name__)


# ============================================================
# HTTP / JSON
# ============================================================

def get_json(params):

    url = (
        COMMONS_API
        + "?"
        + urlencode(params)
    )

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
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
# DOWNLOAD IMAGE
# ============================================================

def download_image(url):

    if not url:
        return None

    try:

        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "image/*",
            },
        )

        with urlopen(
            request,
            timeout=20,
        ) as response:

            image_bytes = response.read()

        if not image_bytes:
            return None

        # Защита от случайного HTML вместо изображения.
        if image_bytes[:20].lower().startswith(
            (
                b"<!doctype",
                b"<html",
                b"<head",
            )
        ):
            return None

        return image_bytes

    except Exception:

        logger.exception(
            "Failed to download image: %s",
            url,
        )

        return None


# ============================================================
# LOCATION NORMALIZATION
# ============================================================

def build_queries(location):

    original = (
        location or ""
    ).strip()

    if not original:
        return []

    lower = original.lower()

    queries = []

    def add(value):

        value = (
            value or ""
        ).strip()

        if not value:
            return

        if value.lower() not in {
            q.lower()
            for q in queries
        }:

            queries.append(value)

    # --------------------------------------------------------
    # Специальные варианты известных городов
    # --------------------------------------------------------

    if (
        "навои" in lower
        or "navoi" in lower
        or "navoiy" in lower
    ):

        add("Navoiy Uzbekistan")
        add("Navoi Uzbekistan")
        add("Navoiy city")
        add("Navoi city")
        add("Navoiy panorama")
        add("Navoi panorama")
        add("Navoiy skyline")
        add("Navoi skyline")
        add("Navoiy landmark")

    elif (
        "воронеж" in lower
        or "voronezh" in lower
    ):

        add("Voronezh Russia")
        add("Voronezh city")
        add("Voronezh panorama")
        add("Voronezh skyline")
        add("Voronezh landmarks")

    # --------------------------------------------------------
    # Универсальные варианты
    # --------------------------------------------------------

    add(original)
    add(f"{original} city")
    add(f"{original} panorama")
    add(f"{original} skyline")
    add(f"{original} landmark")

    return queries


# ============================================================
# IMAGE SEARCH
# ============================================================

def search_images(query):

    try:

        data = get_json(
            {
                "action": "query",
                "format": "json",

                "generator": "search",

                "gsrsearch": query,

                "gsrnamespace": 6,

                "gsrlimit": 15,

                "gsrsort": "relevance",

                "prop": "imageinfo",

                "iiprop": (
                    "url|mime|size"
                ),

                "iiurlwidth": 1280,
            }
        )

    except Exception:

        logger.exception(
            "Wikimedia search failed: %s",
            query,
        )

        return []

    pages = (
        data
        .get("query", {})
        .get("pages", {})
    )

    results = []

    for page in pages.values():

        title = page.get(
            "title",
            "",
        )

        imageinfo = page.get(
            "imageinfo",
            [],
        )

        if not imageinfo:
            continue

        info = imageinfo[0]

        mime = (
            info.get(
                "mime",
                "",
            )
            or ""
        ).lower()

        # ----------------------------------------------------
        # Оставляем только нормальные растровые изображения
        # ----------------------------------------------------

        allowed_mimes = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        }

        if mime not in allowed_mimes:
            continue

        # ----------------------------------------------------
        # Сначала используем уменьшенную версию
        # ----------------------------------------------------

        url = info.get(
            "thumburl"
        )

        if not url:

            url = info.get(
                "url"
            )

        if not url:
            continue

        width = info.get(
            "width",
            0,
        )

        height = info.get(
            "height",
            0,
        )

        # ----------------------------------------------------
        # Не берём совсем маленькие картинки
        # ----------------------------------------------------

        try:

            if (
                width
                and height
                and (
                    width < 500
                    or height < 300
                )
            ):
                continue

        except Exception:
            pass

        results.append(
            {
                "title": title,
                "url": url,
                "mime": mime,
                "width": width,
                "height": height,
            }
        )

    return results


# ============================================================
# IMAGE SCORE
# ============================================================

def score_image(
    result,
    location,
):

    title = (
        result.get(
            "title",
            "",
        )
        or ""
    ).lower()

    location_lower = (
        location or ""
    ).lower()

    score = 0

    # --------------------------------------------------------
    # Предпочитаем фотографии, а не карты / гербы / логотипы
    # --------------------------------------------------------

    bad_words = (
        "map",
        "карта",
        "coat of arms",
        "герб",
        "logo",
        "логотип",
        "flag",
        "флаг",
        "diagram",
        "схема",
        "location map",
        "locator",
    )

    for word in bad_words:

        if word in title:

            score -= 50

    # --------------------------------------------------------
    # Панорамы и городские виды — плюс
    # --------------------------------------------------------

    good_words = (
        "panorama",
        "skyline",
        "city",
        "центр",
        "center",
        "street",
        "улица",
        "view",
        "вид",
        "landscape",
        "landmark",
        "monument",
        "площадь",
        "square",
    )

    for word in good_words:

        if word in title:

            score += 10

    # --------------------------------------------------------
    # Совпадение с названием города
    # --------------------------------------------------------

    location_parts = re_split_location(
        location_lower
    )

    for part in location_parts:

        if len(part) >= 4 and part in title:

            score += 20

    # --------------------------------------------------------
    # Предпочитаем горизонтальные фотографии
    # --------------------------------------------------------

    width = result.get(
        "width",
        0,
    )

    height = result.get(
        "height",
        0,
    )

    try:

        if width and height:

            ratio = width / height

            if ratio >= 1.25:

                score += 15

            elif ratio >= 1.05:

                score += 8

    except Exception:
        pass

    return score


# ============================================================
# LOCATION WORDS
# ============================================================

def re_split_location(
    location,
):

    text = (
        location or ""
    ).lower()

    replacements = (
        ",",
        ".",
        "-",
        "_",
        "/",
    )

    for char in replacements:

        text = text.replace(
            char,
            " ",
        )

    words = text.split()

    # --------------------------------------------------------
    # Русские названия → полезные английские варианты
    # --------------------------------------------------------

    mapping = {
        "навои": "navoiy",
        "воронеж": "voronezh",
        "москва": "moscow",
        "санкт": "saint",
        "петербург": "petersburg",
        "ташкент": "tashkent",
        "самарканд": "samarkand",
        "бухара": "bukhara",
        "казань": "kazan",
        "сочи": "sochi",
    }

    result = []

    for word in words:

        result.append(
            word
        )

        if word in mapping:

            result.append(
                mapping[word]
            )

    return result


# ============================================================
# GET CITY IMAGE
# ============================================================

def get_city_image(
    location,
):

    location = (
        location or ""
    ).strip()

    if not location:
        return None

    queries = build_queries(
        location
    )

    logger.info(
        "City image search: %s",
        queries,
    )

    candidates = []

    # ========================================================
    # SEARCH
    # ========================================================

    for query in queries:

        results = search_images(
            query
        )

        if not results:
            continue

        for result in results:

            result["score"] = score_image(
                result,
                location,
            )

            candidates.append(
                result
            )

    if not candidates:

        logger.warning(
            "No Wikimedia images found for %s",
            location,
        )

        return None

    # ========================================================
    # SORT
    # ========================================================

    candidates.sort(
        key=lambda item: item.get(
            "score",
            0,
        ),
        reverse=True,
    )

    # ========================================================
    # TRY BEST IMAGES
    # ========================================================

    tried_urls = set()

    for candidate in candidates[:20]:

        url = candidate.get(
            "url"
        )

        if not url:
            continue

        if url in tried_urls:
            continue

        tried_urls.add(
            url
        )

        logger.info(
            "Trying city image: %s | score=%s | %s",
            candidate.get(
                "title",
                "",
            ),
            candidate.get(
                "score",
                0,
            ),
            url,
        )

        image_bytes = download_image(
            url
        )

        if image_bytes:

            logger.info(
                "City image found for %s: %s",
                location,
                candidate.get(
                    "title",
                    "",
                ),
            )

            return image_bytes

    # ========================================================
    # NOTHING
    # ========================================================

    logger.warning(
        "Could not download any city image for %s",
        location,
    )

    return None
