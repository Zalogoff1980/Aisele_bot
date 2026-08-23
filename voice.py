import io
import logging
import os
import re

from telegram import Update
from telegram.ext import ContextTypes

from elevenlabs.client import ElevenLabs

from main import (
    ensure_user,
    save_message,
    process_emotion,
    transcribe_voice,
    generate_text_reply,
)

from memory import get_recent_messages


logger = logging.getLogger(__name__)


# ============================================================
# ELEVENLABS
# ============================================================

ELEVENLABS_API_KEY = os.getenv(
    "ELEVENLABS_API_KEY"
)

ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID"
)

ELEVENLABS_MODEL = "eleven_multilingual_v2"


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
# НАСТРОЙКИ ГОЛОСА
# ============================================================

VOICE_SETTINGS = {
    "stability": 0.42,
    "similarity_boost": 0.85,
    "style": 0.40,
    "use_speaker_boost": True,
}


# ============================================================
# НОРМАЛИЗАЦИЯ ТЕКСТА
# ============================================================

def normalize_command(text):
    """
    Приводит команду к нормальному виду.

    Например:

    "Повтори это голосом!"
    "повтори это голосом"
    "ПОвтори   это   голосом"

    превратятся в одно и то же.
    """

    text = text or ""

    text = text.lower().strip()

    text = text.replace("ё", "е")

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


# ============================================================
# КОМАНДЫ ГОЛОСА
# ============================================================

VOICE_COMMANDS = {
    "ответь голосом",
    "ответь это голосом",
    "ответь своим голосом",
    "скажи голосом",
    "скажи это голосом",
    "озвучь ответ",
    "озвучь это",
    "озвучь это голосом",
    "озвучь свой ответ",
    "озвучь свой последний ответ",
    "повтори голосом",
    "повтори это голосом",
    "повтори своим голосом",
    "повтори это своим голосом",
    "повтори свой ответ голосом",
    "повтори свой последний ответ голосом",
    "повтори свой последний ответ своим голосом",
}


def is_voice_command(text):
    normalized = normalize_command(text)

    if normalized in VOICE_COMMANDS:
        return True

    # На случай небольшой разницы в формулировке.
    patterns = (
        r"^повтори.*голосом$",
        r"^повтори.*своим голосом$",
        r"^озвучь.*ответ$",
        r"^озвучь.*голосом$",
        r"^скажи.*голосом$",
        r"^ответь.*голосом$",
    )

    for pattern in patterns:
        if re.match(
            pattern,
            normalized,
            re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# ПОИСК ПОСЛЕДНЕГО ОТВЕТА АЙСЕЛЬ
# ============================================================

def get_last_assistant_message(user_id):

    messages = get_recent_messages(
        user_id,
        limit=50,
    )

    for message in reversed(messages):

        role = message.get("role")

        content = (
            message.get("content")
            or ""
        ).strip()

        if (
            role == "assistant"
            and content
        ):
            return content

    return None


# ============================================================
# ELEVENLABS TTS
# ============================================================

def synthesize_speech(text):

    text = (
        text or ""
    ).strip()

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
        eleven_client.text_to_speech.convert(
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
# ОТПРАВКА ГОЛОСА
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
# ГОЛОСОВОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ
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

        # ----------------------------------------------------
        # TELEGRAM -> AUDIO
        # ----------------------------------------------------

        telegram_file = (
            await context.bot.get_file(
                voice.file_id
            )
        )

        audio_bytes = bytes(
            await telegram_file.download_as_bytearray()
        )

        # ----------------------------------------------------
        # AUDIO -> TEXT
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ОБЫЧНАЯ ЛОГИКА АЙСЕЛЬ
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # OPENAI -> ОТВЕТ
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ELEVENLABS -> ГОЛОС
        # ----------------------------------------------------

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
# ТЕКСТ + КОМАНДЫ ОЗВУЧКИ
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

    logger.info(
        "Text command received: %r",
        text,
    )

    # ========================================================
    # КОМАНДА ПОВТОРИТЬ ГОЛОСОМ
    # ========================================================

    if is_voice_command(text):

        logger.info(
            "VOICE REPEAT COMMAND DETECTED: %r",
            text,
        )

        try:

            user_id = (
                update.effective_user.id
            )

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

            logger.info(
                "Repeating assistant message: %s",
                last_answer[:150],
            )

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
    # ОБЫЧНЫЙ ТЕКСТ
    # ========================================================

    from main import text_handler

    await text_handler(
        update,
        context,
        )
