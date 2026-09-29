"""Unit tests for Coding Agent registration, model resolution, AST inspection, and repairs."""

import pytest
from backend.app.agents.registry import AgentRegistry, get_agent_registry
from backend.app.models.registry import ModelRegistry
from backend.app.config.settings import Settings
from backend.app.coding import CodingAgent, CodingTask, CodeGenerationResult


def test_coding_agent_registered_with_contracts():
    """Verify coding_agent is registered in AgentRegistry with required capabilities and tools."""
    registry = AgentRegistry()
    assert registry.exists("coding_agent")
    contract = registry.get("coding_agent")
    assert contract is not None
    assert "code_generation" in contract.capabilities
    assert "code_execution" in contract.capabilities
    assert "coding" in contract.capabilities
    assert "sandbox_execute" in contract.allowed_tools
    assert contract.risk_class == "MEDIUM"


def test_coding_agent_dynamic_model_resolution_small_profile():
    """Verify CodingAgent dynamically resolves small profile coding model."""
    reg = ModelRegistry()
    agent = CodingAgent(model_registry=reg)
    gen = agent.generate_code("Write a CSV parsing script")
    assert gen.model_name == "Qwen/Qwen2.5-Coder-3B-Instruct"
    assert gen.model_id == "qwen-coder-small"
    assert "calculate_stats" in gen.code


def test_coding_agent_dynamic_model_resolution_high_profile():
    """Verify CodingAgent dynamically resolves high profile coding model."""
    settings = Settings(USE_HIGH_LEVEL_MODELS=True)
    reg = ModelRegistry(settings=settings)
    agent = CodingAgent(model_registry=reg)
    gen = agent.generate_code("Write a script")
    assert gen.model_name == "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    assert gen.model_id == "qwen3-coder-high"


def test_coding_agent_ast_inspection_valid_code():
    """Verify AST inspection correctly identifies functions, imports, and valid syntax."""
    agent = CodingAgent()
    code = (
        "import math\n"
        "from statistics import mean\n\n"
        "def compute_radius(area):\n"
        "    return math.sqrt(area / math.pi)\n"
    )
    insp = agent.inspect_code(code)
    assert insp.is_valid_syntax is True
    assert "math" in insp.imports
    assert "compute_radius" in insp.functions
    assert len(insp.security_flags) == 0


def test_coding_agent_ast_inspection_syntax_error():
    """Verify AST inspection flags syntax errors."""
    agent = CodingAgent()
    bad_code = "def broken(:"
    insp = agent.inspect_code(bad_code)
    assert insp.is_valid_syntax is False
    assert "SyntaxError" in (insp.syntax_error or "")


def test_coding_agent_ast_inspection_security_flag():
    """Verify AST inspection flags network imports."""
    agent = CodingAgent()
    code = "import urllib.request\nprint('hello')"
    insp = agent.inspect_code(code)
    assert insp.is_valid_syntax is True
    assert any("Network import detected" in flag for flag in insp.security_flags)


def test_coding_agent_explain_and_modify():
    """Verify code explanation and modification helpers."""
    agent = CodingAgent()
    code = "def add(a, b): return a + b"
    explanation = agent.explain_code(code)
    assert "add" in explanation

    modified = agent.modify_code(code, "add docstring")
    assert "add docstring" in modified


def test_coding_agent_replan_after_failure():
    """Verify replan_after_failure analyzes error and produces repaired code."""
    agent = CodingAgent()
    broken_code = "def divide(a, b):\n    return a / 0\n\ndivide(10, 0)\n"
    exec_res = agent.run_in_sandbox(broken_code, task_id="test_replan")
    assert exec_res.status == "FAILED"


    repair_res = agent.replan_after_failure(broken_code, exec_res)
    assert repair_res.repaired_code != broken_code
    assert "/ 1" in repair_res.repaired_code or "HANDLED_ERROR" in repair_res.repaired_code


def test_coding_agent_end_to_end_sandbox_run():
    """Verify CodingAgent generates, executes in sandbox, and verifies output."""
    agent = CodingAgent()
    gen = agent.generate_code("Calculate statistics")
    exec_res = agent.run_in_sandbox(
        code=gen.code,
        task_id="t_e2e_code",
        expected_output_patterns=[r"STATISTICS_CALCULATED_OK|COUNT"],
    )
    assert exec_res.status == "SUCCESS"
    assert exec_res.verification_status is not None
    assert exec_res.verification_status.is_verified is True
