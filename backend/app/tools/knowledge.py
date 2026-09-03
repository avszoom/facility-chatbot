from __future__ import annotations

import json
from pathlib import Path


class LocalKnowledgeProvider:
    """Versioned local knowledge. Replace with S3/OpenSearch/Bedrock Knowledge Bases later."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path(__file__).parents[1] / "seed" / "knowledge" / "building.json")

    def search(self, query: str) -> dict[str, str] | None:
        records = json.loads(self.path.read_text())
        terms = {token.strip("?.,!").lower() for token in query.split() if len(token) > 2}
        scored = []
        for record in records:
            haystack = f"{record['title']} {record['content']} {' '.join(record['keywords'])}".lower()
            score = sum(term in haystack for term in terms)
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
