from memory import get_relationship, update_relationship


EMOTIONS = {
    "нейтральное": {
        "trust": 0,
        "closeness": 0,
    },
    "заинтересованное": {
        "trust": 1,
        "closeness": 1,
    },
    "тёплое": {
        "trust": 2,
        "closeness": 2,
    },
    "радостное": {
        "trust": 1,
        "closeness": 2,
    },
    "настороженное": {
        "trust": -1,
        "closeness": -1,
    },
    "обиженное": {
        "trust": -3,
        "closeness": -2,
    },
}


def clamp(value):
    return max(0, min(100, value))


def apply_emotion(
    user_id,
    emotion,
):
    relationship = get_relationship(user_id)

    if emotion not in EMOTIONS:
        emotion = "нейтральное"

    effect = EMOTIONS[emotion]

    trust = clamp(
        relationship["trust"]
        + effect["trust"]
    )

    closeness = clamp(
        relationship["closeness"]
        + effect["closeness"]
    )

    update_relationship(
        user_id,
        trust=trust,
        closeness=closeness,
        mood=emotion,
    )


def get_emotional_state(user_id):
    relationship = get_relationship(user_id)

    return {
        "mood": relationship["mood"],
        "trust": relationship["trust"],
        "closeness": relationship["closeness"],
    }
