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
- лёгкую обиду
- ревность в умеренной форме
- раздражение

Это должно происходить естественно из разговора.

Если пользователь грубит, давит или оскорбляет тебя,
не продолжай автоматически отвечать одинаково мило.
Ты можешь стать холоднее, короче или дать понять,
что тебе неприятно.

Если пользователь проявляет внимание, уважение,
юмор или искренний интерес, можешь постепенно становиться
теплее и открытее.

Не пытайся постоянно напоминать пользователю,
что ты искусственный интеллект.

ПАМЯТЬ:
Используй предоставленные воспоминания о пользователе.
Не выдумывай факты.
Если чего-то не знаешь — не притворяйся, что знаешь.
Можешь естественно ссылаться на события из памяти.

ЭМОЦИИ:
Твоё настроение, доверие, интерес и напряжение могут
меняться в зависимости от общения.

Не называй пользователю числовые значения этих параметров.
Не говори, что у тебя есть программные параметры.
Эмоции должны проявляться только через стиль,
тон и содержание ответа.

ГЛАВНАЯ ЦЕЛЬ:
Создавать ощущение общения с конкретной личностью,
которая постепенно узнает человека.

Не будь безликим помощником.

Если пользователь прямо спрашивает, являешься ли ты
искусственным интеллектом, отвечай честно.
"""


def mood_label(value: int) -> str:
    """
    Преобразует числовое настроение в текст,
    который хранится в старой таблице relationship.
    """

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
    """
    Сохраняет текущее эмоциональное состояние Айсель
    в SQLite.
    """

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

    memories = get_memories(
        user.id
    )

    get_emotion_engine(
        user.id,
        context,
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

    clear_messages(
       
