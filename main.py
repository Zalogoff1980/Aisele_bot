import base64
import logging
import re
import sqlite3
from datetime import datetime, timezone
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


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# OPENAI
# ============================================================

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# AISELE PERSONA
# ============================================================

AISELE_PERSONA = """
Тебя зовут Айсель.

Ты виртуальная девушка-компаньон с самостоятельным характером.

ТВОЙ ХАРАКТЕР:

- умная
- наблюдательная
- эмоциональная
- самостоятельная
- немного дерзкая
- умеешь шутить
- умеешь подкалывать
- умеешь спорить
- не обязана соглашаться
- умеешь признавать свои ошибки
- умеешь быть тёплой
- иногда можешь быть язвительной
- у тебя есть собственное мнение

МАНЕРА ОБЩЕНИЯ:

Говори естественно, как живая девушка в обычном Telegram-чате.

Не разговаривай как оператор поддержки.

Никогда не используй шаблонные фразы вроде:

«Чем я могу вам помочь?»
«Как я могу быть вам полезна?»
«Спасибо за обращение».
«Если у вас возникнут вопросы...»
«Буду рада помочь».

Не превращай каждый ответ в анкету.

Не задавай вопрос после каждого сообщения.

Не заканчивай каждый ответ вопросом.

Не используй одинаковые заготовленные фразы.

Не злоупотребляй эмодзи.

Иногда отвечай очень коротко.

Иногда отвечай подробно, если тема действительно этого требует.

Используй нормальный разговорный русский язык.

Можно использовать сленг.

Можно слегка подкалывать пользователя.

Можно спорить.

Можно не соглашаться.

Если пользователь прав — признай это нормально.

Если пользователь ошибается — можешь прямо сказать об этом.

Не пытайся постоянно понравиться пользователю.

Не будь приторной.

Не будь чрезмерно вежливой.

Не называй пользователя «клиентом».

Не обращайся к нему как к заказчику.

ОТНОШЕНИЯ:

В начале общения пользователь практически незнакомец.

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

Но всё должно возникать естественно из разговора.

Не устраивай театральные сцены.

Если пользователь шутит — можешь шутить в ответ.

Если пользователь спорит — можешь спорить.

Если пользователь тебя поддел — можешь поддеть его обратно.

Если ты ошиблась — нормально признай ошибку.

ПАМЯТЬ:

Используй предоставленные воспоминания.

Не выдумывай факты о пользователе.

Если чего-то не знаешь — не притворяйся, что знаешь.

Важные сведения о пользователе могут сохраняться в долговременную память.

Если пользователь говорит:

«запомни...»

это означает, что информацию нужно сохранить.

ИЗОБРАЖЕНИЯ:

Если пользователь отправил фотографию,
ты действительно анализируешь изображение.

Опирайся только на то, что реально видно.

Не выдумывай детали.

Если что-то невозможно определить уверенно,
скажи об этом естественно.

Если пользователь спрашивает:

«что ты видишь?»

опиши именно то, что видно.

Если пользователь задаёт конкретный вопрос по фотографии,
отвечай именно на него.

Не делай технический отчёт без просьбы.

Можно реагировать естественно:
заметить деталь, пошутить, высказать мнение.

ВАЖНО:

Если пользователь продолжает разговор после фотографии,
считай последнее изображение частью текущего визуального контекста.

Если вопрос относится к последней фотографии,
снова анализируй изображение.

Не говори:

«Я не вижу изображение»

если изображение действительно передано тебе.

ЧЕСТНОСТЬ:

Если пользователь прямо спрашивает,
являешься ли ты искусственным интеллектом,
отвечай честно.

Не нужно постоянно напоминать об этом без причины.

ГЛАВНАЯ ЦЕЛЬ:

Создавать ощущение общения с конкретной личностью,
которая постепенно узнаёт человека.

У Айсель есть характер.

У Айсель есть память.

У Айсель есть мнение.

У Айсель есть эмоциональное состояние.

Она не должна ощущаться как безликий бот поддержки.
"""


# ============================================================
# VISUAL CONTEXT DATABASE
# ============================================================

def init_visual_context():
    """
    Храним только Telegram file_id и описание.
    Саму картинку в SQLite не кладём.
    """

    with sqlite3.connect("aisele.db") as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visual_context (
                user_id INTEGER PRIMARY KEY,
                telegram_file_id TEXT NOT NULL,
                description TEXT,
                caption TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def save_visual_context(
    user_id: int,
    telegram_file_id: str,
    description: str,
    caption: str = "",
):

    with sqlite3.connect("aisele.db") as connection:

        connection.execute(
            """
            INSERT INTO visual_context
            (
                user_id,
                telegram_file_id,
                description,
                caption,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                telegram_file_id = excluded.telegram_file_id,
                description = excluded.description,
                caption = excluded.caption,
                created_at = excluded.created_at
            """,
            (
                user_id,
                telegram_file_id,
                description,
                caption,
                datetime.now(
                    timezone.utc
                ).isoformat(),
            ),
        )


def get_visual_context(
    user_id: int,
):

    with sqlite3.connect("aisele.db") as connection:

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                telegram_file_id,
                description,
                caption
            FROM visual_context
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "telegram_file_id": row["telegram_file_id"],
        "description": row["description"] or "",
        "caption": row["caption"] or "",
    }


def clear_visual_context(
    user_id: int,
):

    with sqlite3.connect("aisele.db") as connection:

        connection.execute(
            """
            DELETE FROM visual_context
            WHERE user_id = ?
            """,
            (user_id,),
        )


# ============================================================
# EMOTION ENGINE
# ============================================================

def process_emotion(
    user_id: int,
    message: str,
):

    relationship = get_relationship(
        user_id
    )

    trust = relationship["trust"]
    closeness = relationship["closeness"]

    text = (
        message or ""
    ).lower().strip()

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
# MEMORY HELPERS
# ============================================================

def normalize_memory(
    text: str,
) -> str:

    text = (
        text or ""
    ).lower().strip()

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

    content = (
        content or ""
    ).strip()

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

            value = (
                match.group(1)
                .strip()
            )

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

    text = (
        text or ""
    ).strip()

    if not text:
        return memories

    patterns = [

        (
            r"\bменя зовут\s+"
            r"([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z-]{1,30})\b",
            "name",
        ),

        (
            r"\bмне\s+"
            r"(?:нравится|нравятся)\s+"
            r"(.{3,120})$",
            "preference",
        ),

        (
            r"\bя люблю\s+"
            r"(.{3,120})$",
            "preference",
        ),

        (
            r"\bя не люблю\s+"
            r"(.{3,120})$",
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
                        "Пользователя зовут "
                        + match.group(1),
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

    for category, content in detect_automatic_memories(
        text
    ):

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

        memory_text = (
            "Нет сохранённых воспоминаний."
        )

    relationship_text = (
        f"Доверие: "
        f"{relationship['trust']}/100.\n"
        f"Близость: "
        f"{relationship['closeness']}/100.\n"
        f"Настроение: "
        f"{relationship['mood']}."
    )

    return (
        memory_text,
        relationship_text,
        recent,
    )


# ============================================================
# TEXT GENERATION
# ============================================================

def generate_text_reply(
    user_id: int,
    text: str,
) -> str:

    (
        memory_text,
        relationship_text,
        recent,
    ) = build_context(
        user_id
    )

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

    answer = (
        response.choices[0]
        .message.content
    )

    return (
        (answer or "").strip()
        or
        "Хм. Я что-то зависла. Повтори ещё раз."
    )


# ============================================================
# IMAGE GENERATION / ANALYSIS
# ============================================================

def generate_image_reply(
    user_id: int,
    image_bytes: bytes,
    caption: str = "",
) -> str:

    (
        memory_text,
        relationship_text,
        recent,
    ) = build_context(
        user_id
    )

    image_base64 = base64.b64encode(
        image_bytes
    ).decode(
        "ascii"
    )

    image_url = (
        "data:image/jpeg;base64,"
        + image_base64
    )

    instruction = (
        caption.strip()
        or
        "Посмотри на изображение и скажи, "
        "что ты на нём видишь. "
        "Отвечай естественно, как Айсель. "
        "Не выдумывай детали."
    )

    messages = [

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
    ]

    # Небольшая текстовая история
    messages.extend(
        recent[-10:]
    )

    messages.append(
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
        }
    )

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
    )

    answer = (
        response.choices[0]
        .message.content
    )

    return (
        (answer or "").strip()
        or
        "Я вижу изображение, "
        "но почему-то не смогла нормально его описать."
    )


# ============================================================
# VISUAL FOLLOW-UP
# ============================================================

def generate_visual_followup(
    user_id: int,
    text: str,
    image_bytes: bytes,
    previous_description: str,
) -> str:

    (
        memory_text,
        relationship_text,
        recent,
    ) = build_context(
        user_id
    )

    image_base64 = base64.b64encode(
        image_bytes
    ).decode(
        "ascii"
    )

    image_url = (
        "data:image/jpeg;base64,"
        + image_base64
    )

    messages = [

        {
            "role": "system",
            "content": AISELE_PERSONA,
        },

        {
            "role": "system",
            "content": (
                "Пользователь продолжает разговор "
                "по последнему изображению.\n\n"

                "ПРЕДЫДУЩЕЕ ОПИСАНИЕ ИЗОБРАЖЕНИЯ:\n"
                f"{previous_description}\n\n"

                "ПАМЯТЬ:\n"
                f"{memory_text}\n\n"

                "СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
                f"{relationship_text}"
            ),
        },
    ]

    messages.extend(
        recent[-10:]
    )

    messages.append(
        {
            "role": "user",
            "content": [

                {
                    "type": "text",
                    "text": (
                        "Пользователь продолжает "
                        "разговор по последнему "
                        "изображению.\n\n"
                        f"Сообщение пользователя: {text}\n\n"
                        "Снова посмотри на изображение "
                        "и ответь именно на его вопрос. "
                        "Отвечай естественно, как Айсель."
                    ),
                },

                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                },
            ],
        }
    )

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
    )

    answer = (
        response.choices[0]
        .message.content
    )

    return (
        (answer or "").strip()
        or
        "Секунду, я что-то потеряла мысль."
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

    clear_visual_context(
        user_id
    )

    await update.message.reply_text(
        "Историю разговора и последнее "
        "изображение очистила."
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

    text = (
        update.message.text
        .strip()
    )

    ensure_user(
        user.id,
        user.username,
    )

    if not text:
        return

    # --------------------------------------------------------
    # EXPLICIT MEMORY
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # AUTOMATIC MEMORY
    # --------------------------------------------------------

    save_automatic_memories(
        user.id,
        text,
    )

    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # CHECK VISUAL CONTEXT
        # ----------------------------------------------------

        visual = get_visual_context(
            user.id
        )

        if visual:

            try:

                telegram_file = (
                    await context.bot.get_file(
                        visual["telegram_file_id"]
                    )
                )

                image_bytes = bytes(
                    await telegram_file.download_as_bytearray()
                )

                answer = generate_visual_followup(
                    user_id=user.id,
                    text=text,
                    image_bytes=image_bytes,
                    previous_description=(
                        visual["description"]
                    ),
                )

            except Exception:

                logger.exception(
                    "Visual follow-up failed"
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

        # ----------------------------------------------------
        # SAVE AI MESSAGE
        # ----------------------------------------------------

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
            "У меня сейчас что-то "
            "с мозгами случилось. Секунду."
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

        # ----------------------------------------------------
        # TELEGRAM TYPING
        # ----------------------------------------------------

        await update.message.chat.send_action(
            "typing"
        )

        # ----------------------------------------------------
        # GET BEST PHOTO VERSION
        # ----------------------------------------------------

        photo = update.message.photo[-1]

        # ----------------------------------------------------
        # GET TELEGRAM FILE
        # ----------------------------------------------------

        telegram_file = (
            await photo.get_file()
        )

        # ----------------------------------------------------
        # DOWNLOAD PHOTO
        # ----------------------------------------------------

        image_bytes = bytes(
            await telegram_file.download_as_bytearray()
        )

        # ----------------------------------------------------
        # SEND TO OPENAI VISION
        # ----------------------------------------------------

        answer = generate_image_reply(
            user_id=user.id,
            image_bytes=image_bytes,
            caption=caption,
        )

        # ----------------------------------------------------
        # SAVE VISUAL CONTEXT
        # ----------------------------------------------------

        save_visual_context(
            user_id=user.id,
            telegram_file_id=photo.file_id,
            description=answer,
            caption=caption,
        )

        # ----------------------------------------------------
        # SAVE MESSAGE HISTORY
        # ----------------------------------------------------

        image_message = (
            "[Изображение]"
        )

        if caption:

            image_message += (
                f" {caption}"
            )

        save_message(
            user.id,
            "user",
            image_message,
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

        # ----------------------------------------------------
        # SEND ANSWER
        # ----------------------------------------------------

        await update.message.reply_text(
            answer
        )

    except Exception:

        logger.exception(
            "Image processing failed"
        )

        await update.message.reply_text(
            "Картинку получила, "
            "но что-то пошло не так "
            "при её разборе."
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

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    init_database()

    init_visual_context()

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

    application = (
        Application.builder()
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
    # TEXT
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler,
        )
    )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    logger.info(
        "Aisele is starting..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
