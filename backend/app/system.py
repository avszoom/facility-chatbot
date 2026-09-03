from __future__ import annotations

from dataclasses import dataclass

from backend.app.agents.ports import AgentRuntime
from backend.app.agents.runtime import runtime_from_settings
from backend.app.config import Settings
from backend.app.repositories.ports import OperationsRepository
from backend.app.repositories.sqlite import SQLiteOperationsRepository
from backend.app.services.events import LocalEventBus
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
    agent: AgentRuntime
    knowledge: KnowledgePort
    building: BuildingPort
    notifications: NotificationPort
    work_orders: WorkOrderPort
    tickets: TicketService
    workflow: WorkflowService

    def providers(self) -> dict[str, str]:
        return {
            "agent_runtime": self.agent.name,
            "persistence": type(self.repository).__name__,
            "scheduler": "SQLiteLeasedJobWorker",
            "knowledge": type(self.knowledge).__name__,
            "building": type(self.building).__name__,
            "notifications": type(self.notifications).__name__,
            "work_orders": type(self.work_orders).__name__,
        }


def build_system(settings: Settings | None = None) -> ApplicationSystem:
    settings = settings or Settings.from_env()
    if settings.app_env != "local":
        raise ValueError(
            "Only APP_ENV=local is implemented in this build. AWS adapters plug in at this composition root."
        )

    repository = SQLiteOperationsRepository(settings.database_path)
    repository.initialize()
    events = LocalEventBus()
    agent = runtime_from_settings(settings)
    knowledge = LocalKnowledgeProvider()
    building = LocalBuildingProvider(repository)
    notifications = LocalNotificationProvider()
    work_orders = LocalWorkOrderProvider(repository)
    tickets = TicketService(repository, events)
    workflow = WorkflowService(
        repository,
        agent,
        knowledge,
        building,
        notifications,
        work_orders,
        events,
        technician_delay_seconds=settings.technician_delay_seconds,
        verification_delay_seconds=settings.verification_delay_seconds,
    )
    return ApplicationSystem(
        settings=settings,
        repository=repository,
        events=events,
        agent=agent,
        knowledge=knowledge,
        building=building,
        notifications=notifications,
        work_orders=work_orders,
        tickets=tickets,
        workflow=workflow,
    )
