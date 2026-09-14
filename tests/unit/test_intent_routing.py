from backend.app.agents.specialists import roles_for
from backend.app.domain.models import TicketCreate


def test_model_completion_is_verified_and_escalation_keeps_its_reason(system, monkeypatch):
    import strands
    from types import SimpleNamespace
    from backend.app.agents.runtime import OpenAIStrandsRuntime
    from backend.app.config import Settings
    from backend.app.domain.models import CoordinatorDirective, SpecialistReport
    runtime = OpenAIStrandsRuntime(Settings(agent_runtime="openai", openai_api_key="stub"))
    monkeypatch.setattr(runtime, "_model", lambda: None)
    response = CoordinatorDirective(iteration=3, action="complete", objective="Finish", rationale="Readings recovered", state_summary="Repair checked")
    class FakeAgent:
        def __init__(self, **kwargs): pass
        def __call__(self, *args, **kwargs): return SimpleNamespace(structured_output=response)
    monkeypatch.setattr(strands, "Agent", FakeAgent)
    ticket = system.tickets.create(TicketCreate(subject="Warm room", description="Apartment is too warm", requester="Resident", location_id="BLDG-A-F04-APT-4B"))
    report = SpecialistReport(role="Verification Agent", objective="Check temperature", summary="Temperature normal")
    directive = runtime.coordinate(ticket, {"phase": "verification"}, [report], 3)
    assert directive.action == "verify"
    response = response.model_copy(update={"action": "escalate", "rationale": "Repair did not restore safe readings; facilities must inspect."})
    directive = runtime.coordinate(ticket, {"phase": "verification"}, [report], 3)
    assert directive.action == "escalate"
    assert directive.rationale == response.rationale


def test_nearby_alarm_does_not_remove_knowledge_role(system):
    ticket = system.tickets.create(TicketCreate(subject="Where does cardboard go?", description="Where should I recycle boxes?", requester="Resident", location_id="BLDG-A-F07-EAST"))
    roles = roles_for(ticket, {"knowledge_result": {"answer": "Recycling area"}, "building_facts": {"nearby_sensors": [{"state": "Critical"}]}})
    assert "Resident Knowledge Agent" in roles
    assert "Sensor Intelligence Agent" not in roles


def test_coordinator_initial_context_does_not_fetch_data(system, monkeypatch):
    ticket = system.tickets.create(TicketCreate(subject="Question about recycling", description="Where do cardboard boxes go?", requester="Resident", location_id="BLDG-A-F07-EAST"))
    def forbidden(*args):
        raise AssertionError("Coordinator must choose what to retrieve first")
    monkeypatch.setattr(system.building, "investigation_context", forbidden)
    monkeypatch.setattr(system.knowledge, "search", forbidden)
    context = system.workflow._context(ticket, "investigation", "coordinator")
    assert context["building_facts"] == {}
    assert context["knowledge_result"] is None
