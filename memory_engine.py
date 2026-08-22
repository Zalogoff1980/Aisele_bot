import json
import logging

from openai import OpenAI

from memory_manager import save_unique_memory


logger = logging.getLogger(__name__)


MEMORY_MODEL = "gpt-5.6"


MEMORY_INSTRUCTIONS = """
Ты — модуль долговременной памяти ИИ-компаньона Айсель.

Проанализируй сообщение пользователя и определи,
есть ли в нём информация, которую действительно стоит
сохранить для будущих разговоров.

Сохраняй устойчивые факты:

- имя;
- интересы;
- любимую музыку, фильмы, игры;
- предпочтения;
- привычки;
- важные события;
- планы;
- цели;
- значимые отношения;
- важные факты жизни;
- информацию, которую пользователь прямо просит запомнить.

НЕ сохраняй:

- приветствия;
- случайные реплики;
- обычные вопросы;
- временное настроение;
- бессмысленную болтовню;
- информацию, относящуюся только к текущему запросу;
- предположения;
- информацию, которой нет в сообщении.

Не выдумывай факты.

Если запоминать нечего — верни пустой список.

Верни ТОЛЬКО JSON:

{
  "memories": [
    {
      "category": "категория",
      "content": "краткий факт",
      "importance": 1
    }
  ]
}

importance:

1-3 — малозначимо
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

        memories = data.get(
            "memories",
            []
        )

        if not isinstance(
            memories,
            list
        ):
            return

        for item in memories:

            if not isinstance(
                item,
                dict
            ):
                continue

            category = item.get(
                "category"
            )

            content = item.get(
                "content"
            )

            importance = item.get(
                "importance",
                5
            )

            if not category or not content:
                continue

            try:
                importance = int(
                    importance
                )
            except (
                TypeError,
                ValueError
            ):
                importance = 5

            importance = max(
                1,
                min(10, importance)
            )

            save_unique_memory(
                user_id=user_id,
                category=str(
                    category
                ),
                content=str(
                    content
                ),
                importance=importance,
            )

    except Exception:

        logger.exception(
            "Memory extraction failed"
        )
