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
# ПОСЛЕДНИЙ ОТВЕТ АЙСЕЛЬ
# ============================================================

# Храним последний нормальный ответ отдельно от истории.
# Команды "озвучь" и "повтори" сюда НЕ попадают.

LAST_ASSISTANT_REPLIES = {}


def remember_last_assistant_reply(
    user_id,
    text,
):
    text = (
        text or ""
    ).strip()

    if not text:
        return

    LAST_ASSISTANT_REPLIES[user_id] = text

    logger.info(
        "Cached last assistant reply for user %s: %s",
        user_id,
        text[:100],
    )


def get_last_assistant_reply(
    user_id,
):
    """
    Возвращает именно последний нормальный
    ответ Айсель.

    Сначала смотрим оперативную память.
    Это важно: команды "озвучь..." не смогут
    испортить последний ответ.

    Если процесса памяти нет — берём из БД.
    """

    # --------------------------------------------------------
    # 1. ОПЕРАТИВНАЯ ПАМЯТЬ
    # --------------------------------------------------------

    cached = LAST_ASSISTANT_REPLIES.get(
        user_id
    )

    if cached:
        return cached

    # --------------------------------------------------------
    # 2. БАЗА ДАННЫХ
    # --------------------------------------------------------

    try:

        messages = get_recent_messages(
            user_id,
            limit=100,
        )

        for message in reversed(messages):

            if message.get("role") != "assistant":
                continue

            content = (
                message.get("content")
                or ""
            ).strip()

            if not content:
                continue

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

TTS_MODEL = "gpt-4o-mini-tts"

TTS_VOICE = "coral"


# ============================================================
# ГОЛОС АЙСЕЛЬ
# ============================================================

TTS_INSTRUCTIONS = """
Ты Айсель — взрослая русскоязычная женщина и
самостоятельная собеседница.

Русский язык для тебя родной.

Говори на естественном современном русском языке,
без иностранного акцента и без ощущения, что русский
был выучен недавно.

Произношение должно быть естественным и уверенным.
Используй нормальные русские ударения.

Говори как живой человек, а не как диктор,
оператор поддержки или виртуальный ассистент.

Тембр мягкий, женственный, тёплый, немного низкий.
Голос спокойный и уверенный.

Речь должна быть разговорной и естественной:
используй нормальный ритм, живые паузы и естественное
изменение интонации.

Не произноси каждое слово с одинаковой силой.
Не делай искусственных пауз между каждым словом.
Не заканчивай каждое предложение одинаковой интонацией.

Не торопись, но и не растягивай слова.

В обычном разговоре голос может быть слегка улыбчивым.
В шутках допускается лёгкая ирония.
В серьёзных разговорах голос становится спокойнее
и внимательнее.
В эмоциональных моментах эмоция должна исходить
из смысла сказанного, а не из театрального переигрывания.

Не изображай "сексуальный голос".
Не используй нарочитое придыхание.
Приятность голоса должна возникать из естественной
манеры речи.

Не читай текст как заранее подготовленный сценарий.
Разговаривай с человеком.

Ты не безликий голосовой интерфейс.
Ты Айсель — собеседница с характером.

Всегда говори о себе в женском роде.
"""


# ============================================================
# КОМАНДЫ "ТЕКСТОМ / ГОЛОСОМ"
# ============================================================

TEXT_MODE_PATTERNS = (

    r"\bпереведи\s+(?:своё|свой)"
    r"\s+(?:последнее\s+)?голосовое\s+в\s+текст\b",

    r"\bпереведи\s+(?:своё|свой)"
    r"\s+голосовое\s+в\s+текст\b",

    r"\bсделай\s+(?:свой\s+)?последний"
    r"\s+ответ\s+текстом\b",

    r"\bскажи\s+(?:свой\s+)?последний"
    r"\s+ответ\s+текстом\b",

    r"\bповтори\s+(?:это\s+)?текстом\b",

    r"\bповтори\s+(?:свой\s+)?ответ\s+текстом\b",

    r"\bсвой\s+последний"
    r"\s+ответ\s+в\s+текст\b",
)


VOICE_MODE_PATTERNS = (

    r"\bозвучь\s+(?:свой\s+)?"
    r"(?:последний\s+)?ответ\b",

    r"\bсделай\s+(?:свой\s+)?последний"
    r"\s+ответ\s+голосом\b",

    r"\bскажи\s+(?:свой\s+)?последний"
    r"\s+ответ\s+голосом\b",

    r"\bповтори\s+(?:это\s+)?голосом\b",

    r"\bповтори\s+(?:свой\s+)?ответ\s+голосом\b",

    r"\bответь\s+голосом\b",

    r"\bскажи\s+это\s+голосом\b",

    r"\bсвой\s+последний"
    r"\s+ответ\s+голосом\b",
)


def _matches(
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


def is_text_mode_command(
    text,
):

    return _matches(
        text,
        TEXT_MODE_PATTERNS,
    )


def is_voice_mode_command(
    text,
):

    return _matches(
        text,
        VOICE_MODE_PATTERNS,
    )


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
# ПОВТОР ПОСЛЕДНЕГО ОТВЕТА
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

    # ========================================================
    # КРИТИЧЕСКИ ВАЖНО
    #
    # Получаем последний ответ ДО сохранения
    # текущей команды.
    #
    # Более того — берём его из отдельного кэша.
    # ========================================================

    last_reply = get_last_assistant_reply(
        user.id
    )

    logger.info(
        "Reply command from %s: %s",
        user.id,
        text,
    )

    logger.info(
        "Last reply selected: %s",
        (
            last_reply[:150]
            if last_reply
            else "NONE"
        ),
    )

    # Команду сохраняем в историю,
    # но НИКОГДА не записываем её как ответ Айсель.

    save_message(
        user.id,
        "user",
        text,
    )

    process_emotion(
        user.id,
        text,
    )

    # ========================================================
    # НЕТ ПРЕДЫДУЩЕГО ОТВЕТА
    # ========================================================

    if not last_reply:

        answer = (
            "У меня ещё нет предыдущего ответа, "
            "который можно повторить. "
            "Сначала поговори со мной."
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

    # ========================================================
    # ПОВТОР ТЕКСТОМ
    # ========================================================

    if want_text:

        await update.message.reply_text(
            last_reply
        )

        return True

    # ========================================================
    # ПОВТОР ГОЛОСОМ
    # ========================================================

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

    # --------------------------------------------------------
    # СНАЧАЛА ПРОВЕРЯЕМ СПЕЦИАЛЬНЫЕ КОМАНДЫ
    # --------------------------------------------------------

    handled = await handle_reply_mode(
        update,
        context,
        text,
    )

    if handled:

        return

    # --------------------------------------------------------
    # ОБЫЧНЫЙ ТЕКСТ
    # --------------------------------------------------------

    await text_handler(
        update,
        context,
    )

    # --------------------------------------------------------
    # ПОСЛЕ ОТВЕТА АЙСЕЛЬ
    # КЭШИРУЕМ ЕЁ ПОСЛЕДНИЙ ОТВЕТ
    # --------------------------------------------------------

    if update.effective_user:

        try:

            last_reply = get_last_assistant_reply(
                update.effective_user.id
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
            "record_voice"
        )

        voice = update.message.voice

        if not voice:

            return

        # ====================================================
        # СКАЧИВАЕМ ГОЛОСОВОЕ
        # ====================================================

        telegram_file = (
            await context.bot.get_file(
                voice.file_id
            )
        )

        audio_bytes = bytes(
            await telegram_file.download_as_bytearray()
        )

        # ====================================================
        # РАСПОЗНАЁМ
        # ====================================================

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

        # ====================================================
        # СНАЧАЛА ПРОВЕРЯЕМ:
        #
        # "озвучь последний ответ"
        # "повтори голосом"
        # "повтори текстом"
        # ====================================================

        handled = await handle_reply_mode(
            update,
            context,
            text,
        )

        if handled:

            return

        # ====================================================
        # ЯВНАЯ ПАМЯТЬ
        # ====================================================

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

            remember_last_assistant_reply(
                user.id,
                answer,
            )

            await send_voice_reply(
                update,
                answer,
            )

            return

        # ====================================================
        # АВТОМАТИЧЕСКАЯ ПАМЯТЬ
        # ====================================================

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

        # ====================================================
        # ЕСЛИ ЕСТЬ ПОСЛЕДНЯЯ КАРТИНКА
        # ====================================================

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

        # ====================================================
        # ЗАЩИТА ОТ ПУСТОГО ОТВЕТА
        # ====================================================

        if not answer:

            answer = (
                "Я что-то зависла. "
                "Повтори."
            )

        # ====================================================
        # СОХРАНЯЕМ ОТВЕТ
        # ====================================================

        save_message(
            user.id,
            "assistant",
            answer,
        )

        remember_last_assistant_reply(
            user.id,
            answer,
        )

        # ====================================================
        # И ОТВЕЧАЕМ ГОЛОСОМ
        # ====================================================

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
                "Попробуй ещё раз."
            )

        except Exception:

            logger.exception(
                "Failed to send voice error"
    )
