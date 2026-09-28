"""Phase 0 Tests: Architecture & Configuration Contract."""

import pytest
from backend.app.config.settings import Settings
from backend.app.models.registry import ModelRegistry
from backend.app.schemas.agents import AgentContract, A2AMessage
from backend.app.schemas.tools import ToolContract


def test_default_settings():
    """Verify default configuration has USE_HIGH_LEVEL_MODELS=false and SOVEREIGN_MODE=true."""
    settings = Settings()
    assert settings.USE_HIGH_LEVEL_MODELS is False
    assert settings.SOVEREIGN_MODE is True
    assert settings.ALLOW_EXTERNAL_NETWORK is False
    assert settings.ALLOW_CLOUD_MODELS is False
    assert settings.MODEL_BASE_URL == "http://127.0.0.1:8000/v1"


def test_small_profile_resolution():
    """Verify that with default settings (USE_HIGH_LEVEL_MODELS=false), small profile models are resolved."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=False)
    registry = ModelRegistry(settings=settings)

    assert registry.active_profile_name == "small"
    profile = registry.get_active_profile()
    assert profile.profile == "small"

    # General reasoning model
    general_model = registry.resolve_model_name("general_reasoning")
    assert general_model == "Qwen/Qwen3-4B"

    # Vision model
    vision_model = registry.resolve_model_name("vision_document")
    assert vision_model == "Qwen/Qwen3-VL-4B-Instruct"

    # Coding model
    coding_model = registry.resolve_model_name("coding")
    assert coding_model == "Qwen/Qwen2.5-Coder-3B-Instruct"


def test_high_profile_resolution():
    """Verify that toggling ONLY USE_HIGH_LEVEL_MODELS=true switches to high profile models."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=True)
    registry = ModelRegistry(settings=settings)

    assert registry.active_profile_name == "high"
    profile = registry.get_active_profile()
    assert profile.profile == "high"

    # General reasoning model
    general_model = registry.resolve_model_name("general_reasoning")
    assert general_model == "Qwen/Qwen3-30B-A3B"

    # Vision model
    vision_model = registry.resolve_model_name("vision_document")
    assert vision_model == "Qwen/Qwen3-VL-30B-A3B-Instruct"

    # Coding model
    coding_model = registry.resolve_model_name("coding")
    assert coding_model == "Qwen/Qwen3-Coder-30B-A3B-Instruct"


def test_agent_contract_schema():
    """Verify AgentContract schema adherence per AGENTS.md."""
    agent = AgentContract(
        agent_id="document_agent",
        description="Ingests documents and normalizes evidence",
        capabilities=["pdf_ingestion", "page_extraction", "evidence_normalization"],
        accepted_inputs=["pdf", "image"],
        produced_outputs=["evidence_object"],
        allowed_tools=["paddle_ocr", "read_file"],
        risk_class="LOW",
        max_retries=2,
    )
    assert agent.agent_id == "document_agent"
    assert "pdf_ingestion" in agent.capabilities

    # Structured A2A message test
    msg = A2AMessage(
        message_id="msg_001",
        task_id="task_100",
        sender="document_agent",
        receiver="knowledge_agent",
        type="REQUEST",
        payload={"query": "find sop"},
        provenance={"page": 1},
    )
    assert msg.sender == "document_agent"
    assert msg.type == "REQUEST"


def test_tool_contract_schema():
    """Verify ToolContract schema adherence."""
    tool = ToolContract(
        tool_id="read_file",
        name="Read File Tool",
        description="Reads contents of a file within sandbox",
        parameters={"path": {"type": "string"}},
        required_permissions=["file_read"],
        risk_level="LOW",
    )
    assert tool.tool_id == "read_file"
    assert tool.risk_level == "LOW"
