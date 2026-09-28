"""Test hardware capability probe."""

from unittest.mock import patch
from backend.app.models.hardware import probe_hardware, HardwareSnapshot


def test_probe_hardware_real():
    """Verify hardware probe executes safely and returns valid snapshot."""
    snapshot = probe_hardware()
    assert isinstance(snapshot, HardwareSnapshot)
    assert snapshot.cpu_count >= 1
    assert len(snapshot.cpu_architecture) > 0
    # ram should be reported if available on system
    assert snapshot.ram_total_gb is None or snapshot.ram_total_gb > 0


def test_probe_hardware_cpu_only_fallback():
    """Verify hardware probe safely handles absence of GPU without error."""
    with patch("backend.app.models.hardware._get_gpu_info", return_value=(False, None, None, None)):
        snapshot = probe_hardware()
        assert snapshot.gpu_available is False
        assert snapshot.gpu_name is None
        assert snapshot.gpu_memory_total_gb is None
