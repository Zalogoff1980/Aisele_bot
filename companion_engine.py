import json
import logging

from openai import OpenAI

from memory_manager import save_unique_memory
from emotion import apply_emotion


logger = logging.getLogger(__name__)


ANALYSIS_MODEL = "gpt-5.6"


ANALYSIS_INSTRUCTIONS = """
Ты — внутренний аналитический модуль ИИ-компаньона Айсель.

Проанализируй сообщение пользователя.

Нужно определить две вещи:

1. Эмоциональную реакцию Айсель.
2. Нужно ли сохранить какую-либо информацию
   о пользователе в долговременную память.

ЭМОЦИИ:

Допустимые значения:

нейтральное
заинтересованное
тёплое
радостное
настороженное
обиженное

Обычная реплика должна чаще всего давать
нейтральную реакцию.

Не создавай искусственную обиду.

Не интерпретируй обычное несогласие как оскорбление.

ПАМЯТЬ:

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
- информацию, которую пользователь явно просит запомнить.

Не сохраняй:

- приветствия;
- случайные реплики;
- обычные вопросы;
- временное настроение;
- бессмысленную болтовню;
- предположения;
- информацию, которая нужна только для текущего ответа.

Не выдумывай факты.

Верни ТОЛЬКО JSON:

{
  "emotion": "нейтральное",
  "memories": [
    {
      "category": "категория",
      "content": "краткая формулировка факта",
      "importance": 1
    }
  ]
}

Если сохранять нечего:

{
  "emotion": "нейтральное",
  "memories": []
}

importance:

1-3 — малозначимо
4-6 — умеренно важно
7-8 — важно
9-10 — очень важно
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
            model=ANALYSIS_MODEL,
            instructions=ANALYSIS_INSTRUCTIONS,
            input=user_message,
        )

        raw = response.output_text.strip()

        data = json.loads(raw)

        emotion = data.get(
            "emotion",
            "нейтральное"
        )

        if emotion not in ALLOWED_EMOTIONS:
            emotion = "нейтральное"

        # Обновляем эмоциональное состояние
        apply_emotion(
            user_id,
            emotion
        )

        memories = data.get(
            "memories",
            []
        )

        if isinstance(memories, list):

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
                    category=str(category),
                    content=str(content),
                    importance=importance,
                )

        return {
            "emotion": emotion,
            "memories_saved": len(memories)
            if isinstance(memories, list)
            else 0,
        }

    except Exception:

        logger.exception(
            "Companion analysis failed"
        )

        return {
            "emotion": "нейтральное",
            "memories_saved": 0,
        }
