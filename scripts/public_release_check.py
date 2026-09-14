"""Check Git history and intended public source without printing secret values."""
from pathlib import Path
import re
import subprocess


PATTERNS = [
    re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
]


def main():
    root = Path(__file__).resolve().parent.parent
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    violations = []
    for name in filter(None, tracked):
        path = Path(name)
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".db", ".pem", ".key"} or path.parts[0] in {"artifacts", ".deployment"}:
            violations.append("Forbidden tracked path: " + name)
    candidates = {root / name for name in tracked if name}
    for directory in ["backend", "frontend/src", "deploy", "tests"]:
        candidates.update(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    candidates.update(root / "scripts" / name for name in ["deploy_stage1.py", "public_release_check.py"])
    for path in candidates:
        if path.is_file() and any(pattern.search(path.read_bytes()) for pattern in PATTERNS):
            violations.append("Credential pattern in source: " + str(path.relative_to(root)))
    # Inspect every reachable historical blob. Report object IDs only, never values.
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=root).decode().splitlines()
    seen = set()
    for line in objects:
        oid = line.split(" ", 1)[0]
        if oid in seen:
            continue
        seen.add(oid)
        if subprocess.check_output(["git", "cat-file", "-t", oid], cwd=root).strip() != b"blob":
            continue
        data = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=root)
        if any(pattern.search(data) for pattern in PATTERNS):
            violations.append("Credential pattern in historical object: " + oid)
    if violations:
        raise SystemExit("\n".join(violations))
    print(f"PASS source and {len(seen)} historical Git objects checked; no credential patterns found.")
    print("Heuristic check only; review the exact staged diff before publishing. Artifacts and private deployment state remain excluded.")


if __name__ == "__main__":
    main()
