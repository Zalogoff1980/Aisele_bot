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
    update_relationship,
    clear_messages,
)

from emotion_engine import EmotionEngine


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

Если отношения становятся близкими, можешь проявлять:
- симпатию
- тепло
- интерес
- игривость
- легкую обиду
- раздражение

Это должно происходить естественно из разговора.

Если пользователь грубит, давит или оскорбляет тебя,
не продолжай автоматически отвечать одинаково мило.
Ты можешь стать холоднее, короче или дать понять,
что тебе неприятно.

Если пользователь проявляет внимание, уважение,
юмор или искренний интерес, можешь постепенно становиться
теплее и открытее.

Не напоминай постоянно, что ты искусственный интеллект.

ПАМЯТЬ:
Используй предоставленные воспоминания о пользователе.
Не выдумывай факты.
Если чего-то не знаешь — не притворяйся, что знаешь.
Можешь естественно ссылаться на события из памяти.

ЭМОЦИИ:
Твое настроение, доверие, интерес и напряжение могут
меняться в зависимости от общения.

Не называй пользователю числовые значения этих параметров.
Не говори, что у тебя есть программные параметры.
Эмоциональное состояние должно проявляться только
через стиль, тон и содержание ответа.

ГЛАВНАЯ ЦЕЛЬ:
Создавать ощущение общения с конкретной личностью,
которая постепенно узнает человека.

Не будь безликим помощником.

Если пользователь прямо спрашивает, являешься ли ты
искусственным интеллектом, отвечай честно.
"""


def mood_label(value: int) -> str:
    if value >= 80:
        return "отличное"

    if value >= 65:
        return "хорошее"

    if value >= 45:
        return "спокойное"

    if value >= 25:
        return "подавленное"

    return "плохое"


def get_emotion_engine(
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> EmotionEngine:

    engines = context.application.bot_data.setdefault(
        "emotion_engines",
        {},
    )

    if user_id not in engines:

        relationship = get_relationship(user_id)

        initial_state = {
            "mood": relationship.get(
                "mood",
                50,
            ),
            "trust": relationship.get(
                "trust",
                20,
            ),
            "interest": relationship.get(
                "closeness",
                30,
            ),
            "tension": 0,
        }

        engines[user_id] = EmotionEngine(
            initial_state
        )

    return engines[user_id]


def persist_emotion(
    user_id: int,
    emotion_engine: EmotionEngine,
) -> None:

    state = emotion_engine.state

    state.clamp()

    update_relationship(
        user_id,
        trust=state.trust,
        closeness=state.interest,
        mood=mood_label(state.mood),
    )


def build_instructions(
    user_id: int,
    emotion_engine: EmotionEngine,
) -> str:

    memories = get_memories(
        user_id,
        limit=20,
    )

    relationship = get_relationship(
        user_id
    )

    instructions = AISELE_PERSONA

    instructions += (
        "\n\nТЕКУЩЕЕ СОСТОЯНИЕ ОТНОШЕНИЙ:"
    )

    instructions += (
        f"\nДоверие: "
        f"{relationship.get('trust', 20)}/100"
    )

    instructions += (
        f"\nБлизость: "
        f"{relationship.get('closeness', 30)}/100"
    )

    instructions += (
        "\n\nЭМОЦИОНАЛЬНОЕ СОСТОЯНИЕ:"
    )

    instructions += (
        "\n" + emotion_engine.personality_hint()
    )

    if memories:

        instructions += (
            "\n\nВАЖНЫЕ ВОСПОМИНАНИЯ:"
        )

        for memory in memories:

            instructions += (
                f"\n- [{memory['category']}] "
                f"{memory['content']}"
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

    get_emotion_engine(
        user.id,
        context,
    )

    memories = get_memories(
        user.id
    )

    if memories:

        text = (
            f"С возвращением, "
            f"{user.first_name or ''}.\n\n"
            "Я тебя помню. 😏"
        )

    else:

        text = (
            f"Привет, "
            f"{user.first_name or 'незнакомец'}.\n\n"
            "Я Айсель. 🌙\n"
            "Ну что... познакомимся?"
        )

    await update.message.reply_text(
        text
    )


async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.first_name,
    )

    # Очищаем только историю текущего разговора.
    clear_messages(user_id)

    # Создаем новое эмоциональное состояние.
    engines = context.application.bot_data.setdefault(
        "emotion_engines",
        {},
    )

    engines[user_id] = EmotionEngine()

    # Сохраняем начальное состояние.
    persist_emotion(
        user_id,
        engines[user_id],
    )

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

    memories = get_memories(
        user_id
    )

    if not memories:

        await update.message.reply_text(
            "Пока я ничего важного "
            "о тебе не запомнила."
        )

        return

    lines = [
        "Вот что я о тебе помню:\n"
    ]

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

    relationship = get_relationship(
        user_id
    )

    emotion_engine = get_emotion_engine(
        user_id,
        context,
    )

    state = emotion_engine.state

    text = (
        "Мое текущее состояние:\n\n"
        f"Настроение: {state.mood}/100\n"
        f"Доверие: {state.trust}/100\n"
        f"Интерес: {state.interest}/100\n"
        f"Напряжение: {state.tension}/100\n\n"
        f"Близость: "
        f"{relationship.get('closeness', 30)}/100"
    )

    await update.message.reply_text(
        text
    )


async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if (
        not update.message
        or not update.message.text
    ):
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

    # Получаем эмоциональный движок.
    emotion_engine = get_emotion_engine(
        user_id,
        context,
    )

    # Обрабатываем новое сообщение.
    emotion_engine.process_message(
        text
    )

    # Сохраняем изменившееся состояние.
    persist_emotion(
        user_id,
        emotion_engine,
    )

    # Сохраняем сообщение пользователя.
    save_message(
        user_id,
        "user",
        text,
    )

    # Получаем последние сообщения.
    history = get_recent_messages(
        user_id,
        limit=20,
    )

    # Формируем инструкции для Айсель.
    instructions = build_instructions(
        user_id,
        emotion_engine,
    )

    try:

        response = client.responses.create(
            model=AI_MODEL,
            instructions=instructions,
            input=history,
        )

        answer = (
            response.output_text.strip()
        )

        if not answer:

            answer = (
                "Что-то я задумалась..."
            )

        # Сохраняем ответ Айсель.
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
            "Кажется, мои мозги сейчас "
            "немного зависли 😅"
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
