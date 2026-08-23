import io
import logging
import os
import re
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from main import (
    client,
    ensure_user,
    save_message,
    process_emotion,
    transcribe_voice,
    generate_text_reply,
    get_recent_messages,
    text_handler,
)

logger = logging.getLogger(__name__)


# ============================================================
# ГОЛОС АЙСЕЛЬ
# ============================================================

TTS_MODEL = "gpt-4o-mini-tts"

# Женский голос
TTS_VOICE = "coral"

# Немного медленнее стандартного — естественнее для русского
TTS_SPEED = 0.96


TTS_INSTRUCTIONS = """
Ты Айсель — взрослая русскоязычная женщина.

Русский язык для тебя родной.

Говори исключительно естественным современным русским языком,
без иностранного акцента и без ощущения, что русский язык
был выучен недавно.

Произношение естественное и уверенное.
Используй нормальные русские ударения.

Голос женственный, тёплый, живой, спокойный и уверенный.
Тембр приятный, естественный, взрослый.
Не делай голос мультяшным.
Не делай его детским.
Не делай мужским.
Не используй чрезмерно высокий тон.

Разговаривай как живая женщина в обычном личном разговоре,
а не как диктор, оператор поддержки или голосовой помощник.

Используй естественный ритм речи.
Делай короткие естественные паузы там, где они нужны.
Не ставь искусственную паузу после каждого слова.

Не произноси каждое слово одинаково.
Используй естественное изменение интонации.
Не заканчивай каждое предложение одинаково.

Не торопись, но и не растягивай слова.

В дружеском разговоре голос может быть слегка улыбчивым.
В серьёзном разговоре говори спокойнее и внимательнее.
В шутках допускай лёгкую иронию.

Не переигрывай эмоции.
Не используй театральную драматичность.
Не используй сексуализированное придыхание.

Ты не читаешь заранее подготовленный текст.
Ты разговариваешь с человеком.

Всегда говори о себе в женском роде.

Ты Айсель.
"""


# ============================================================
# ПОСЛЕДНИЙ ОТВЕТ
# ============================================================

LAST_ASSISTANT_REPLIES = {}


def remember_last_assistant_reply(
    user_id,
    text,
):
    text = (
        text or ""
    ).strip()

    if text:
        LAST_ASSISTANT_REPLIES[
            user_id
        ] = text


def get_last_assistant_reply(
    user_id,
):
    cached = LAST_ASSISTANT_REPLIES.get(
        user_id
    )

    if cached:
        return cached

    try:

        messages = get_recent_messages(
            user_id,
            limit=100,
        )

        for message in reversed(
            messages
        ):

            if message.get(
                "role"
            ) != "assistant":
                continue

            content = (
                message.get(
                    "content"
                )
                or ""
            ).strip()

            if content:

                remember_last_assistant_reply(
                    user_id,
                    content,
                )

                return content

    except Exception:

        logger.exception(
            "Failed to load last assistant reply"
        )

    return None


# ============================================================
# TTS
# ============================================================

def synthesize_speech(
    text,
):
    text = (
        text or ""
    ).strip()

    if not text:
        raise ValueError(
            "Empty text for TTS"
        )

    if len(text) > 4000:
        text = (
            text[:3990]
            + "..."
        )

    fd, path = tempfile.mkstemp(
        suffix=".mp3"
    )

    os.close(fd)

    try:

        response = (
            client.audio.speech.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=text,
                instructions=TTS_INSTRUCTIONS,
                response_format="mp3",
                speed=TTS_SPEED,
            )
        )

        response.stream_to_file(
            path
        )

        return path

    except Exception:

        if os.path.exists(path):
            os.remove(path)

        raise


async def send_voice_reply(
    update,
    text,
):
    path = None

    try:

        path = synthesize_speech(
            text
        )

        with open(
            path,
            "rb",
        ) as audio_file:

            audio = io.BytesIO(
                audio_file.read()
            )

        audio.name = "aisele.mp3"

        await update.message.reply_voice(
            voice=audio
        )

    finally:

        if (
            path
            and os.path.exists(path)
        ):
            os.remove(path)


# ============================================================
# КОМАНДЫ ПОВТОРА
# ============================================================

TEXT_MODE_PATTERNS = (

    r"\bпереведи\s+(?:своё|свой)"
    r"\s+(?:последнее\s+)?голосовое"
    r"\s+в\s+текст\b",

    r"\bсделай\s+(?:свой\s+)?последний"
    r"\s+ответ\s+текстом\b",

    r"\bскажи\s+(?:свой\s+)?последний"
    r"\s+ответ\s+текстом\b",

    r"\bповтори\s+(?:это\s+)?текстом\b",

    r"\bповтори\s+(?:свой\s+)?ответ"
    r"\s+текстом\b",
)


VOICE_MODE_PATTERNS = (

    r"\bозвучь\s+(?:свой\s+)?"
    r"(?:последний\s+)?ответ\b",

    r"\bсделай\s+(?:свой\s+)?последний"
    r"\s+ответ\s+голосом\b",

    r"\bскажи\s+(?:свой\s+)?последний"
    r"\s+ответ\s+голосом\b",

    r"\bповтори\s+(?:это\s+)?голосом\b",

    r"\bповтори\s+(?:свой\s+)?ответ"
    r"\s+голосом\b",

    r"\bответь\s+голосом\b",

    r"\bскажи\s+это\s+голосом\b",
)


def matches(
    text,
    patterns,
):

    text = (
        text or ""
    ).strip().lower()

    return any(
        re.search(
            pattern,
            text,
            re.IGNORECASE,
        )
        for pattern in patterns
    )


async def handle_reply_mode(
    update,
    text,
):

    if not update.effective_user:
        return False

    if not update.message:
        return False

    text = (
        text or ""
    ).strip()

    want_text = matches(
        text,
        TEXT_MODE_PATTERNS,
    )

    want_voice = matches(
        text,
        VOICE_MODE_PATTERNS,
    )

    if not want_text and not want_voice:
        return False

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
    )

    # ВАЖНО:
    # получаем последний ответ ДО сохранения
    # команды "озвучь..." в историю.

    last_reply = get_last_assistant_reply(
        user.id
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

    if not last_reply:

        answer = (
            "У меня ещё нет предыдущего "
            "ответа, который можно повторить."
        )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        remember_last_assistant_reply(
            user.id,
            answer,
        )

        await update.message.reply_text(
            answer
        )

        return True

    if want_text:

        await update.message.reply_text(
            last_reply
        )

        return True

    try:

        await send_voice_reply(
            update,
            last_reply,
        )

    except Exception:

        logger.exception(
            "TTS failed"
        )

        await update.message.reply_text(
            "Не получилось озвучить. "
            "Вот мой последний ответ:\n\n"
            + last_reply
        )

    return True


# ============================================================
# ТЕКСТ
# ============================================================

async def smart_text_handler(
    update,
    context,
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text

    handled = await handle_reply_mode(
        update,
        text,
    )

    if handled:
        return

    await text_handler(
        update,
        context,
    )

    if update.effective_user:

        try:

            last_reply = (
                get_last_assistant_reply(
                    update.effective_user.id
                )
            )

            if last_reply:

                remember_last_assistant_reply(
                    update.effective_user.id,
                    last_reply,
                )

        except Exception:

            logger.exception(
                "Failed to cache text reply"
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
            await telegram_file.download_as_bytearray()
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

        # Сохраняем существующую логику памяти.

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

        remember_last_assistant_reply(
            user.id,
            answer,
        )

        # ГЛАВНОЕ:
        # пользователь говорит -> Айсель отвечает голосом.

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
