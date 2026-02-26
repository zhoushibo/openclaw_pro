"""
Executors Package for OpenClaw Pro
"""

from .base import BaseExecutor, ExecutionResult
from .local import LocalExecutor

# SSH and WinRM executors require external dependencies
try:
    from .ssh import SSHExecutor
    _HAS_SSH = True
except ImportError:
    _HAS_SSH = False
    SSHExecutor = None

try:
    from .winrm import WinRMExecutor
    _HAS_WINRM = True
except ImportError:
    _HAS_WINRM = False
    WinRMExecutor = None

__all__ = [
    "BaseExecutor",
    "ExecutionResult",
    "LocalExecutor",
]

if _HAS_SSH:
    __all__.append("SSHExecutor")

if _HAS_WINRM:
    __all__.append("WinRMExecutor")
