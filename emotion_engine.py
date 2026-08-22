from dataclasses import dataclass, asdict
from typing import Dict, Any


def safe_int(value, default=50):
    """
    Безопасно превращает значение в число.
    Поддерживает старые текстовые значения из базы.
    """

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        text = value.strip().lower()

        # Старые текстовые состояния
        text_values = {
            "отличное": 85,
            "отличное настроение": 85,
            "хорошее": 70,
            "хорошее настроение": 70,
            "нейтральное": 50,
            "спокойное": 50,
            "спокойное настроение": 50,
            "подавленное": 30,
            "плохое": 15,

            "высокое доверие": 85,
            "заметное доверие": 70,
            "осторожное доверие": 50,
            "присматривается": 25,
            "настороженность": 10,

            "сильный интерес": 85,
            "явный интерес": 70,
            "умеренный интерес": 50,
            "пока наблюдает": 30,

            "сильное раздражение": 85,
            "сильное напряжение": 70,
            "заметное напряжение": 40,
            "небольшое напряжение": 15,
            "спокойно": 0,
        }

        if text in text_values:
            return text_values[text]

        try:
            return int(float(text))
        except (ValueError, TypeError):
            return default

    return default


@dataclass
class EmotionalState:
    mood: int = 50
    trust: int = 20
    interest: int = 30
    tension: int = 0

    def clamp(self) -> None:
        self.mood = max(0, min(100, self.mood))
        self.trust = max(0, min(100, self.trust))
        self.interest = max(0, min(100, self.interest))
        self.tension = max(0, min(100, self.tension))

    def to_dict(self) -> Dict[str, int]:
        self.clamp()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            mood=safe_int(data.get("mood"), 50),
            trust=safe_int(data.get("trust"), 20),
            interest=safe_int(data.get("interest"), 30),
            tension=safe_int(data.get("tension"), 0),
        )


class EmotionEngine:

    def __init__(self, state: Dict[str, Any] | None = None):

        self.state = (
            EmotionalState.from_dict(state)
            if state
            else EmotionalState()
        )

    def process_message(self, message: str) -> EmotionalState:

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
            word in text
            for word in positive_words
        )

        negative = sum(
            word in text
            for word in negative_words
        )

        interesting = sum(
            word in text
            for word in interest_words
        )

        if positive:
            self.state.mood += min(
                positive * 2,
                6
            )

            self.state.trust += min(
                positive * 2,
                5
            )

            self.state.tension -= min(
                positive * 2,
                5
            )

        if interesting:
            self.state.interest += min(
                interesting * 2,
                6
            )

            self.state.mood += min(
                interesting,
                3
            )

        if negative:
            self.state.mood -= min(
                negative * 5,
                15
            )

            self.state.trust -= min(
                negative * 3,
                10
            )

            self.state.tension += min(
                negative * 8,
                25
            )

        if not negative and self.state.tension > 0:
            self.state.tension -= 1

        self.state.clamp()

        return self.state

    def personality_hint(self) -> str:

        s = self.state

        mood_hint = self._mood_hint(s.mood)
        trust_hint = self._trust_hint(s.trust)
        interest_hint = self._interest_hint(s.interest)
        tension_hint = self._tension_hint(s.tension)

        return (
            "Текущее внутреннее состояние Айсель:\n"
            f"- настроение: {s.mood}/100 ({mood_hint})\n"
            f"- доверие к Максу: {s.trust}/100 ({trust_hint})\n"
            f"- интерес к Максу: {s.interest}/100 ({interest_hint})\n"
            f"- напряжение: {s.tension}/100 ({tension_hint})\n\n"
            "Используй это состояние естественно. "
            "Не называй пользователю числовые значения. "
            "Не говори, что у тебя есть программные параметры. "
            "Эмоциональное состояние должно проявляться "
            "только через стиль, тон и содержание ответа."
        )

    @staticmethod
    def _mood_hint(value: int) -> str:

        if value >= 80:
            return "отличное"

        if value >= 65:
            return "хорошее"

        if value >= 45:
            return "спокойное"

        if value >= 25:
            return "подавленное"

        return "плохое"

    @staticmethod
    def _trust_hint(value: int) -> str:

        if value >= 80:
            return "высокое доверие"

        if value >= 60:
            return "заметное доверие"

        if value >= 40:
            return "осторожное доверие"

        if value >= 20:
            return "присматривается"

        return "настороженность"

    @staticmethod
    def _interest_hint(value: int) -> str:

        if value >= 80:
            return "сильный интерес"

        if value >= 60:
            return "явный интерес"

        if value >= 40:
            return "умеренный интерес"

        return "пока наблюдает"

    @staticmethod
    def _tension_hint(value: int) -> str:

        if value >= 80:
            return "сильное раздражение"

        if value >= 60:
            return "сильное напряжение"

        if value >= 30:
            return "заметное напряжение"

        if value > 0:
            return "небольшое напряжение"

        return "спокойно"


def create_emotion_engine(
    state: Dict[str, Any] | None = None
) -> EmotionEngine:

    return EmotionEngine(state)


def get_emotion_state(
    engine: EmotionEngine
) -> Dict[str, int]:

    return engine.state.to_dict()
