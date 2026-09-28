"""Authoritative Agent Registry module for discovering and managing system agents."""

from typing import Dict, List, Optional
from backend.app.schemas.agents import AgentContract


class AgentRegistryError(Exception):
    """Base exception for agent registry operations."""
    pass


class DuplicateAgentError(AgentRegistryError):
    """Raised when registering an agent with an ID that already exists."""
    pass


class UnknownAgentError(AgentRegistryError):
    """Raised when an agent ID is not found in the registry."""
    pass


class InvalidRegistryDefinitionError(AgentRegistryError):
    """Raised when an agent definition has missing or invalid required metadata."""
    pass


def get_standard_agents() -> List[AgentContract]:
    """Return standard agent definitions specified in AGENTS.md."""
    return [
        AgentContract(
            agent_id="main_agent",
            name="Main Agent",
            description="Workflow coordinator: accepts task, maintains workflow state, delegates, aggregates, triggers verification, delivers artifacts",
            capabilities=["workflow_management", "planning", "delegation", "aggregation", "verification_trigger", "artifact_delivery"],
            accepted_inputs=["task_request"],
            produced_outputs=["plan", "aggregated_result", "delivered_artifact"],
            allowed_tools=[],
            risk_class="LOW",
            max_retries=2,
        ),
        AgentContract(
            agent_id="reasoning_agent",
            name="Reasoning Agent",
            description="Logical reasoning specialist for planning, decomposition, and structured reasoning",
            capabilities=["planning", "decomposition", "synthesis", "structured_reasoning", "reasoning"],
            accepted_inputs=["problem_statement", "task_context"],
            produced_outputs=["reasoning_plan", "synthesis"],
            allowed_tools=[],
            risk_class="LOW",
            max_retries=2,
        ),
        AgentContract(
            agent_id="document_agent",
            name="Document Agent",
            description="PDF/DOCX ingestion, page extraction, structure, and evidence normalization",
            capabilities=["pdf_ingestion", "docx_ingestion", "page_extraction", "document_structure", "evidence_normalization", "document_extraction"],
            accepted_inputs=["pdf", "docx"],
            produced_outputs=["normalized_evidence", "extracted_pages"],
            allowed_tools=["file_read", "ocr"],
            risk_class="LOW",
            max_retries=2,
        ),
        AgentContract(
            agent_id="vision_agent",
            name="Vision Agent",
            description="Image understanding, scanned page analysis, engineering drawings, and visual evidence",
            capabilities=["image_understanding", "scanned_page_analysis", "engineering_drawing_observation", "visual_evidence", "visual_analysis", "visual_reasoning"],
            accepted_inputs=["image", "drawing"],
            produced_outputs=["visual_observation", "spatial_evidence"],
            allowed_tools=["ocr"],
            risk_class="LOW",
            max_retries=2,
        ),
        AgentContract(
            agent_id="knowledge_agent",
            name="Knowledge Agent",
            description="Organizational knowledge retrieval, hybrid search, evidence ranking, and citations",
            capabilities=["knowledge_retrieval", "hybrid_search", "evidence_ranking", "citation_generation", "knowledge_search"],
            accepted_inputs=["query", "context"],
            produced_outputs=["citations", "ranked_evidence"],
            allowed_tools=["knowledge_search"],
            risk_class="LOW",
            max_retries=2,
        ),
        AgentContract(
            agent_id="coding_agent",
            name="Coding Agent",
            description="Reads/writes task files, generates code, executes tests in sandbox, repairs code",
            capabilities=["task_file_io", "code_generation", "sandbox_test_execution", "failure_inspection", "code_repair", "code_reasoning", "code_execution"],
            accepted_inputs=["coding_task", "test_specification"],
            produced_outputs=["source_code", "test_report", "repaired_code"],
            allowed_tools=["file_read", "file_write", "sandbox_execute"],
            risk_class="MEDIUM",
            max_retries=2,
        ),
        AgentContract(
            agent_id="data_agent",
            name="Data Agent",
            description="Reads CSV/XLSX, performs calculations, generates tables, produces calculation traces",
            capabilities=["csv_reading", "xlsx_reading", "calculation_execution", "table_generation", "calculation_trace", "data_analysis", "calculation"],
            accepted_inputs=["csv", "xlsx", "data_query"],
            produced_outputs=["calculation_trace", "data_table"],
            allowed_tools=["file_read", "file_write", "python_calculation"],
            risk_class="LOW",
            max_retries=2,
        ),
    ]


class AgentRegistry:
    """Authoritative registry maintaining active agent declarations and capabilities."""

    def __init__(self, populate_defaults: bool = True):
        self._agents: Dict[str, AgentContract] = {}
        if populate_defaults:
            for agent in get_standard_agents():
                self.register(agent)

    def register(self, agent: AgentContract, overwrite: bool = False) -> None:
        """Register an agent definition. Rejects duplicates unless overwrite=True."""
        if not agent.agent_id:
            raise InvalidRegistryDefinitionError("Agent must have a non-empty 'agent_id'.")
        if agent.agent_id in self._agents and not overwrite:
            raise DuplicateAgentError(f"Agent '{agent.agent_id}' is already registered.")

        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent by ID."""
        if agent_id not in self._agents:
            raise UnknownAgentError(f"Agent '{agent_id}' is not registered.")
        del self._agents[agent_id]

    def get(self, agent_id: str) -> Optional[AgentContract]:
        """Obtain agent definition by ID."""
        return self._agents.get(agent_id)

    def get_or_raise(self, agent_id: str) -> AgentContract:
        """Obtain agent definition by ID or raise UnknownAgentError."""
        agent = self.get(agent_id)
        if not agent:
            raise UnknownAgentError(f"Agent '{agent_id}' is not registered.")
        return agent

    def exists(self, agent_id: str) -> bool:
        """Check if an agent ID is registered."""
        return agent_id in self._agents

    def list(self) -> List[AgentContract]:
        """List all registered agents."""
        return list(self._agents.values())

    def list_all(self) -> List[AgentContract]:
        """Alias for list() maintained for backward compatibility."""
        return self.list()

    def find_by_capability(self, capability: str) -> List[AgentContract]:
        """Find all registered agents advertising a specific capability."""
        return [
            agent for agent in self._agents.values()
            if capability in agent.capabilities and agent.enabled
        ]

    def find_by_tool(self, tool_id: str) -> List[AgentContract]:
        """Find all registered agents permitted to use a specific tool."""
        return [
            agent for agent in self._agents.values()
            if tool_id in agent.allowed_tools and agent.enabled
        ]



# Global singleton instance
_default_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Obtain or initialize global AgentRegistry."""
    global _default_agent_registry
    if _default_agent_registry is None:
        _default_agent_registry = AgentRegistry()
    return _default_agent_registry


get_default_agents = get_standard_agents

