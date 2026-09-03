from __future__ import annotations

from pathlib import Path
import re


PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
]
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "data"}


def main() -> None:
    findings: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts) or path.name == ".env.example":
            continue
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(errors="ignore")
        if any(pattern.search(text) for pattern in PATTERNS):
            findings.append(str(path))
    if findings:
        raise SystemExit("Potential secrets found in: " + ", ".join(findings))
    print("PASS no credential-shaped secrets detected in source files")


if __name__ == "__main__":
    main()
