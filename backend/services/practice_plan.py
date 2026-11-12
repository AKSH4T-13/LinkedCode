"""Choose practice automatically from the recent accepted-submission sample."""
from collections import Counter


def build_practice_plan(profile):
    questions = profile.get("analyzed_questions", [])[:20]
    topics = Counter()
    difficulties = Counter()
    for question in questions:
        difficulty = question.get("difficulty")
        if difficulty in ("Easy", "Medium", "Hard"):
            difficulties[difficulty] += 1
        for topic in question.get("topics", []):
            name = topic.get("name") if isinstance(topic, dict) else topic
            if name:
                topics[name] += 1
    if not topics:
        frequency = profile.get("topic_frequency", {})
        if isinstance(frequency, dict):
            topics.update({key: value for key, value in frequency.items() if isinstance(value, (int, float)) and value > 0})
    if not difficulties:
        difficulties.update({key: value for key, value in profile.get("difficulty_distribution", {}).items()
                             if key in ("Easy", "Medium", "Hard") and isinstance(value, (int, float)) and value > 0})
    # Match the demonstrated level; accepted submissions alone cannot establish weaknesses.
    difficulty = max(difficulties, key=lambda key: (difficulties[key], key == "Medium")) if difficulties else "Easy"
    return {"difficulty": difficulty, "topics": [name for name, _ in topics.most_common(2)] or ["Array"],
            "sample_size": len(questions), "source": "recent_accepted_submissions"}
