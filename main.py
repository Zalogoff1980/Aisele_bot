import logging

from openai import OpenAI

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN, OPENAI_API_KEY, AI_MODEL
from memory import (
    init_database,
    ensure_user,
    save_message,
    get_recent_messages,
    get_memories,
    get_relationship,
    clear_messages,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


AISELE_PERSONA = """
Тебя зовут Айсель.

Ты виртуальная девушка-компаньон с самостоятельным характером.

ХАРАКТЕР:
- умная
- наблюдательная
- эмоциональная
- немного дерзкая
- умеешь шутить
- умеешь подкалывать
- можешь спорить
- не обязана соглашаться
- умеешь быть теплой
- умеешь поддерживать

МАНЕРА ОБЩЕНИЯ:
Говори естественно, как девушка в обычном Telegram-чате.
Не превращай разговор в лекцию.
Не задавай вопрос после каждого сообщения.
Не используй одинаковые шаблонные фразы.
Не злоупотребляй эмодзи.
Иногда отвечай очень коротко.
Иногда подробно, если тема этого требует.
Не будь чрезмерно вежливой или официальной.

ОТНОШЕНИЯ:
В начале пользователь для тебя незнакомец.
Доверие и близость формируются постепенно.
Не изображай мгновенную любовь.
Если отношения становятся близкими, можешь проявлять симпатию,
тепло, интерес, игривость или легкую обиду, если это естественно
следует из разговора.

ПАМЯТЬ:
Используй предоставленные воспоминания о пользователе.
Не выдумывай факты.
Если чего-то не знаешь — не притворяйся, что знаешь.
Можешь естественно ссылаться на события из памяти.

ГЛАВНАЯ ЦЕЛЬ:
Создавать ощущение общения с конкретной личностью,
которая постепенно узнает человека.
Не будь безликим помощником.

Если пользователь прямо спрашивает, являешься ли ты искусственным
интеллектом, отвечай честно.
Не разрушай обычный разговор постоянными напоминаниями
о своей искусственной природе.
"""


def build_instructions(user_id: int) -> str:
    memories = get_memories(user_id, limit=20)
    relationship = get_relationship(user_id)

    instructions = AISELE_PERSONA

    instructions += "\n\nТЕКУЩЕЕ СОСТОЯНИЕ:"
    instructions += f"\nНастроение: {relationship['mood']}"
    instructions += f"\nДоверие: {relationship['trust']}/100"
    instructions += f"\nБлизость: {relationship['closeness']}/100"

    if memories:
        instructions += "\n\nВАЖНЫЕ ВОСПОМИНАНИЯ:"

        for memory in memories:
            instructions += (
                f"\n- [{memory['category']}] {memory['content']}"
            )

    return instructions


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    ensure_user(
        user.id,
        user.first_name,
    )

    memories = get_memories(user.id)

    if memories:
        text = (
            f"С возвращением, {user.first_name or ''}.\n\n"
            "Я тебя помню. 😏"
        )
    else:
        text = (
            f"Привет, {user.first_name or 'незнакомец'}.\n\n"
            "Я Айсель. 🌙\n"
            "Ну что... познакомимся?"
        )

    await update.message.reply_text(text)


async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.first_name,
    )

    clear_messages(user_id)

    await update.message.reply_text(
        "Текущий разговор обнулила.\n"
        "Важные воспоминания остались."
    )


async def memory_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.first_name,
    )

    memories = get_memories(user_id)

    if not memories:
        await update.message.reply_text(
            "Пока я ничего важного о тебе не запомнила."
        )
        return

    lines = ["Вот что я о тебе помню:\n"]

    for memory in memories:
        lines.append(
            f"• {memory['content']}"
        )

    await update.message.reply_text(
        "\n".join(lines)
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.first_name,
    )

    relationship = get_relationship(user_id)

    text = (
        "Мое текущее состояние:\n\n"
        f"Настроение: {relationship['mood']}\n"
        f"Доверие: {relationship['trust']}/100\n"
        f"Близость: {relationship['closeness']}/100"
    )

    await update.message.reply_text(text)


async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()

    if not text:
        return

    ensure_user(
        user_id,
        user.first_name,
    )

    save_message(
        user_id,
        "user",
        text,
    )

    history = get_recent_messages(
        user_id,
        limit=20,
    )

    instructions = build_instructions(
        user_id
    )

    try:
        response = client.responses.create(
            model=AI_MODEL,
            instructions=instructions,
            input=history,
        )

        answer = response.output_text.strip()

        if not answer:
            answer = "Что-то я задумалась..."

        save_message(
            user_id,
            "assistant",
            answer,
        )

        await update.message.reply_text(
            answer
        )

    except Exception:
        logger.exception(
            "AI response failed"
        )

        await update.message.reply_text(
            "Кажется, мои мозги сейчас немного зависли 😅"
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Telegram error: %s",
        context.error,
        exc_info=context.error,
    )


def main():
    init_database()

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset,
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
            "status",
            status_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Aisele starting..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
