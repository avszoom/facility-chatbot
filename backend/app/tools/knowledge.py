from __future__ import annotations

import json
from pathlib import Path
import re


STOP_WORDS = {
    "about", "and", "building", "does", "from", "happened", "have", "help",
    "need", "please", "question", "request", "something", "tell", "that", "there",
    "this", "what", "when", "where", "with", "would",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


class LocalKnowledgeProvider:
    """Versioned local knowledge. Replace with S3/OpenSearch/Bedrock Knowledge Bases later."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path(__file__).parents[1] / "seed" / "knowledge" / "building.json")

    def search(self, query: str) -> dict[str, str] | None:
        records = json.loads(self.path.read_text())
        terms = _tokens(query)
        if not terms:
            return None
        scored = []
        for record in records:
            haystack = f"{record['title']} {record['content']} {' '.join(record['keywords'])}"
            score = len(terms & _tokens(haystack))
            if score:
                scored.append((score, record))
        if not scored:
            return None
        record = max(scored, key=lambda item: item[0])[1]
        return {
            "answer": record["content"],
            "source": record["source"],
            "title": record["title"],
        }
