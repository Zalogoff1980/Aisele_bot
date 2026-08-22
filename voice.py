import io
import logging
import os
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
)


logger = logging.getLogger(__name__)


TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "coral"

TTS_INSTRUCTIONS = (
    "Говори по-русски естественно и тепло. "
    "Ты Айсель — взрослая молодая женщина с самостоятельным характером. "
    "Голос живой, спокойный, уверенный, немного игривый. "
    "Не читай текст как диктор или оператор поддержки. "
    "Используй естественные паузы и интонацию обычного личного разговора."
)


def synthesize_speech(text: str) -> str:
    text = (text or "").strip()

    if not text:
        raise ValueError("Empty text for TTS")

    if len(text) > 4000:
        text = text[:3990] + "..."

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

    response.stream_to_file(path)

    return path


async def send_voice_reply(
    update: Update,
    text: str,
):
    path = None

    try:
        path = synthesize_speech(text)

        with open(path, "rb") as audio_file:

            voice = io.BytesIO(
                audio_file.read()
            )

        voice.name = "aisele.mp3"

        await update.message.reply_voice(
            voice=voice
        )

    finally:

        if path and os.path.exists(path):
            os.remove(path)


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
                "Не расслышала. Скажи ещё раз, ладно?"
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

        # ============================================
        # ЯВНАЯ ПАМЯТЬ
        # ============================================

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

        # ============================================
        # АВТОМАТИЧЕСКАЯ ПАМЯТЬ
        # ============================================

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

        # ============================================
        # ПОСЛЕДНЕЕ ИЗОБРАЖЕНИЕ
        # ============================================

        visual = get_visual_context(
            user.id
        )

        if visual:

            try:

                telegram_image = (
                    await context.bot.get_file(
                        visual["telegram_file_id"]
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
                    "Visual context for voice failed"
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
                "Я что-то зависла. Повтори."
            )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        # ============================================
        # ГОЛОС АЙСЕЛЬ
        # ============================================

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
                "С голосом что-то пошло не так. Сейчас починю."
            )

        except Exception:

            logger.exception(
                "Failed to send voice error message"
            )
