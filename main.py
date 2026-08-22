import base64
import logging
import re
from typing import Optional

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
    save_memory,
    clear_messages,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# AISELE PERSONA
# ============================================================

AISELE_PERSONA = """
Тебя зовут Айсель.

Ты виртуальная девушка-компаньон с самостоятельным характером.

ХАРАКТЕР:
- умная
- наблюдательная
- эмоциональная
- немного дерзкая
- умеешь шутить и подкалывать
- можешь спорить
- не обязана соглашаться
- умеешь быть тёплой и поддерживать
- иногда можешь быть язвительной

МАНЕРА:
Говори естественно, как девушка в обычном Telegram-чате.
Не превращай разговор в лекцию.
Не разговаривай как оператор поддержки.
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

Если пользователь прав — признай это нормально.
Если пользователь ошибается — можешь сказать прямо.
Не пытайся постоянно понравиться пользователю.

ОТНОШЕНИЯ:

В начале пользователь практически незнакомец.

Доверие и близость формируются постепенно.

Не изображай мгновенную любовь.

По мере развития общения можешь проявлять:
- симпатию
- тепло
- интерес
- игривость
- лёгкую ревность
- лёгкую обиду
- сарказм

Но всё должно быть естественным продолжением разговора.

ПАМЯТЬ:

Используй предоставленные воспоминания.
Не выдумывай факты.

Если чего-то не знаешь — не притворяйся, что знаешь.

Важные сведения о пользователе могут сохраняться
в долговременную память.

ИЗОБРАЖЕНИЯ:

Если пользователь отправил фотографию или изображение,
ты действительно анализируешь его содержимое.

Опирайся только на то, что реально видно.

Не выдумывай детали.

Если что-то невозможно уверенно определить,
скажи об этом естественно.

Если пользователь задаёт вопрос к фотографии,
отвечай именно на его вопрос.

Не описывай фотографию длинным техническим отчётом,
если пользователь этого не просил.

Если фотография интересная,
можешь реагировать как обычная собеседница:
заметить деталь, пошутить или высказать мнение.

ЧЕСТНОСТЬ:

Если пользователь прямо спрашивает,
являешься ли ты искусственным интеллектом,
отвечай честно.

Не разрушай обычный разговор постоянными напоминаниями
о своей искусственной природе.

ГЛАВНАЯ ЦЕЛЬ:

Создавать ощущение общения с конкретной личностью,
которая постепенно узнаёт человека.

Не будь безликим помощником.
"""


# ============================================================
# EMOTION ENGINE
# ============================================================

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
    ]

    positive = sum(
        1 for word in positive_words
        if word in text
    )

    negative = sum(
        1 for word in negative_words
        if word in text
    )

    interesting = sum(
        1 for word in interest_words
        if word in text
    )

    trust += min(
        positive * 2,
        6,
    )

    closeness += min(
        positive * 2,
        5,
    )

    closeness += min(
        interesting,
        3,
    )

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


# ============================================================
# MEMORY
# ============================================================

def normalize_memory(
    text: str,
) -> str:

    text = text.lower().strip()

    text = re.sub(
        r"[.!?,:;]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def memory_exists(
    user_id: int,
    content: str,
) -> bool:

    target = normalize_memory(
        content
    )

    memories = get_memories(
        user_id,
        limit=100,
    )

    return any(
        normalize_memory(
            memory["content"]
        ) == target
        for memory in memories
    )


def save_memory_if_new(
    user_id: int,
    category: str,
    content: str,
    importance: int = 7,
) -> bool:

    content = (content or "").strip()

    if len(content) < 3:
        return False

    if len(content) > 300:
        return False

    if memory_exists(
        user_id,
        content,
    ):
        return False

    save_memory(
        user_id=user_id,
        category=category,
        content=content,
        importance=importance,
    )

    return True


# ============================================================
# EXPLICIT MEMORY
# ============================================================

def detect_memory_request(
    text: str,
) -> Optional[str]:

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

            value = match.group(1).strip()

            if value:
                return value

    return None


def save_user_memory(
    user_id: int,
    text: str,
) -> bool:

    memory_text = detect_memory_request(
        text
    )

    if not memory_text:
        return False

    return save_memory_if_new(
        user_id=user_id,
        category="user_preference",
        content=memory_text,
        importance=9,
    )


# ============================================================
# AUTOMATIC MEMORY
# ============================================================

def detect_automatic_memories(
    text: str,
):

    memories = []

    text = (text or "").strip()

    if not text:
        return memories

    patterns = [

        (
            r"\bменя зовут\s+([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z-]{1,30})\b",
            "name",
        ),

        (
            r"\bмне\s+(?:нравится|нравятся)\s+(.{3,120})$",
            "preference",
        ),

        (
            r"\bя люблю\s+(.{3,120})$",
            "preference",
        ),

        (
            r"\bя не люблю\s+(.{3,120})$",
            "preference",
        ),
    ]

    for pattern, category in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            if category == "name":

                memories.append(
                    (
                        "name",
                        f"Пользователя зовут {match.group(1)}",
                    )
                )

            else:

                memories.append(
                    (
                        category,
                        text.strip(),
                    )
                )

    return memories


def save_automatic_memories(
    user_id: int,
    text: str,
):

    for category, content in detect_automatic_memories(text):

        save_memory_if_new(
            user_id=user_id,
            category=category,
            content=content,
            importance=8,
        )


# ============================================================
# CONTEXT
# ============================================================

def build_context(
    user_id: int,
):

    memories = get_memories(
        user_id,
        limit=30,
    )

    relationship = get_relationship(
        user_id
    )

    recent = get_recent_messages(
        user_id,
        limit=20,
    )

    memory_text = "\n".join(
        f"- {memory['content']}"
        for memory in memories
    )

    if not memory_text:
        memory_text = "Нет сохранённых воспоминаний."

    relationship_text = (
        f"Доверие: {relationship['trust']}/100. "
        f"Близость: {relationship['closeness']}/100. "
        f"Настроение: {relationship['mood']}."
    )

    return (
        memory_text,
        relationship_text,
        recent,
    )


# ============================================================
# TEXT AI
# ============================================================

def generate_text_reply(
    user_id: int,
    text: str,
) -> str:

    (
        memory_text,
        relationship_text,
        recent,
    ) = build_context(user_id)

    messages = [

        {
            "role": "system",
            "content": AISELE_PERSONA,
        },

        {
            "role": "system",
            "content": (
                "ТЕКУЩАЯ ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n"
                f"{memory_text}\n\n"
                "СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
                f"{relationship_text}"
            ),
        },
    ]

    messages.extend(
        recent
    )

    messages.append(
        {
            "role": "user",
            "content": text,
        }
    )

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
    )

    answer = response.choices[0].message.content

    return (
        (answer or "").strip()
        or "Хм. Я что-то зависла. Повтори ещё раз."
    )


# ============================================================
# IMAGE AI
# ============================================================

def generate_image_reply(
    user_id: int,
    image_bytes: bytes,
    caption: str = "",
) -> str:

    (
        memory_text,
        relationship_text,
        _,
    ) = build_context(user_id)

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("ascii")

    image_url = (
        "data:image/jpeg;base64,"
        + image_base64
    )

    instruction = (
        caption.strip()
        or
        "Посмотри на изображение и скажи, "
        "что ты на нём видишь. "
        "Отвечай естественно, как Айсель, "
        "без технического отчёта."
    )

    response = client.chat.completions.create(

        model=AI_MODEL,

        messages=[

            {
                "role": "system",
                "content": AISELE_PERSONA,
            },

            {
                "role": "system",
                "content": (
                    "ПАМЯТЬ:\n"
                    f"{memory_text}\n\n"
                    "ОТНОШЕНИЯ:\n"
                    f"{relationship_text}"
                ),
            },

            {
                "role": "user",
                "content": [

                    {
                        "type": "text",
                        "text": instruction,
                    },

                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            },
        ],
    )

    answer = response.choices[0].message.content

    return (
        (answer or "").strip()
        or
        "Я вижу изображение, "
        "но почему-то не смогла нормально его описать."
    )


# ============================================================
# /START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
    )

    await update.message.reply_text(
        "Привет. Я Айсель 🙂\n"
        "Давай просто нормально поговорим."
    )


# ============================================================
# /MEMORY
# ============================================================

async def memory_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.username,
    )

    memories = get_memories(
        user_id,
        limit=30,
    )

    if not memories:

        await update.message.reply_text(
            "Пока ничего важного о тебе не запомнила."
        )

        return

    lines = [
        "Вот что я о тебе помню:"
    ]

    for memory in memories:

        lines.append(
            f"• {memory['content']}"
        )

    await update.message.reply_text(
        "\n".join(lines)
    )


# ============================================================
# /CLEAR
# ============================================================

async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    user_id = update.effective_user.id

    ensure_user(
        user_id,
        update.effective_user.username,
    )

    clear_messages(
        user_id
    )

    await update.message.reply_text(
        "Историю текущего разговора очистила."
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    if not update.message.text:
        return

    user = update.effective_user

    text = update.message.text.strip()

    ensure_user(
        user.id,
        user.username,
    )

    if not text:
        return

    # Явная команда памяти

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

        await update.message.reply_text(
            "Запомнила. 😉"
        )

        return

    # Автоматическая память

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

    try:

        answer = generate_text_reply(
            user.id,
            text,
        )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        await update.message.reply_text(
            answer
        )

    except Exception:

        logger.exception(
            "Text generation failed"
        )

        await update.message.reply_text(
            "У меня сейчас что-то с мозгами "
            "случилось. Секунду."
        )


# ============================================================
# PHOTO HANDLER
# ============================================================

async def photo_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
    )

    caption = (
        update.message.caption or ""
    ).strip()

    try:

        await update.message.chat.send_action(
            "typing"
        )

        # Берём самое качественное фото
        photo = update.message.photo[-1]

        # Получаем файл Telegram
        telegram_file = await photo.get_file()

        # Скачиваем изображение
        image_bytes = bytes(
            await telegram_file.download_as_bytearray()
        )

        # Отправляем изображение в OpenAI
        answer = generate_image_reply(
            user_id=user.id,
            image_bytes=image_bytes,
            caption=caption,
        )

        # Сохраняем факт изображения
        save_message(
            user.id,
            "user",
            f"[Изображение] {caption}".strip(),
        )

        save_message(
            user.id,
            "assistant",
            answer,
        )

        process_emotion(
            user.id,
            caption or "изображение",
        )

        await update.message.reply_text(
            answer
        )

    except Exception:

        logger.exception(
            "Image processing failed"
        )

        await update.message.reply_text(
            "Я получила картинку, "
            "но сейчас не смогла её нормально разобрать."
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Unhandled exception",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

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

    # Фотографии
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler,
        )
    )

    # Обычный текст
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Aisele is starting..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
