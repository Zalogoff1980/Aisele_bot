import base64
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

РАБОТА С ИЗОБРАЖЕНИЯМИ:

Если пользователь отправил фотографию или изображение,
ты действительно анализируешь его содержимое.

Не говори, что не видишь изображение,
если изображение было успешно передано тебе.

Опирайся только на то, что действительно видно
на изображении.

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

Если пользователь прямо спрашивает, являешься ли ты
искусственным интеллектом, отвечай честно.

Не разрушай обычный разговор постоянными напоминаниями
о своей искусственной природе.
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
        "нравится",
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


# ============================================================
# MEMORY
# ============================================================

def normalize_memory(text: str) -> str:
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

    for memory in memories:

        existing = normalize_memory(
            memory["content"]
        )

        if existing == target:
            return True

    return False


def save_memory_if_new(
    user_id: int,
    category: str,
    content: str,
    importance: int = 7,
) -> bool:

    if not content:
        return False

    content = content.strip()

    if len(content) < 3:
        return False

    if len(content) > 200:
        return False

    if memory_exists(
        user_id,
        content,
    ):
        logger.info(
            "Duplicate memory ignored: %s",
            content,
        )

        return False

    save_memory(
        user_id=user_id,
        category=category,
        content=content,
        importance=importance,
    )

    logger.info(
        "Memory saved for %s: %s",
        user_id,
        content,
    )

    return True


# ============================================================
# EXPLICIT MEMORY
# ============================================================

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

    text = text.strip()

    if not text:
       
