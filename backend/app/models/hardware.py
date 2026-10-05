"""Lightweight hardware capability probe."""

import os
import platform
from typing import Optional
from pydantic import BaseModel


class HardwareSnapshot(BaseModel):
    """Snapshot of system hardware resources."""

    cpu_count: int
    cpu_architecture: str
    ram_total_gb: Optional[float] = None
    ram_available_gb: Optional[float] = None
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    gpu_memory_total_gb: Optional[float] = None
    gpu_memory_free_gb: Optional[float] = None


def _get_ram_info() -> tuple[Optional[float], Optional[float]]:
    """Safe extraction of RAM information without hard dependencies."""
    # Attempt psutil if available
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        avail_gb = round(mem.available / (1024**3), 2)
        return total_gb, avail_gb
    except Exception:
        pass

    # Windows fallback via ctypes
    if platform.system() == "Windows":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = round(stat.ullTotalPhys / (1024**3), 2)
                avail_gb = round(stat.ullAvailPhys / (1024**3), 2)
                return total_gb, avail_gb
        except Exception:
            pass

    return None, None


def _get_gpu_info() -> tuple[bool, Optional[str], Optional[float], Optional[float]]:
    """Safe probe for GPU capability across PyTorch, Apple Silicon Metal, and system CLI."""
    # 1. PyTorch CUDA / ROCm
    try:
        import torch

        if hasattr(torch, "cuda") and torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                total_gb = round(props.total_memory / (1024**3), 2)
                free_gb = None
                try:
                    free_bytes, _ = torch.cuda.mem_get_info(0)
                    free_gb = round(free_bytes / (1024**3), 2)
                except Exception:
                    pass
                return True, name, total_gb, free_gb
        
        # Apple Silicon Metal Performance Shaders (MPS)
        if hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return True, "Apple Silicon GPU (Metal / MPS)", None, None
    except Exception:
        pass

    # 2. System CLI fallback: nvidia-smi
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in first_line.split(",")]
            if parts:
                name = parts[0]
                total_gb = round(float(parts[1]) / 1024, 2) if len(parts) > 1 and parts[1].replace(".", "").isdigit() else None
                free_gb = round(float(parts[2]) / 1024, 2) if len(parts) > 2 and parts[2].replace(".", "").isdigit() else None
                return True, name, total_gb, free_gb
    except Exception:
        pass

    return False, None, None, None


def probe_hardware() -> HardwareSnapshot:
    """Probe CPU, RAM, and GPU hardware capabilities safely."""
    cpu_count = os.cpu_count() or 1
    cpu_arch = platform.machine() or "unknown"
    ram_total, ram_avail = _get_ram_info()
    gpu_avail, gpu_name, gpu_total, gpu_free = _get_gpu_info()

    return HardwareSnapshot(
        cpu_count=cpu_count,
        cpu_architecture=cpu_arch,
        ram_total_gb=ram_total,
        ram_available_gb=ram_avail,
        gpu_available=gpu_avail,
        gpu_name=gpu_name,
        gpu_memory_total_gb=gpu_total,
        gpu_memory_free_gb=gpu_free,
    )
