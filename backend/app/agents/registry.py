"""Agent registry module."""

from typing import Dict, List, Optional
from backend.app.schemas.agents import AgentContract


class AgentRegistry:
    """Registry maintaining active agent declarations."""

    def __init__(self):
        self._agents: Dict[str, AgentContract] = {}

    def register(self, agent: AgentContract) -> None:
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> Optional[AgentContract]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[AgentContract]:
        return list(self._agents.values())
