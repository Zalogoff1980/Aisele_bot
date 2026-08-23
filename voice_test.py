import os
import tempfile
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY


client = OpenAI(
    api_key=OPENAI_API_KEY
)


TEXT = (
    "Привет. Я Айсель. "
    "Давай проверим, насколько естественно я могу звучать по-русски. "
    "Я не диктор и не голосовой помощник. "
    "Я просто разговариваю с тобой."
)


# ============================================================
# ГОЛОСА ДЛЯ ТЕСТА
# ============================================================

VOICES = [
    "coral",
    "shimmer",
    "marin",
]


INSTRUCTIONS = """
Говори на естественном русском языке.

Русский язык — родной.
Никакого иностранного акцента.

Ты взрослая русскоязычная женщина.

Говори естественно, спокойно и уверенно.
Не используй манеру диктора.
Не звучишь как оператор поддержки.
Не читай текст монотонно.

Используй естественные русские ударения,
живой ритм речи и нормальные паузы.

Не переигрывай эмоции.
Не используй нарочитое придыхание.
Не пытайся звучать сексуально.

Ты разговариваешь с человеком,
а не читаешь ему заранее подготовленный текст.

Всегда говори о себе в женском роде.
"""


def make_voice(
    voice,
    output_path,
):

    print(
        f"Генерирую голос: {voice}"
    )

    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=TEXT,
        instructions=INSTRUCTIONS,
        response_format="mp3",
    )

    response.stream_to_file(
        output_path
    )

    print(
        f"Готово: {output_path}"
    )


def main():

    output_dir = Path(
        "voice_tests"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    print()
    print(
        "================================"
    )
    print(
        "      ТЕСТ ГОЛОСА АЙСЕЛЬ"
    )
    print(
        "================================"
    )
    print()

    for voice in VOICES:

        output_file = (
            output_dir
            / f"aisele_{voice}.mp3"
        )

        try:

            make_voice(
                voice,
                str(output_file),
            )

        except Exception as error:

            print()
            print(
                f"ОШИБКА {voice}:"
            )
            print(error)
            print()

    print()
    print(
        "================================"
    )
    print(
        "ТЕСТ ЗАВЕРШЁН"
    )
    print(
        "================================"
    )
    print()
    print(
        "Файлы находятся в папке:"
    )
    print(
        "voice_tests/"
    )
    print()

    for voice in VOICES:

        print(
            f"{voice}: "
            f"voice_tests/aisele_{voice}.mp3"
        )


if __name__ == "__main__":
    main()
