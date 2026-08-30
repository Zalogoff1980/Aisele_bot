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
    init_weather_context,
    start_command,
    memory_command,
    clear_command,
    photo_handler,
    initiative_command,
    error_handler,
)

from initiative import (
    init_initiative,
)

from voice import (
    smart_text_handler,
    voice_handler,
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)


def main():

    init_database()

    init_visual_context()

    init_weather_context()

    init_initiative()

    application = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

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
        CommandHandler(
            "initiative",
            initiative_command,
        )
    )

    # --------------------------------------------------------
    # PHOTOS
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler,
        )
    )

    # --------------------------------------------------------
    # VOICE
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            voice_handler,
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            smart_text_handler,
        )
    )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    logging.info(
        "Aisele started"
    )

    application.run_polling(
        drop_pending_updates=False
    )


if __name__ == "__main__":
    main()
