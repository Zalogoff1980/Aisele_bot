import logging

from memory import get_memories, save_memory


logger = logging.getLogger(__name__)


def normalize(text):
    """
    Простая нормализация текста
    для поиска очевидных дублей.
    """

    return (
        text
        .lower()
        .strip()
        .replace(".", "")
        .replace(",", "")
        .replace("!", "")
        .replace("?", "")
    )


def is_duplicate(
    new_content,
    existing_memories,
):
    """
    Проверяем, не существует ли уже
    практически такого же воспоминания.
    """

    new_text = normalize(new_content)

    for memory in existing_memories:

        old_text = normalize(
            memory["content"]
        )

        if new_text == old_text:
            return True

    return False


def save_unique_memory(
    user_id,
    category,
    content,
    importance=5,
):
    """
    Сохраняет воспоминание только если
    такого факта ещё нет.
    """

    existing = get_memories(
        user_id,
        limit=100
    )

    if is_duplicate(
        content,
        existing
    ):
        logger.info(
            "Duplicate memory skipped"
        )
        return False

    save_memory(
        user_id=user_id,
        category=category,
        content=content,
        importance=importance,
    )

    return True
