import json
import logging

from openai import OpenAI

from memory import save_memory


logger = logging.getLogger(__name__)


MEMORY_MODEL = "gpt-5.6-luna"


MEMORY_INSTRUCTIONS = """
Ты — модуль долговременной памяти ИИ-компаньона Айсель.

Твоя задача — определить, содержит ли сообщение пользователя
информацию, которую действительно стоит сохранить на будущее.

Сохраняй только полезные устойчивые сведения.

Хорошо сохранять:
- имя и важные личные сведения;
- интересы;
- любимую музыку, фильмы, игры;
- предпочтения;
- важные события;
- планы;
- цели;
- привычки;
- значимые отношения;
- важные факты из жизни;
- вещи, которые пользователь явно просит запомнить.

Не сохраняй:
- случайные фразы;
- приветствия;
- временное настроение;
- обычные вопросы;
- бессмысленную болтовню;
- технические детали текущего диалога;
- предположения о пользователе.

Не придумывай информацию.

Если сохранять нечего — верни пустой список.

Верни ТОЛЬКО JSON следующего формата:

{
  "memories": [
    {
      "category": "категория",
      "content": "краткая формулировка факта",
      "importance": 1
    }
  ]
}

importance:
1-3 — мало важно
4-6 — умеренно важно
7-8 — важно
9-10 — очень важно
"""


def extract_memories(
    client: OpenAI,
    user_id: int,
    user_message: str,
):
    try:
        response = client.responses.create(
            model=MEMORY_MODEL,
            instructions=MEMORY_INSTRUCTIONS,
            input=user_message,
        )

        raw = response.output_text.strip()

        data = json.loads(raw)

        memories = data.get("memories", [])

        if not isinstance(memories, list):
            return

        for item in memories:
            if not isinstance(item, dict):
                continue

            category = item.get("category")
            content = item.get("content")
            importance = item.get("importance", 5)

            if not category or not content:
                continue

            try:
                importance = int(importance)
            except (TypeError, ValueError):
                importance = 5

            importance = max(
                1,
                min(10, importance)
            )

            save_memory(
                user_id=user_id,
                category=str(category),
                content=str(content),
                importance=importance,
            )

    except Exception:
        logger.exception(
            "Memory extraction failed"
          )
