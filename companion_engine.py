import json
import logging

from openai import OpenAI

from config import MEMORY_MODEL
from emotion import apply_emotion
from memory_manager import save_unique_memory


logger = logging.getLogger(__name__)


ANALYSIS_INSTRUCTIONS = """
Ты — внутренний аналитический модуль ИИ-компаньона Айсель.

Проанализируй сообщение пользователя.

Определи две вещи:

1. Эмоциональную реакцию Айсель.
2. Нужно ли сохранить устойчивую информацию о пользователе.

Допустимые эмоции:

нейтральное
заинтересованное
тёплое
радостное
настороженное
обиженное

Обычная реплика чаще всего должна быть нейтральной.

Не создавай искусственную обиду.
Не считай обычное несогласие оскорблением.

Сохраняй только устойчивые и полезные сведения:

- имя;
- интересы;
- любимую музыку;
- фильмы и сериалы;
- игры;
- предпочтения;
- привычки;
- цели;
- планы;
- важные события;
- значимые отношения;
- информацию, которую пользователь прямо просит запомнить.

Не сохраняй:

- приветствия;
- случайные реплики;
- обычные вопросы;
- временное настроение;
- бессмысленную болтовню;
- предположения;
- информацию только для текущего ответа.

Не выдумывай факты.

Верни ТОЛЬКО JSON:

{
  "emotion": "нейтральное",
  "memories": [
    {
      "category": "категория",
      "content": "краткая формулировка факта",
      "importance": 5
    }
  ]
}

Если сохранять нечего:

{
  "emotion": "нейтральное",
  "memories": []
}
"""


ALLOWED_EMOTIONS = {
    "нейтральное",
    "заинтересованное",
    "тёплое",
    "радостное",
    "настороженное",
    "обиженное",
}


def analyze_message(
    client: OpenAI,
    user_id: int,
    user_message: str,
):
    try:
        response = client.responses.create(
            model=MEMORY_MODEL,
            instructions=ANALYSIS_INSTRUCTIONS,
            input=user_message,
        )

        raw = response.output_text.strip()
        data = json.loads(raw)

        emotion = data.get(
            "emotion",
            "нейтральное",
        )

        if emotion not in ALLOWED_EMOTIONS:
            emotion = "нейтральное"

        apply_emotion(
            user_id,
            emotion,
        )

        memories = data.get(
            "memories",
            [],
        )

        saved = 0

        if isinstance(memories, list):
            for item in memories:

                if not isinstance(item, dict):
                    continue

                category = item.get("category")
                content = item.get("content")

                if not category or not content:
                    continue

                try:
                    importance = int(
                        item.get("importance", 5)
                    )
                except (TypeError, ValueError):
                    importance = 5

                importance = max(
                    1,
                    min(10, importance),
                )

                if save_unique_memory(
                    user_id=user_id,
                    category=str(category),
                    content=str(content),
                    importance=importance,
                ):
                    saved += 1

        return {
            "emotion": emotion,
            "memories_saved": saved,
        }

    except Exception:
        logger.exception(
            "Companion analysis failed"
        )

        return {
            "emotion": "нейтральное",
            "memories_saved": 0,
        }
