import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN

from main import (
    init_database,
    init_visual_context,
    start_command,
    memory_command,
    clear_command,
    text_handler,
    photo_handler,
)

from voice import voice_handler


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)


def main():

    init_database()

    init_visual_context()

    application = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "memory",
            memory_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "clear",
            clear_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler,
        )
    )

    # ==========================================
    # ГОЛОСОВЫЕ СООБЩЕНИЯ
    # Используем новый voice.py
    # ==========================================

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            voice_handler,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    logging.info(
        "Aisele started"
    )

    application.run_polling(
        drop_pending_updates=False
    )


if __name__ == "__main__":
    main()
