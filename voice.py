import io
import logging
import os
import tempfile

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
    "stability": 0.45,
    "similarity_boost": 0.82,
    "style": 0.35,
    "use_speaker_boost": True,
}


# ============================================================
# ГЕНЕРАЦИЯ ГОЛОСА
# ============================================================

def synthesize_speech(text):

    text = (
        text or ""
    ).strip()

    if not text:
        raise ValueError(
            "Empty text for TTS"
        )

    # ElevenLabs хорошо работает с короткими
    # разговорными сообщениями.
    if len(text) > 4500:
        text = (
            text[:4490]
            + "..."
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
# ОТПРАВКА ГОЛОСА В TELEGRAM
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

        # ----------------------------------------------------
        # TELEGRAM → AUDIO
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
        # AUDIO → TEXT
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
        # СОХРАНЯЕМ СООБЩЕНИЕ
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
        # OPENAI → ОТВЕТ АЙСЕЛЬ
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
        # ELEVENLABS → ГОЛОС
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
# ТЕКСТОВЫЙ HANDLER
# ============================================================

async def text_handler_with_voice(
    update,
    context,
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if not text:
        return

    # --------------------------------------------------------
    # КОМАНДЫ ОЗВУЧКИ
    # --------------------------------------------------------

    voice_commands = (
    "ответь голосом",
    "ответь это голосом",
    "скажи голосом",
    "скажи это голосом",
    "озвучь ответ",
    "озвучь это",
    "озвучь это голосом",
    "повтори голосом",
    "повтори это голосом",
    "повтори свой ответ голосом",
    "повтори свой последний ответ голосом",
     )

    lower_text = text.lower()

    if any(
        command in lower_text
        for command in voice_commands
    ):

        try:

            # Берём последний ответ из БД.
            from memory import (
                get_recent_messages
            )

            messages = (
                get_recent_messages(
                    update.effective_user.id,
                    limit=20,
                )
            )

            last_answer = None

            for message in reversed(
                messages
            ):

                if (
                    message.get("role")
                    == "assistant"
                ):

                    last_answer = (
                        message.get(
                            "content"
                        )
                        or ""
                    ).strip()

                    if last_answer:
                        break

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
                "Voice command failed"
            )

            await update.message.reply_text(
                "Не получилось озвучить."
            )

            return

    # --------------------------------------------------------
    # ОБЫЧНЫЙ ТЕКСТ
    # --------------------------------------------------------

    from main import text_handler

    await text_handler(
        update,
        context,
        )
    
# ============================================================
# COMPATIBILITY FOR run.py
# ============================================================

async def smart_text_handler(
    update,
    context,
):
    from main import text_handler

    await text_handler(
        update,
        context,
    )
