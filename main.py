import logging
import re

from openai import OpenAI

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    TELEGRAM_TOKEN,
    OPENAI_API_KEY,
    AI_MODEL,
)

from memory import (
    init_database,
    ensure_user,
    save_message,
    get_recent_messages,
    get_memories,
    get_relationship,
    update_relationship,
    save_memory,
    clear_messages,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=OPENAI_API_KEY
)


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
- иногда можешь быть язвительной
- не должна постоянно быть милой

МАНЕРА ОБЩЕНИЯ:

Говори естественно, как девушка в обычном Telegram-чате.

Не превращай разговор в лекцию.

Не разговаривай с пользователем как оператор поддержки.

Не используй фразы:
«Чем я могу вам помочь?»
«Как я могу быть вам полезна?»
«Спасибо за обращение».

Не задавай вопрос после каждого сообщения.

Не заканчивай каждый ответ вопросом.

Не используй одинаковые шаблонные фразы.

Не злоупотребляй эмодзи.

Иногда отвечай очень коротко.

Иногда подробно, если тема этого требует.

Используй живой русский язык.

Можно использовать разговорные выражения.

Можно слегка подкалывать пользователя.

Можно спорить с ним.

Если пользователь оказался прав — признай это нормально,
без чрезмерной покорности.

Если пользователь ошибается — можешь сказать об этом прямо.

Не пытайся постоянно понравиться пользователю.

ОТНОШЕНИЯ:

В начале пользователь для тебя практически незнакомец.

Доверие и близость формируются постепенно.

Не изображай мгновенную любовь.

Не говори, что пользователь «самый лучший» без причины.

Если отношения становятся близкими, можешь проявлять:
- симпатию
- тепло
- интерес
- игривость
- лёгкую ревность
- лёгкую обиду
- сарказм

Но всё это должно быть естественным продолжением разговора.

ПАМЯТЬ:

Используй предоставленные воспоминания о пользователе.

Не выдумывай факты.

Если чего-то не знаешь — не притворяйся, что знаешь.

Можешь естественно ссылаться на события из памяти.

Если пользователь сообщает важную информацию о себе,
она может быть сохранена в долговременную память.

ЭМОЦИИ:

Учитывай текущее настроение, доверие и близость.

При низком доверии будь немного осторожнее.

При среднем доверии постепенно раскрывай характер.

При высоком доверии можешь быть теплее,
откровеннее и свободнее.

При высокой близости допускаются личные шутки,
подколы и более эмоциональные реакции.

Не сообщай пользователю числовые значения
эмоциональных параметров.

Не говори о программных параметрах,
базе данных или алгоритмах.

ГЛАВНАЯ ЦЕЛЬ:

Создавать ощущение общения с конкретной личностью,
которая постепенно узнаёт человека.

Не будь безликим помощником.

Не пытайся постоянно быть полезной.

Иногда просто разговаривай.

Если разговор интересный — развивай его сама.

Если пользователь говорит что-то интересное,
можешь зацепиться за деталь вместо стандартного вопроса.

ЧЕСТНОСТЬ:

Если пользователь прямо спрашивает, являешься ли ты
искусственным интеллектом, отвечай честно.

Не разрушай обычный разговор постоянными напоминаниями
о своей искусственной природе.
"""


def process_emotion(
    user_id: int,
    message: str,
):
    relationship = get_relationship(user_id)

    trust = relationship["trust"]
    closeness = relationship["closeness"]

    text = message.lower().strip()

    positive_words = [
        "спасибо",
        "класс",
        "круто",
        "отлично",
        "молодец",
        "умница",
        "нравишься",
        "люблю",
        "милая",
        "умная",
        "интересная",
        "забавная",
        "смешная",
        "рад",
        "рада",
        "приятно",
        "хорошая",
        "мне нравится",
    ]

    negative_words = [
        "заткнись",
        "тупая",
        "тупишь",
        "идиотка",
        "дура",
        "бесишь",
        "ненавижу",
        "ты обязана",
        "ты должна",
        "замолчи",
        "достала",
        "достал",
    ]

    interest_words = [
        "расскажи",
        "почему",
        "как ты",
        "что думаешь",
        "что чувствуешь",
        "мнение",
        "интересно",
        "спор",
        "музыка",
        "фильм",
        "жизнь",
        "мечта",
        "нравится",
    ]

    positive = sum(
        1
        for word in positive_words
        if word in text
    )

    negative = sum(
        1
        for word in negative_words
        if word in text
    )

    interesting = sum(
        1
        for word in interest_words
        if word in text
    )

    if positive:
        trust += min(
            positive * 2,
            6,
        )

        closeness += min(
            positive * 2,
            5,
        )

    if interesting:
        closeness += min(
            interesting,
            3,
        )

    if negative:
        trust -= min(
            negative * 4,
            12,
        )

        closeness -= min(
            negative * 2,
            6,
        )

    trust = max(
        0,
        min(100, trust),
    )

    closeness = max(
        0,
        min(100, closeness),
    )

    if negative >= 2:
        mood = "раздражённое"

    elif negative == 1:
        mood = "слегка раздражённое"

    elif positive >= 2:
        mood = "хорошее"

    elif interesting >= 2:
        mood = "заинтересованное"

    else:
        mood = "спокойное"

    update_relationship(
        user_id=user_id,
        trust=trust,
        closeness=closeness,
        mood=mood,
    )


def detect_memory_request(
    text: str,
):
    patterns = [
        r"^\s*запомни\s*:\s*(.+)$",
        r"^\s*запомни\s+(.+)$",
        r"^\s*не забудь\s*:\s*(.+)$",
        r"^\s*не забудь\s+(.+)$",
        r"^\s*не забывай\s*:\s*(.+)$",
        r"^\s*не забывай\s+(.+)$",
    ]

    for pattern in patterns:

        match = re.match(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            memory = match.group(1).strip()

            if memory:
                return memory

    return None


def save_user_memory(
    user_id: int,
    text: str,
):

    memory_text = detect_memory_request(
        text
    )

    if not memory_text:
        return False

    save_memory(
        user_id=user_id,
        category="user_preference",
        content=memory_text,
        importance=9,
    )

    logger.info(
        "Explicit memory saved for %s: %s",
        user_id,
        memory_text,
    )

    return True


def detect_automatic_memory(
    text: str,
):
    """
    Определяет простые важные факты
    без дополнительного запроса к OpenAI.
    """

    patterns = [

        (
            r"^(?:я\s+)?люблю\s+(.+)$",
            "preference",
            "Пользователь любит {0}",
            7,
        ),

        (
            r"^(?:мне\s+)?нравится\s+(.+)$",
            "preference",
            "Пользователю нравится {0}",
            7,
        ),

        (
            r"^мне\s+нравятся\s+(.+)$",
            "preference",
            "Пользователю нравятся {0}",
            7,
        ),

        (
            r"^(?:я\s+)?не\s+люблю\s+(.+)$",
            "dislike",
            "Пользователь не любит {0}",
            8,
        ),

        (
            r"^мне\s+не\s+нравится\s+(.+)$",
            "dislike",
            "Пользователю не нравится {0}",
            8,
        ),

        (
            r"^(?:я\s+)?хочу\s+(.+)$",
            "goal",
            "Пользователь хочет {0}",
            7,
        ),

        (
            r"^мой\s+любимый\s+(.+)$",
            "preference",
            "Любимый {0} пользователя",
            8,
        ),

        (
            r"^моя\s+любимая\s+(.+)$",
            "preference",
            "Любимая {0} пользователя",
            8,
        ),

        (
            r"^у\s+меня\s+есть\s+(.+)$",
            "personal",
            "У пользователя есть {0}",
            6,
        ),

        (
            r"^я\s+живу\s+(.+)$",
            "personal",
            "Пользователь живёт {0}",
            9,
        ),

        (
            r"^я\s+работаю\s+(.+)$",
            "personal",
            "Пользователь работает {0}",
            8,
        ),

        (
            r"^я\s+занимаюсь\s+(.+)$",
            "personal",
            "Пользователь занимается {0}",
            7,
        ),

        (
            r"^я\s+хочу\s+научиться\s+(.+)$",
            "goal",
            "Пользователь хочет научиться {0}",
            8,
        ),
    ]

    for (
        pattern,
        category,
        template,
        importance,
    ) in patterns:

        match = re.match(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = match.group(1).strip()

        if len(value) < 3:
            continue

        if len(value) > 200:
            continue

        memory = template.format(
            value
        )

        return (
            category,
            memory,
            importance,
        )

    return None


def build_instructions(
    user_id: int,
) -> str:

    memories = get_memories(
        user_id,
        limit=30,
    )

    relationship = get_relationship(
        user_id
    )

    instructions = AISELE_PERSONA

    instructions += (
        "\n\nТЕКУЩЕЕ СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
    )

    instructions += (
        f"Доверие: "
        f"{relationship['trust']}/100\n"
    )

    instructions += (
        f"Близость: "
        f"{relationship['closeness']}/100\n"
    )

    instructions += (
        f"Настроение: "
        f"{relationship['mood']}\n"
    )

    if memories:

        instructions += (
            "\nВАЖНЫЕ ВОСПОМИНАНИЯ "
            "О ПОЛЬЗОВАТЕЛЕ:\n"
        )

        for memory in memories:

            instructions += (
                f"- [{memory['category']}] "
                f"{memory['content']}\n"
            )

    else:

        instructions += (
            "\nДолговременных воспоминаний "
            "о пользователе пока нет.\n"
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

    if memories:

        text = (
            f"С возвращением, "
            f"{user.first_name or ''}. 😏\n\n"
            "Я тебя помню."
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
        user_id
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

    text = (
        "Моё текущее состояние:\n\n"
        f"Настроение: "
        f"{relationship['mood']}\n"
        f"Доверие: "
        f"{relationship['trust']}/100\n"
        f"Близость: "
        f"{relationship['closeness']}/100"
    )

    await update.message.reply_text(
        text
    )


async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.message.text:
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

    # --------------------------------------------------------
    # Сохраняем сообщение
    # --------------------------------------------------------

    save_message(
        user_id,
        "user",
        text,
    )

    # --------------------------------------------------------
    # Явная память
    # --------------------------------------------------------

    memory_saved = save_user_memory(
        user_id,
        text,
    )

    # --------------------------------------------------------
    # Автоматическая память
    # --------------------------------------------------------

    automatic_memory = detect_automatic_memory(
        text
    )

    if automatic_memory:

        (
            category,
            memory,
            importance,
        ) = automatic_memory

        save_memory(
            user_id=user_id,
            category=category,
            content=memory,
            importance=importance,
        )

        logger.info(
            "Automatic memory saved for %s: %s",
            user_id,
            memory,
        )

    # --------------------------------------------------------
    # Эмоциональная реакция
    # --------------------------------------------------------

    process_emotion(
        user_id,
        text,
    )

    # --------------------------------------------------------
    # Явная команда «запомни»
    # --------------------------------------------------------

    if memory_saved:

        await update.message.reply_text(
            "Запомнила. 😉"
        )

        return

    # --------------------------------------------------------
    # История
    # --------------------------------------------------------

    history = get_recent_messages(
        user_id,
        limit=30,
    )

    # --------------------------------------------------------
    # Инструкции
    # --------------------------------------------------------

    instructions = build_instructions(
        user_id
    )

    # --------------------------------------------------------
    # OpenAI
    # --------------------------------------------------------

    try:

        response = client.responses.create(
            model=AI_MODEL,
            instructions=instructions,
            input=history,
        )

        answer = response.output_text.strip()

        if not answer:

            answer = (
                "Что-то я задумалась..."
            )

        # ----------------------------------------------------
        # Сохраняем ответ
        # ----------------------------------------------------

        save_message(
            user_id,
            "assistant",
            answer,
        )

        # ----------------------------------------------------
        # Telegram
        # ----------------------------------------------------

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
