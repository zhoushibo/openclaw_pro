"""
连接管理器模块
管理所有机器的执行器连接池
"""

import asyncio
from typing import Dict, Optional, List, Type
import logging

from config import AgentConfig, MachineConfig
from tools.executors.base import BaseExecutor
from tools.executors.local import LocalExecutor
from tools.executors.ssh import SSHExecutor
from tools.executors.winrm import WinRMExecutor

logger = logging.getLogger(__name__)


class ConnectionManager:
    """连接管理器
    统一管理本地/SSH/WinRM 执行器的连接池
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.executors: Dict[str, BaseExecutor] = {}
        self.default_machine: str = "local"
        self._initialized = False

        logger.info("ConnectionManager initialized")

    async def initialize(self) -> None:
        """初始化所有执行器连接

        连接顺序：
        1. 本地执行器（始终可用）
        2. SSH 执行器（如果配置）
        3. WinRM 执行器（如果配置）
        """
        logger.info("🔌 Initializing connection pool...")

        # 1. 本地执行器
        local_config = {
            "allowed_roots": self.config.local_allowed_roots,
            "blocked_patterns": self.config.local_blocked_patterns
        }

        local_executor = LocalExecutor(name="local", config=local_config)
        connected = await local_executor.connect()

        if connected:
            self.executors["local"] = local_executor
            logger.info("✅ Local executor connected")
        else:
            logger.error("❌ Failed to connect local executor")

        # 2. 远程机器执行器
        for machine in self.config.machines:
            if machine.type == "local":
                if machine.is_default:
                    self.default_machine = machine.name
                continue

            executor = None

            try:
                if machine.type == "ssh" and machine.ssh:
                    executor = SSHExecutor(
                        name=machine.name,
                        config=machine.ssh.dict()
                    )
                elif machine.type == "winrm" and machine.winrm:
                    executor = WinRMExecutor(
                        name=machine.name,
                        config=machine.winrm.dict()
                    )

                if executor:
                    connected = await executor.connect()

                    if connected:
                        self.executors[machine.name] = executor
                        if machine.is_default:
                            self.default_machine = machine.name
                        logger.info(f"✅ {machine.type.upper()} executor connected: {machine.name}")
                    else:
                        logger.warning(f"⚠️ Failed to connect {machine.name}")

            except Exception as e:
                logger.error(f"❌ Failed to initialize {machine.name}: {e}")

        self._initialized = True
        logger.info(f"🎉 Connection pool initialized ({len(self.executors)} executors)")

    def get_executor(self, machine_name: Optional[str] = None) -> BaseExecutor:
        """获取指定机器的执行器

        Args:
            machine_name: 机器名称（可选，默认使用默认机器）

        Returns:
            BaseExecutor: 执行器实例

        Raises:
            ValueError: 如果机器不可用
        """
        name = machine_name or self.default_machine

        if name not in self.executors:
            available = list(self.executors.keys())
            raise ValueError(
                f"Machine '{name}' not available. Available: {available}"
            )

        return self.executors[name]

    def list_machines(self) -> List[str]:
        """获取所有可用机器名称"""
        return list(self.executors.keys())

    def get_default_machine(self) -> str:
        """获取默认机器名称"""
        return self.default_machine

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def get_executor_stats(self) -> Dict[str, Any]:
        """获取所有执行器状态"""
        stats = {}

        for name, executor in self.executors.items():
            stats[name] = {
                "type": executor.__class__.__name__,
                "connected": executor.is_connected(),
                "allowed_roots": executor.get_allowed_roots()
            }

        return stats

    async def test_all_connections(self) -> Dict[str, bool]:
        """测试所有连接

        Returns:
            Dict: 机器名称 -> 连接状态
        """
        results = {}

        for name, executor in self.executors.items():
            try:
                result = await executor.execute_command("echo test")
                results[name] = result.ok
            except Exception as e:
                logger.error(f"Connection test failed for {name}: {e}")
                results[name] = False

        return results

    async def shutdown(self) -> None:
        """关闭所有连接"""
        logger.info("🔌 Shutting down connection pool...")

        for name, executor in list(self.executors.items()):
            try:
                await executor.disconnect()
                logger.info(f"✅ Disconnected: {name}")
            except Exception as e:
                logger.error(f"Error disconnecting {name}: {e}")

        self.executors.clear()
        self._initialized = False

        logger.info("Connection pool shutdown complete")

    def __len__(self) -> int:
        return len(self.executors)

    def __repr__(self) -> str:
        return f"ConnectionManager(executors={list(self.executors.keys())})"
