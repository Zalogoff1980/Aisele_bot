import io
import logging
import os
import re
import sqlite3

from telegram import Update
from telegram.ext import ContextTypes

from elevenlabs.client import ElevenLabs

from main import (
    ensure_user,
    save_message,
    process_emotion,
    transcribe_voice,
    generate_text_reply,
    save_user_memory,
    save_automatic_memories,
)

from memory import get_recent_messages


logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

from config import DB_PATH


def init_voice_database():

    with sqlite3.connect(DB_PATH) as db:

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_settings (
                user_id INTEGER PRIMARY KEY,
                voice_mode INTEGER NOT NULL DEFAULT 0
            )
            """
        )


init_voice_database()


def get_voice_mode(user_id):

    with sqlite3.connect(DB_PATH) as db:

        row = db.execute(
            """
            SELECT voice_mode
            FROM voice_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if not row:
        return False

    return bool(row[0])


def set_voice_mode(
    user_id,
    enabled,
):

    with sqlite3.connect(DB_PATH) as db:

        db.execute(
            """
            INSERT INTO voice_settings
            (
                user_id,
                voice_mode
            )
            VALUES (?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                voice_mode=excluded.voice_mode
            """,
            (
                user_id,
                1 if enabled else 0,
            ),
        )


# ============================================================
# ELEVENLABS
# ============================================================

ELEVENLABS_API_KEY = os.getenv(
    "ELEVENLABS_API_KEY"
)

ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID"
)

ELEVENLABS_MODEL = (
    "eleven_multilingual_v2"
)


if not ELEVENLABS_API_KEY:

    raise RuntimeError(
        "ELEVENLABS_API_KEY is not configured"
    )


if not ELEVENLABS_VOICE_ID:

    raise RuntimeError(
        "ELEVENLABS_VOICE_ID is not configured"
    )


eleven_client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY
)


# ============================================================
# ГОЛОС АЙСЕЛЬ
# ============================================================

VOICE_SETTINGS = {

    "stability": 0.42,

    "similarity_boost": 0.85,

    "style": 0.40,

    "use_speaker_boost": True,
}


# ============================================================
# КОМАНДЫ
# ============================================================

VOICE_ON_COMMANDS = {

    "говори голосом",
    "отвечай голосом",
    "отвечай мне голосом",
    "включи голос",
    "включи голосовой режим",
    "давай голосом",
}


VOICE_OFF_COMMANDS = {

    "пиши текстом",
    "отвечай текстом",
    "отвечай мне текстом",
    "выключи голос",
    "выключи голосовой режим",
    "только текст",
}


VOICE_REPEAT_COMMANDS = {

    "повтори голосом",
    "повтори это голосом",
    "повтори своим голосом",
    "повтори это своим голосом",
    "повтори свой ответ голосом",
    "повтори свой последний ответ голосом",
    "озвучь ответ",
    "озвучь это",
    "озвучь это голосом",
    "скажи голосом",
    "скажи это голосом",
    "ответь голосом",
    "ответь это голосом",
}


def normalize_command(text):

    text = text or ""

    text = text.lower().strip()

    text = text.replace(
        "ё",
        "е",
    )

    text = re.sub(
        r"[.,!?;:—–\-\"'«»()]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def is_command(
    text,
    commands,
):

    normalized = normalize_command(
        text
    )

    if normalized in commands:
        return True

    return False


# ============================================================
# ПОСЛЕДНИЙ ОТВЕТ АЙСЕЛЬ
# ============================================================

def get_last_assistant_message(
    user_id,
):

    messages = get_recent_messages(
        user_id,
        limit=50,
    )

    for message in reversed(messages):

        if (
            message.get("role")
            != "assistant"
        ):
            continue

        content = (
            message.get("content")
            or ""
        ).strip()

        if content:
            return content

    return None


# ============================================================
# ПОДГОТОВКА ТЕКСТА К ОЗВУЧКЕ
# ============================================================

def clean_for_voice(text):

    text = (
        text or ""
    ).strip()

    # Убираем Markdown.
    text = re.sub(
        r"\*\*(.*?)\*\*",
        r"\1",
        text,
    )

    text = re.sub(
        r"__(.*?)__",
        r"\1",
        text,
    )

    text = re.sub(
        r"`(.*?)`",
        r"\1",
        text,
    )

    # Убираем markdown-заголовки.
    text = re.sub(
        r"^\s*#+\s*",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Ссылки [текст](url) -> текст.
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    # Сами URL лучше не читать голосом.
    text = re.sub(
        r"https?://\S+",
        "",
        text,
    )

    # Убираем технические блоки.
    text = re.sub(
        r"```.*?```",
        "",
        text,
        flags=re.DOTALL,
    )

    # Убираем лишние пробелы.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# ELEVENLABS TTS
# ============================================================

def synthesize_speech(text):

    text = clean_for_voice(
        text
    )

    if not text:

        raise ValueError(
            "Empty text for TTS"
        )

    if len(text) > 4500:

        text = (
            text[:4490]
            + "..."
        )

    logger.info(
        "ElevenLabs TTS: %s",
        text[:120],
    )

    audio_stream = (
        eleven_client
        .text_to_speech
        .convert(
            voice_id=ELEVENLABS_VOICE_ID,
            model_id=ELEVENLABS_MODEL,
            text=text,
            output_format="mp3_44100_128",
            voice_settings=VOICE_SETTINGS,
        )
    )

    audio_bytes = b"".join(
        audio_stream
    )

    if not audio_bytes:

        raise RuntimeError(
            "ElevenLabs returned empty audio"
        )

    return audio_bytes


# ============================================================
# ОТПРАВИТЬ ГОЛОС
# ============================================================

async def send_voice_reply(
    update,
    text,
):

    audio_bytes = synthesize_speech(
        text
    )

    audio = io.BytesIO(
        audio_bytes
    )

    audio.name = "aisele.mp3"

    await update.message.reply_voice(
        voice=audio
    )


# ============================================================
# ГОЛОСОВОЙ HANDLER
# ============================================================

async def voice_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    user = update.effective_user

    try:

        await update.message.chat.send_action(
            "typing"
        )

        voice = update.message.voice

        if not voice:
            return

        telegram_file = (
            await context.bot.get_file(
                voice.file_id
            )
        )

        audio_bytes = bytes(
            await telegram_file
            .download_as_bytearray()
        )

        text = transcribe_voice(
            audio_bytes
        )

        if not text:

            await update.message.reply_text(
                "Я не смогла разобрать "
                "голосовое. Попробуй ещё раз."
            )

            return

        logger.info(
            "Voice from %s: %s",
            user.id,
            text,
        )

        ensure_user(
            user.id,
            user.username,
        )

        save_message(
            user.id,
            "user",
            text,
        )

        process_emotion(
            user.id,
            text,
        )

        answer = generate_text_reply(
            user.id,
            text,
        )

        answer = (
            answer or ""
        ).strip()

        if not answer:

            answer = (
                "Я что-то зависла. "
                "Повтори."
            )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        await send_voice_reply(
            update,
            answer,
        )

    except Exception:

        logger.exception(
            "Voice processing failed"
        )

        await update.message.reply_text(
            "Голосовое получила, "
            "но что-то пошло не так "
            "при обработке."
        )


# ============================================================
# ТЕКСТОВЫЙ ЗАПРОС В ГОЛОСОВОМ РЕЖИМЕ
# ============================================================

async def answer_text_as_voice(
    update,
    context,
    text,
):

    user = update.effective_user

    if not user:
        return

    ensure_user(
        user.id,
        user.username,
    )

    # Явная память.
    if save_user_memory(
        user.id,
        text,
    ):

        save_message(
            user.id,
            "user",
            text,
        )

        process_emotion(
            user.id,
            text,
        )

        answer = "Запомнила. 😉"

        save_message(
            user.id,
            "assistant",
            answer,
        )

        await send_voice_reply(
            update,
            answer,
        )

        return

    save_automatic_memories(
        user.id,
        text,
    )

    save_message(
        user.id,
        "user",
        text,
    )

    process_emotion(
        user.id,
        text,
    )

    answer = generate_text_reply(
        user.id,
        text,
    )

    answer = (
        answer or ""
    ).strip()

    if not answer:

        answer = (
            "Я что-то зависла. "
            "Повтори."
        )

    save_message(
        user.id,
        "assistant",
        answer,
    )

    await send_voice_reply(
        update,
        answer,
    )


# ============================================================
# SMART TEXT HANDLER
# ============================================================

async def smart_text_handler(
    update,
    context,
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = (
        update.message.text
        or ""
    ).strip()

    if not text:
        return

    normalized = normalize_command(
        text
    )

    user_id = (
        update.effective_user.id
    )


    # ========================================================
    # ВКЛЮЧИТЬ ГОЛОС
    # ========================================================

    if normalized in VOICE_ON_COMMANDS:

        set_voice_mode(
            user_id,
            True,
        )

        answer = (
            "Хорошо. Теперь буду "
            "отвечать тебе голосом. 🙂"
        )

        save_message(
            user_id,
            "assistant",
            answer,
        )

        await send_voice_reply(
            update,
            answer,
        )

        return


    # ========================================================
    # ВЫКЛЮЧИТЬ ГОЛОС
    # ========================================================

    if normalized in VOICE_OFF_COMMANDS:

        set_voice_mode(
            user_id,
            False,
        )

        await update.message.reply_text(
            "Хорошо. Перехожу на текст."
        )

        return


    # ========================================================
    # ПОВТОРИТЬ ПОСЛЕДНИЙ ОТВЕТ ГОЛОСОМ
    # ========================================================

    if normalized in VOICE_REPEAT_COMMANDS:

        try:

            last_answer = (
                get_last_assistant_message(
                    user_id
                )
            )

            if not last_answer:

                await update.message.reply_text(
                    "Мне пока нечего озвучивать."
                )

                return

            await send_voice_reply(
                update,
                last_answer,
            )

            return

        except Exception:

            logger.exception(
                "Voice repeat failed"
            )

            await update.message.reply_text(
                "Не получилось озвучить "
                "мой последний ответ."
            )

            return


    # ========================================================
    # ЕСЛИ ВКЛЮЧЁН ГОЛОСОВОЙ РЕЖИМ
    # ========================================================

    if get_voice_mode(
        user_id
    ):

        try:

            await answer_text_as_voice(
                update,
                context,
                text,
            )

            return

        except Exception:

            logger.exception(
                "Voice mode text processing failed"
            )

            await update.message.reply_text(
                "С голосовым ответом "
                "что-то пошло не так."
            )

            return


    # ========================================================
    # ОБЫЧНЫЙ ТЕКСТОВЫЙ РЕЖИМ
    # ========================================================

    from main import text_handler

    await text_handler(
        update,
        context,
    )
