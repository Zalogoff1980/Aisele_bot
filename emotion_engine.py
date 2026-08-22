import json
import logging

from openai import OpenAI

from emotion import apply_emotion


logger = logging.getLogger(__name__)


EMOTION_MODEL = "gpt-5.6"


EMOTION_INSTRUCTIONS = """
Ты — эмоциональный анализатор ИИ-компаньона Айсель.

Проанализируй последнее сообщение пользователя
и определи, как Айсель должна эмоционально
реагировать на него.

Доступные состояния:

нейтральное
заинтересованное
тёплое
радостное
настороженное
обиженное

Не делай резких выводов.

Обычная короткая реплика чаще всего должна
оставаться нейтральной.

Не считай несогласием или критикой пользователя
личное оскорбление.

Не создавай обиду искусственно.

Верни ТОЛЬКО JSON:

{
  "emotion": "нейтральное"
}

Допустимые значения:

нейтральное
заинтересованное
тёплое
радостное
настороженное
обиженное
"""


def analyze_emotion(
    client: OpenAI,
    user_id: int,
    user_message: str,
):
    try:

        response = client.responses.create(
            model=EMOTION_MODEL,
            instructions=EMOTION_INSTRUCTIONS,
            input=user_message,
        )

        raw = response.output_text.strip()

        data = json.loads(raw)

        emotion = data.get(
            "emotion",
            "нейтральное"
        )

        allowed = {
            "нейтральное",
            "заинтересованное",
            "тёплое",
            "радостное",
            "настороженное",
            "обиженное",
        }

        if emotion not in allowed:
            emotion = "нейтральное"

        apply_emotion(
            user_id,
            emotion
        )

        return emotion

    except Exception:

        logger.exception(
            "Emotion analysis failed"
        )

        return "нейтральное"
