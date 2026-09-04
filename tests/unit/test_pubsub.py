from datetime import UTC, datetime, timedelta


def test_publish_is_idempotent_and_delivery_is_acknowledged_once(system):
    first = system.message_bus.publish(
        topic="building.events",
        message_type="building.request.detected",
        payload={"ticket_id": "TKT-IDEMPOTENT", "request": {"subject": "Gym hours", "description": "When does it close?", "requester": "Resident", "location_id": "BLDG-A"}},
        correlation_id="CORR-IDEMPOTENT",
        idempotency_key="BUILDING-IDEMPOTENT",
        message_id="MSG-IDEMPOTENT",
    )
    second = system.message_bus.publish(
        topic="building.events",
        message_type="building.request.detected",
        payload=first.payload,
        correlation_id="CORR-IDEMPOTENT",
        idempotency_key="BUILDING-IDEMPOTENT",
        message_id="MSG-IDEMPOTENT",
    )

    assert first.message_id == second.message_id
    deliveries = system.message_bus.pull("operations.intake", limit=10)
    assert len(deliveries) == 1
    system.message_bus.acknowledge(deliveries[0])
    assert system.message_bus.pull("operations.intake", limit=10) == []
    assert system.message_bus.stats()["completed"] == 1


def test_delivery_retries_with_backoff_then_moves_to_dead_letter(system):
    system.message_bus.publish(
        topic="workflow.commands",
        message_type="unsupported",
        payload={"job": {}},
        correlation_id="CORR-RETRY",
        idempotency_key="RETRY",
        message_id="MSG-RETRY",
    )
    now = datetime.now(UTC)
    for attempt in range(3):
        delivery = system.message_bus.pull(
            "operations.workflow", now=now + timedelta(minutes=attempt), limit=1
        )[0]
        dead_lettered = system.message_bus.reject(
            delivery, RuntimeError("temporary failure"), now=now + timedelta(minutes=attempt)
        )
        assert dead_lettered is (attempt == 2)

    stats = system.message_bus.stats()
    assert stats["dead_letters"] == 1
    assert stats["retrying"] == 0
