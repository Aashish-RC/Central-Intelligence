"""Abstract interfaces for Pheonix Agent Builder components."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    AgentBuildResult,
    AgentExecutionResult,
    AgentRulesBinding,
    AgentSpecification,
    AgentToolBinding,
    DescribeAgentRequest,
)


class BaseToolMatcher(ABC):
    """Interface for resolving relevant tools from natural language descriptions."""

    @abstractmethod
    def match_tools(self, description_text: str) -> AgentToolBinding:
        pass


class BaseRulesBinder(ABC):
    """Interface for dynamically binding permission modes and safety rules."""

    @abstractmethod
    def bind_rules(
        self, description_text: str, requested_mode: Optional[str] = None
    ) -> AgentRulesBinding:
        pass


class BaseDescribeToAgentCompiler(ABC):
    """Interface for compiling natural language requests into agent specifications."""

    @abstractmethod
    def compile_agent(self, request: DescribeAgentRequest) -> AgentBuildResult:
        pass


class BaseAgentInstantiator(ABC):
    """Interface for instantiating and executing a compiled agent specification."""

    @abstractmethod
    def execute_agent(
        self, spec: AgentSpecification, input_prompt: str
    ) -> AgentExecutionResult:
        pass
