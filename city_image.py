import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def get_json(params):

    request = Request(
        COMMONS_API + "?" + urlencode(params),
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


def get_city_image(
    location,
):

    location = (
        location or ""
    ).strip()

    if not location:
        return None

    queries = (
        location,
        f"{location} city",
        f"{location} panorama",
        f"{location} skyline",
    )

    for query in queries:

        try:

            data = get_json(
                {
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrnamespace": 6,
                    "gsrlimit": 8,
                    "prop": "imageinfo",
                    "iiprop": "url|mime",
                }
            )

            pages = (
                data
                .get("query", {})
                .get("pages", {})
            )

            for page in pages.values():

                imageinfo = page.get(
                    "imageinfo",
                    [],
                )

                if not imageinfo:
                    continue

                info = imageinfo[0]

                url = info.get(
                    "url"
                )

                mime = info.get(
                    "mime",
                    "",
                )

                if not url:
                    continue

                if not mime.startswith(
                    "image/"
                ):
                    continue

                try:

                    request = Request(
                        url,
                        headers={
                            "User-Agent":
                                "AiseleBot/1.0"
                        },
                    )

                    with urlopen(
                        request,
                        timeout=20,
                    ) as response:

                        image_bytes = (
                            response.read()
                        )

                    if image_bytes:
                        return image_bytes

                except Exception:
                    continue

        except Exception:
            continue

    return None
