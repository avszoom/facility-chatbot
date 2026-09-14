import pytest

from backend.app.tools.knowledge import LocalKnowledgeProvider


@pytest.mark.parametrize("query, expected", [
    ("What time does the gym close?", "11:00 PM"),
    ("Where can I collect my parcel?", "parcel room"),
    ("How do I reserve the sky lounge?", "concierge"),
    ("When are quiet hours?", "10:00 PM to 8:00 AM"),
    ("Where are the laundry rooms?", "floors 3 through 9"),
    ("I lost my fob", "verifies resident identity"),
])
def test_resident_handbook_answers_have_sources(query, expected):
    result = LocalKnowledgeProvider().search(query)
    assert result and expected in result["answer"]
    assert result["source"].startswith("Northstar Residences")
