from __future__ import annotations

from dataclasses import dataclass

from backend.app.agents.ports import AgentRuntime
from backend.app.agents.runtime import runtime_from_settings
from backend.app.config import Settings
from backend.app.messaging.local import SQLiteDurablePubSub
from backend.app.messaging.ports import MessageBusPort
from backend.app.repositories.ports import OperationsRepository
from backend.app.repositories.sqlite import SQLiteOperationsRepository
from backend.app.services.events import LocalEventBus
from backend.app.services.operations import OperationsMessageService
from backend.app.services.simulation import BuildingSimulationService
from backend.app.services.tickets import TicketService
from backend.app.services.workflow import WorkflowService
from backend.app.tools.building import LocalBuildingProvider
from backend.app.tools.knowledge import LocalKnowledgeProvider
from backend.app.tools.notifications import LocalNotificationProvider
from backend.app.tools.ports import BuildingPort, KnowledgePort, NotificationPort, WorkOrderPort
from backend.app.tools.work_orders import LocalWorkOrderProvider


@dataclass
class ApplicationSystem:
    """Composition root: replace adapters here, never inside workflow logic."""

    settings: Settings
    repository: OperationsRepository
    events: LocalEventBus
    message_bus: MessageBusPort
    agent: AgentRuntime
    knowledge: KnowledgePort
    building: BuildingPort
    notifications: NotificationPort
    work_orders: WorkOrderPort
    tickets: TicketService
    workflow: WorkflowService
    operations: OperationsMessageService
    simulation: BuildingSimulationService

    def providers(self) -> dict[str, str]:
        return {
            "agent_runtime": self.agent.name,
            "agent_provider": self.agent.provider,
            "agent_model": self.agent.model_id,
            "persistence": type(self.repository).__name__,
            "scheduler": "SQLiteLeasedJobWorker",
            "message_bus": type(self.message_bus).__name__,
            "knowledge": type(self.knowledge).__name__,
            "building": type(self.building).__name__,
            "notifications": type(self.notifications).__name__,
            "work_orders": type(self.work_orders).__name__,
        }


def build_system(settings: Settings | None = None) -> ApplicationSystem:
    settings = settings or Settings.from_env()
    if settings.app_env not in {"local", "aws_ec2"}:
        raise ValueError(
            "Use APP_ENV=local or aws_ec2. Stage 1 retains the SQLite adapters on one persistent host."
        )
    if settings.app_env == "aws_ec2" and settings.agent_runtime not in {"bedrock", "strands", "agentcore"}:
        raise ValueError("AWS deployment requires Bedrock directly or through AgentCore; OpenAI/deterministic execution is disabled.")

    repository = SQLiteOperationsRepository(settings.database_path)
    repository.initialize()
    events = LocalEventBus()
    message_bus = SQLiteDurablePubSub(
        repository,
        max_attempts=settings.message_max_attempts,
        base_retry_seconds=settings.message_retry_base_seconds,
        lease_seconds=settings.message_lease_seconds,
    )
    agent = runtime_from_settings(settings)
    knowledge = LocalKnowledgeProvider()
    building = LocalBuildingProvider(repository)
    notifications = LocalNotificationProvider()
    work_orders = LocalWorkOrderProvider(repository)
    tickets = TicketService(
        repository,
        events,
        notifications,
        intake_delay_seconds=settings.intake_delay_seconds,
    )
    workflow = WorkflowService(
        repository,
        agent,
        knowledge,
        building,
        notifications,
        work_orders,
        events,
        message_bus,
        agent_analysis_seconds=settings.agent_analysis_seconds,
        action_delay_seconds=settings.action_delay_seconds,
        technician_delay_seconds=settings.technician_delay_seconds,
        verification_delay_seconds=settings.verification_delay_seconds,
    )
    operations = OperationsMessageService(message_bus, tickets, workflow)
    simulation = BuildingSimulationService(
        repository,
        tickets,
        building,
        events,
        message_bus,
        enabled=settings.simulation_enabled,
        interval_seconds=settings.simulation_interval_seconds,
    )
    return ApplicationSystem(
        settings=settings,
        repository=repository,
        events=events,
        message_bus=message_bus,
        agent=agent,
        knowledge=knowledge,
        building=building,
        notifications=notifications,
        work_orders=work_orders,
        tickets=tickets,
        workflow=workflow,
        operations=operations,
        simulation=simulation,
    )
