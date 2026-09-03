from __future__ import annotations

from backend.app.system import build_system


def main() -> None:
    system = build_system()
    tickets = system.tickets.seed_demo()
    print(f"Seeded {len(tickets)} tickets in {system.settings.database_path}")


if __name__ == "__main__":
    main()
