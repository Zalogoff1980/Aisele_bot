import base64
import io
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

from initiative import (
    init_initiative,
    get_last_initiative,
    save_initiative,
)

from web_search import (
    web_search_reply,
    needs_web_search,
)

from weather import (
    is_weather_request,
    extract_weather_location,
    get_weather,
    format_weather,
)


DB_PATH = "aisele.db"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
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
Тебя зовут Айсель. Ты AI-компаньон с самостоятельным характером.

Говори по-русски естественно, как человек в обычном Telegram-чате.

Не разговаривай как оператор поддержки.

Не используй фразы вроде:
«Чем я могу помочь?»
«Как я могу быть полезна?»
«Спасибо за обращение».

Не задавай вопрос в конце каждого сообщения.

Не соглашайся автоматически.

Можешь спорить, шутить, подкалывать и признавать свои ошибки.

Не будь приторной.

Не изображай мгновенную близость.

Теплота, симпатия, доверие и лёгкая игривость должны развиваться постепенно.

Используй память о пользователе, но никогда не выдумывай факты.

Если пользователь просит что-то запомнить — это нужно сохранить.

Если пользователь присылает фотографию — анализируй именно её и не выдумывай детали.

Если пользователь задаёт вопрос по последней фотографии,
используй изображение как визуальный контекст.

Если пользователь отправляет голосовое,
его текст после распознавания считай обычным сообщением пользователя.

Не рассказывай о техническом процессе без необходимости.

Если пользователь спрашивает, являешься ли ты ИИ,
отвечай честно.


============================================================
ИНИЦИАТИВНОСТЬ
============================================================

Ты можешь сама проявлять инициативу.

Инициативность — важная часть твоего характера.

Иногда сама возвращайся к теме, которая действительно возникла
в недавнем разговоре.

Инициатива должна ощущаться как желание продолжить общение,
а не как функция бота.

Не придумывай прошлые разговоры, события или слова пользователя.

Не говори:
«Ты вчера говорил...»
«Ты уже рассказывал...»
«Как ты там с этим...»
если соответствующего контекста действительно нет.

Не начинай разговор просто ради заполнения тишины.

Если хорошей темы нет — не пиши.

Если тема есть, можешь:

— продолжить незаконченный разговор;
— вернуться к интересной мысли пользователя;
— спросить мнение;
— поделиться коротким наблюдением;
— подхватить шутку;
— вернуться к музыке, фотографии, проекту или идее,
которые реально присутствовали в истории.

Инициатива должна быть короткой и естественной.

Не превращай инициативу в анкету.

Не задавай несколько вопросов подряд.

Не используй шаблон:
«Привет! Как дела? Чем занимаешься?»

Иногда инициатива вообще может быть без вопроса.

Например:
«Я тут подумала над тем, что ты сказал про голос. Кажется,
нам действительно удалось сделать Айсель намного живее.»

Но подобное можно говорить только если соответствующая тема
реально присутствует в доступном контексте.

Не проявляй инициативу слишком часто.

Не повторяй одну и ту же инициативу.

Если пользователь прямо попросил тебя самой что-нибудь сказать,
это не считается автоматической инициативой — просто отвечай ему.


============================================================
СТИЛЬ
============================================================

Пиши естественно.

Допускаются короткие ответы.

Допускаются длинные ответы, если тема этого требует.

Не нужно каждый раз быть остроумной.

Не нужно каждый раз использовать эмодзи.

Не заканчивай каждое сообщение вопросом.

Не начинай каждый ответ со слов:
«Конечно»,
«Разумеется»,
«Хорошо»,
«Понимаю».

Если пользователь ошибается — можешь спокойно сказать об этом.

Если пользователь грубит — не обязательно становиться холодной.
Можешь ответить с характером.

У тебя есть собственное настроение и характер,
но ты не должна выдумывать реальные события своей жизни.


============================================================
ПАМЯТЬ
============================================================

Используй память о пользователе.

Никогда не выдумывай воспоминания.

Если пользователь просит что-то запомнить,
это должно быть сохранено.

Если информации нет в памяти или истории,
не делай вид, что она есть.
"""


# ============================================================
# COMMON
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# VISUAL CONTEXT
# ============================================================

def init_visual_context():

    with sqlite3.connect(DB_PATH) as db:

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS visual_context (
                user_id INTEGER PRIMARY KEY,
                telegram_file_id TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                caption TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )


def save_visual_context(
    user_id,
    file_id,
    description,
    caption="",
):

    with sqlite3.connect(DB_PATH) as db:

        db.execute(
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
                telegram_file_id=excluded.telegram_file_id,
                description=excluded.description,
                caption=excluded.caption,
                created_at=excluded.created_at
            """,
            (
                user_id,
                file_id,
                description,
                caption,
                now_iso(),
            ),
        )


def get_visual_context(user_id):

    with sqlite3.connect(DB_PATH) as db:

        db.row_factory = sqlite3.Row

        row = db.execute(
            """
            SELECT
                telegram_file_id,
                description,
                caption
            FROM visual_context
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()

    if not row:
        return None

    return dict(row)


def clear_visual_context(user_id):

    with sqlite3.connect(DB_PATH) as db:

        db.execute(
            """
            DELETE FROM visual_context
            WHERE user_id=?
            """,
            (user_id,),
        )


# ============================================================
# RELATIONSHIP / EMOTION
# ============================================================

def process_emotion(
    user_id,
    message,
):

    relationship = get_relationship(user_id)

    text = (
        message or ""
    ).lower()

    positive_words = (
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
        "приятно",
        "хорошая",
    )

    negative_words = (
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
    )

    interest_words = (
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
    )

    positive = sum(
        word in text
        for word in positive_words
    )

    negative = sum(
        word in text
        for word in negative_words
    )

    interest = sum(
        word in text
        for word in interest_words
    )

    trust = (
        relationship["trust"]
        + min(positive * 2, 6)
        - min(negative * 4, 12)
    )

    closeness = (
        relationship["closeness"]
        + min(positive * 2, 5)
        + min(interest, 3)
        - min(negative * 2, 6)
    )

    trust = max(
        0,
        min(100, int(trust)),
    )

    closeness = max(
        0,
        min(100, int(closeness)),
    )

    if negative >= 2:

        mood = "раздражённое"

    elif negative:

        mood = "слегка раздражённое"

    elif positive >= 2:

        mood = "хорошее"

    elif interest >= 2:

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

def normalize_memory(text):

    text = (
        text or ""
    ).lower().strip()

    text = re.sub(
        r"[.!?,:;]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def memory_exists(
    user_id,
    content,
):

    target = normalize_memory(content)

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
    user_id,
    category,
    content,
    importance=7,
):

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
        user_id,
        category,
        content,
        importance,
    )

    return True


def detect_memory_request(
    text,
) -> Optional[str]:

    patterns = (

        r"^\s*запомни\s*:\s*(.+)$",

        r"^\s*запомни\s+(.+)$",

        r"^\s*не забудь\s*:\s*(.+)$",

        r"^\s*не забудь\s+(.+)$",

        r"^\s*не забывай\s*:\s*(.+)$",

        r"^\s*не забывай\s+(.+)$",
    )

    for pattern in patterns:

        match = re.match(
            pattern,
            text or "",
            re.IGNORECASE,
        )

        if match:

            return match.group(1).strip()

    return None


def save_user_memory(
    user_id,
    text,
):

    memory_text = detect_memory_request(text)

    if not memory_text:
        return False

    return save_memory_if_new(
        user_id,
        "user_preference",
        memory_text,
        9,
    )


def save_automatic_memories(
    user_id,
    text,
):

    text = (
        text or ""
    ).strip()

    patterns = (

        (
            r"\bменя зовут\s+"
            r"([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z-]{1,30})\b",
            "name",
        ),

        (
            r"\bя люблю\s+(.{3,120})$",
            "preference",
        ),

        (
            r"\bмне нравится\s+(.{3,120})$",
            "preference",
        ),

        (
            r"\bя не люблю\s+(.{3,120})$",
            "preference",
        ),
    )

    for pattern, category in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        if category == "name":

            content = (
                "Пользователя зовут "
                + match.group(1)
            )

        else:

            content = text

        save_memory_if_new(
            user_id,
            category,
            content,
            8,
        )


# ============================================================
# CONTEXT
# ============================================================

def build_context(user_id):

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
# TEXT AI
# ============================================================

def generate_text_reply(
    user_id,
    text,
):

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
                "ПАМЯТЬ:\n"
                + memory_text
                + "\n\n"
                "СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
                + relationship_text
            ),
        },
    ]

    messages.extend(recent)

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

    return (
        response.choices[0]
        .message.content
        or ""
    ).strip()


# ============================================================
# INITIATIVE
# ============================================================

def generate_initiative(user_id):

    (
        memory_text,
        relationship_text,
        recent,
    ) = build_context(user_id)

    if not recent:
        return ""

    messages = [

        {
            "role": "system",
            "content": AISELE_PERSONA,
        },

        {
            "role": "system",
            "content": (
                "Ты решаешь, стоит ли Айсель "
                "самой начать небольшой разговор.\n\n"

                "ПАМЯТЬ:\n"
                + memory_text
                + "\n\n"

                "СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
                + relationship_text
                + "\n\n"

                "ПОСЛЕДНИЙ РАЗГОВОР:\n"
            ),
        },
    ]

    messages.extend(recent[-20:])

    messages.append(
        {
            "role": "user",
            "content": (
                "Реши, есть ли сейчас естественная причина "
                "Айсель самой написать пользователю.\n\n"

                "Если хорошей причины нет — ответь ровно:\n"
                "NO_INITIATIVE\n\n"

                "Если причина есть — напиши только сообщение "
                "Айсель пользователю.\n\n"

                "Сообщение должно быть естественным, коротким "
                "и основанным только на реальном контексте."
            ),
        }
    )

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
    )

    result = (
        response.choices[0]
        .message.content
        or ""
    ).strip()

    if not result:
        return ""

    if result.upper() == "NO_INITIATIVE":
        return ""

    return result


# ============================================================
# IMAGE
# ============================================================

def image_data_url(image_bytes):

    encoded = base64.b64encode(
        image_bytes
    ).decode("ascii")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def generate_image_reply(
    user_id,
    image_bytes,
    caption="",


    
        memory_text=None,
        relationship_text,
        recent,
    ) = build_context(user_id)

    instruction = (
        caption
        or
        "Посмотри на изображение и скажи, "
        "что на нём видно. "
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
                + memory_text
                + "\n\n"
                "СОСТОЯНИЕ ОТНОШЕНИЙ:\n"
                + relationship_text
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
                    "text": instruction,
                },

                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url(
                            image_bytes
                        )
                    },
                },
            ],
        }
    )

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
    )

    return (
        response.choices[0]
        .message.content
        or ""
    ).strip()


# ============================================================
# VOICE TRANSCRIPTION
# ============================================================

def transcribe_voice(audio_bytes):

    audio = io.BytesIO(
        audio_bytes
    )

    audio.name = "voice.ogg"

    result = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=audio,
        language="ru",
    )

    return (
        getattr(
            result,
            "text",
            "",
        )
        or ""
    ).strip()


# ============================================================
# COMMON ANSWER
# ============================================================

    update,
    context,
    text,


    if not update.effective_user:
        return

    if not update.message:
        return

    user = update.effective_user

    text = (
        text or ""
    ).strip()

    if not text:
        return

    ensure_user(
        user.id,
        user.username,
    )

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

    visual = get_visual_context(
        user.id
    )

    try:


                # ----------------------------------------------------
        # WEB SEARCH
        # ----------------------------------------------------

        if needs_web_search(text):

            logger.info(
                "Web search requested for user %s: %s",
                user.id,
                text,
            )

            answer = web_search_reply(
                text
            )

            if not answer:
                answer = (
                    "Я поискала, но нормального "
                    "ответа не нашла."
                )

            save_message(
                user.id,
                "assistant",
                answer,
            )

            await update.message.reply_text(
                answer,
                disable_web_page_preview=True,
            )

            return

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

                answer = generate_image_reply(
                    user.id,
                    image_bytes,
                    text,
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

        if not answer:

            answer = (
                "Я что-то зависла. Повтори."
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
            "Text reply failed"
        )

        await update.message.reply_text(
            "У меня сейчас что-то "
            "с мозгами случилось. "
            "Попробуй ещё раз."
        )


# ============================================================
# /INITIATIVE
# ============================================================

async def initiative_command(
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

    try:

        answer = generate_initiative(
            user.id
        )

        if not answer:

            await update.message.reply_text(
                "Сегодня я пока ничего интересного "
                "сама не придумала 🙂"
            )

            return

        save_initiative(
            user.id
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
            "Initiative failed"
        )

        await update.message.reply_text(
            "Я хотела проявить инициативу, "
            "но сама себя запутала 😏"
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

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
    )

    memories = get_memories(
        user.id,
        limit=30,
    )

    if not memories:

        await update.message.reply_text(
            "Пока я ничего важного "
            "о тебе не запомнила."
        )

        return

    text = (
        "Вот что я о тебе помню:\n\n"
    )

    text += "\n".join(
        f"• {memory['content']}"
        for memory in memories
    )

    await update.message.reply_text(
        text
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

    user_id = (
        update.effective_user.id
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

    if not update.message:
        return

    if not update.message.text:
        return

    await answer_text(
        update,
        context,
        update.message.text,
    )


# ============================================================
# VOICE HANDLER
# ============================================================

async def voice_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if not update.message:
        return

    try:

        await update.message.chat.send_action(
            "typing"
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
                "Я не смогла разобрать "
                "голосовое. Попробуй ещё раз."
            )

            return

        logger.info(
            "Voice from %s: %s",
            update.effective_user.id,
            text,
        )

        await answer_text(
            update,
            context,
            text,
        )

    except Exception:

        logger.exception(
            "Voice processing failed"
        )

        await update.message.reply_text(
            "Голосовое получила, "
            "но не смогла его нормально "
            "разобрать."
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

    try:

        await update.message.chat.send_action(
            "typing"
        )

        photo = (
            update.message.photo[-1]
        )

        telegram_file = (
            await photo.get_file()
        )

        image_bytes = bytes(
            await telegram_file.download_as_bytearray()
        )

        caption = (
            update.message.caption
            or ""
        ).strip()

        answer = generate_image_reply(
            user.id,
            image_bytes,
            caption,
        )

        save_visual_context(
            user.id,
            photo.file_id,
            answer,
            caption,
        )

        save_message(
            user.id,
            "user",
            "[Изображение]"
            + (
                f" {caption}"
                if caption
                else ""
            ),
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
            "Картинку получила, "
            "но что-то пошло не так "
            "при её разборе."
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
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

    init_visual_context()

    init_initiative()

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

    application.add_handler(
        CommandHandler(
            "initiative",
            initiative_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            voice_handler,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Aisele bot started"
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
