"""Abstract interfaces for Internal Agents, Background Scheduler, and Visible Log Store."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    AgentLogEntry,
    AgentRunReport,
    AgentType,
)


class BaseVisibleLogStore(ABC):
    """Abstract append-only store for live visible agent log entries."""

    @abstractmethod
    def append_log(self, entry: AgentLogEntry) -> None:
        """Appends a new visible log record."""
        pass

    @abstractmethod
    def query_logs(
        self, agent_type: Optional[AgentType] = None, limit: int = 50
    ) -> List[AgentLogEntry]:
        """Queries recorded log entries filtered by agent and sorted by recency."""
        pass


class BaseInternalAgent(ABC):
    """Abstract background agent implementing an autonomous monitoring/review cycle."""

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """The distinct AgentType identifier."""
        pass

    @abstractmethod
    def run_cycle(self) -> AgentRunReport:
        """Executes one evaluation cycle and logs activity to the visible store."""
        pass


class BaseAgentScheduler(ABC):
    """Manages scheduled background execution loops for internal agents."""

    @abstractmethod
    def register_agent(self, agent: BaseInternalAgent, interval_seconds: float = 60.0) -> None:
        """Registers an agent with a periodic execution frequency."""
        pass

    @abstractmethod
    def trigger_cycle(self, agent_type: AgentType) -> AgentRunReport:
        """Manually runs an agent cycle on-demand."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Starts the background scheduling threads."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Gracefully halts all background scheduler threads."""
        pass
