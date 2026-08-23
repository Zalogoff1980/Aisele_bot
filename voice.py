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
    save_user_memory,
    save_automatic_memories,
    transcribe_voice,
    generate_text_reply,
    generate_image_reply,
    get_visual_context,
    get_recent_messages,
    text_handler,
)


logger = logging.getLogger(__name__)


# ============================================================
# TTS
# ============================================================

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "coral"

TTS_INSTRUCTIONS = (
    "Говори по-русски естественно и тепло. "
    "Ты Айсель — взрослая женщина с самостоятельным характером. "
    "Голос живой, спокойный, уверенный, немного игривый. "
    "Не читай текст как диктор или оператор поддержки. "
    "Используй естественные паузы и интонацию обычного личного разговора. "
    "Всегда говори о себе в женском роде."
)


# ============================================================
# КОМАНДЫ ДЛЯ ПОСЛЕДНЕГО ОТВЕТА
# ============================================================

TEXT_MODE_PATTERNS = (
    r"\bпереведи\s+(?:своё|свой)\s+(?:последнее\s+)?голосовое\s+в\s+текст\b",
    r"\bпереведи\s+(?:своё|свой)\s+голосовое\s+в\s+текст\b",
    r"\bсделай\s+(?:свой\s+)?последний\s+ответ\s+текстом\b",
    r"\bскажи\s+(?:свой\s+)?последний\s+ответ\s+текстом\b",
    r"\bповтори\s+(?:это\s+)?текстом\b",
    r"\bповтори\s+(?:свой\s+)?ответ\s+текстом\b",
    r"\bсвой\s+последний\s+ответ\s+в\s+текст\b",
)


VOICE_MODE_PATTERNS = (
    r"\bозвучь\s+(?:свой\s+)?(?:последний\s+)?ответ\b",
    r"\bсделай\s+(?:свой\s+)?последний\s+ответ\s+голосом\b",
    r"\bскажи\s+(?:свой\s+)?последний\s+ответ\s+голосом\b",
    r"\bповтори\s+(?:это\s+)?голосом\b",
    r"\bповтори\s+(?:свой\s+)?ответ\s+голосом\b",
    r"\bответь\s+голосом\b",
    r"\bскажи\s+это\s+голосом\b",
    r"\bсвой\s+последний\s+ответ\s+голосом\b",
)


def _matches(text, patterns):

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


def is_text_mode_command(text):

    return _matches(
        text,
        TEXT_MODE_PATTERNS,
    )


def is_voice_mode_command(text):

    return _matches(
        text,
        VOICE_MODE_PATTERNS,
    )


# ============================================================
# ПОСЛЕДНИЙ ОТВЕТ АЙСЕЛЬ
# ============================================================

def get_last_assistant_reply(user_id):

    messages = get_recent_messages(
        user_id,
        limit=50,
    )

    for message in reversed(messages):

        if message.get("role") != "assistant":
            continue

        content = (
            message.get("content")
            or ""
        ).strip()

        if content:
            return content

    return None


# ============================================================
# ОЗВУЧИВАНИЕ
# ============================================================

def synthesize_speech(text):

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

    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        instructions=TTS_INSTRUCTIONS,
        response_format="mp3",
    )

    response.stream_to_file(
        path
    )

    return path


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

            voice = io.BytesIO(
                audio_file.read()
            )

        voice.name = "aisele.mp3"

        await update.message.reply_voice(
            voice=voice
        )

    finally:

        if (
            path
            and os.path.exists(path)
        ):

            os.remove(path)


# ============================================================
# ОБРАБОТКА «ПОВТОРИ / ОЗВУЧЬ / ТЕКСТОМ»
# ============================================================

async def handle_reply_mode(
    update,
    context,
    text,
):

    if not update.effective_user:
        return False

    if not update.message:
        return False

    text = (
        text or ""
    ).strip()

    if not text:
        return False

    want_text = is_text_mode_command(
        text
    )

    want_voice = is_voice_mode_command(
        text
    )

    if not want_text and not want_voice:
        return False

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
    )

    # Получаем последний ответ ДО того,
    # как записываем текущую команду.
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
            "У меня пока нет предыдущего "
            "ответа, который можно повторить."
        )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        await update.message.reply_text(
            answer
        )

        return True

    # --------------------------------------------------------
    # ПОВТОР ТЕКСТОМ
    # --------------------------------------------------------

    if want_text:

        await update.message.reply_text(
            last_reply
        )

        return True

    # --------------------------------------------------------
    # ПОВТОР ГОЛОСОМ
    # --------------------------------------------------------

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
# УМНЫЙ ТЕКСТОВЫЙ HANDLER
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
        context,
        text,
    )

    if handled:
        return

    await text_handler(
        update,
        context,
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
            "record_voice"
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
                "Не расслышала. "
                "Скажи ещё раз, ладно?"
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

        # Сначала проверяем:
        # «повтори голосом»,
        # «повтори текстом»,
        # «озвучь свой последний ответ» и т.д.

        handled = await handle_reply_mode(
            update,
            context,
            text,
        )

        if handled:
            return

        # ----------------------------------------------------
        # ЯВНАЯ ПАМЯТЬ
        # ----------------------------------------------------

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

            answer = (
                "Запомнила. 😉"
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

            return

        # ----------------------------------------------------
        # АВТОМАТИЧЕСКАЯ ПАМЯТЬ
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ПОСЛЕДНЯЯ КАРТИНКА
        # ----------------------------------------------------

        visual = get_visual_context(
            user.id
        )

        if visual:

            try:

                telegram_image = (
                    await context.bot.get_file(
                        visual[
                            "telegram_file_id"
                        ]
                    )
                )

                image_bytes = bytes(
                    await telegram_image.download_as_bytearray()
                )

                answer = generate_image_reply(
                    user.id,
                    image_bytes,
                    text,
                )

            except Exception:

                logger.exception(
                    "Visual context failed"
                )

                answer = generate_text_reply(
                    user.id,
                    text,
                )

        else:

            answer = generate_text_reply(
                user.id,
                text,
            )

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
        # ОТВЕТ ГОЛОСОМ
        # ----------------------------------------------------

        await send_voice_reply(
            update,
            answer,
        )

    except Exception:

        logger.exception(
            "Voice reply failed"
        )

        try:

            await update.message.reply_text(
                "С голосом что-то пошло не так. "
                "Сейчас починю."
            )

        except Exception:

            logger.exception(
                "Failed to send voice error"
    )
