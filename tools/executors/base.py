"""
执行器基类模块
定义本地/SSH/WinRM 执行器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

import logging

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """执行结果模型
    统一所有执行器的返回格式
    """
    ok: bool = False
    stdout: str = ""
    stderr: str = ""
    content: str = ""
    path: str = ""
    error: str = ""
    returncode: int = 0
    target: str = "local"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.dict()

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.ok


class BaseExecutor(ABC):
    """执行器抽象基类
    所有执行器必须继承此类
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.connected = False
        self._allowed_roots: List[str] = []
        self._blocked_patterns: List[str] = []

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def execute_command(self, command: str, timeout: int = 60) -> ExecutionResult:
        """执行 Shell 命令"""
        pass

    @abstractmethod
    async def read_file(self, path: str) -> ExecutionResult:
        """读取文件"""
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入文件"""
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    async def list_directory(self, path: str) -> ExecutionResult:
        """列出目录内容"""
        pass

    def set_allowed_roots(self, roots: List[str]):
        """设置允许的根目录"""
        self._allowed_roots = roots

    def set_blocked_patterns(self, patterns: List[str]):
        """设置禁止的路径模式"""
        self._blocked_patterns = patterns

    def get_allowed_roots(self) -> List[str]:
        """获取允许的根目录"""
        return self._allowed_roots

    def get_blocked_patterns(self) -> List[str]:
        """获取禁止的路径模式"""
        return self._blocked_patterns

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, connected={self.connected})"
