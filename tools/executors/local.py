"""
本地执行器模块
在本地机器上执行命令和文件操作
"""

import os
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from .base import BaseExecutor, ExecutionResult
from ..security import SecurityPolicy

import logging

logger = logging.getLogger(__name__)


class LocalExecutor(BaseExecutor):
    """本地执行器
    在本地机器上执行命令和文件操作
    """

    def __init__(self, name: str = "local", config: Dict[str, Any] = None):
        super().__init__(name, config)

        self._allowed_roots = config.get("allowed_roots", ["./workspace"]) if config else ["./workspace"]
        self._blocked_patterns = config.get("blocked_patterns", []) if config else []

        self.set_allowed_roots(self._allowed_roots)
        self.set_blocked_patterns(self._blocked_patterns)

    async def connect(self) -> bool:
        """初始化本地执行器"""
        try:
            workspace = Path("./workspace")
            workspace.mkdir(parents=True, exist_ok=True)

            self.connected = True
            logger.info(f"✅ LocalExecutor connected: {self.name}")
            return True

        except Exception as e:
            logger.error(f"LocalExecutor connection failed: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        self.connected = False
        logger.info(f"🔌 LocalExecutor disconnected: {self.name}")

    async def execute_command(self, command: str, timeout: int = 60) -> ExecutionResult:
        """执行本地 Shell 命令"""
        try:
            # 安全检查
            if SecurityPolicy.is_dangerous_command(command):
                return ExecutionResult(
                    ok=False,
                    error="Security Violation: Dangerous command detected",
                    target=self.name
                )

            logger.info(f"⚡ Executing local command: {command[:100]}...")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                return ExecutionResult(
                    ok=True,
                    stdout=stdout.decode('utf-8', errors='ignore')[:2000],
                    stderr=stderr.decode('utf-8', errors='ignore')[:2000],
                    returncode=process.returncode,
                    target=self.name
                )

            except asyncio.TimeoutError:
                process.kill()
                return ExecutionResult(
                    ok=False,
                    error=f"Command timed out after {timeout}s",
                    target=self.name
                )

        except Exception as e:
            logger.error(f"Local command execution failed: {e}")
            return ExecutionResult(
                ok=False,
                error=str(e),
                target=self.name
            )

    async def read_file(self, path: str) -> ExecutionResult:
        """读取本地文件"""
        try:
            safe_path = SecurityPolicy.resolve_safe_path(
                path,
                must_exist=True,
                allowed_roots=self._allowed_roots,
                blocked_patterns=self._blocked_patterns
            )

            if not safe_path.is_file():
                return ExecutionResult(
                    ok=False,
                    error=f"File not found: {path}",
                    target=self.name
                )

            max_size = 2 * 1024 * 1024  # 2MB

            if safe_path.stat().st_size > max_size:
                return ExecutionResult(
                    ok=False,
                    error=f"File too large (>2MB): {safe_path}",
                    target=self.name
                )

            with open(safe_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            logger.info(f"📖 Read {len(content)} chars from {safe_path}")

            return ExecutionResult(
                ok=True,
                content=content,
                path=str(safe_path),
                target=self.name
            )

        except PermissionError as e:
            return ExecutionResult(
                ok=False,
                error=f"Security Violation: {str(e)}",
                target=self.name
            )
        except Exception as e:
            logger.error(f"Local file read failed: {e}")
            return ExecutionResult(
                ok=False,
                error=str(e),
                target=self.name
            )

    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入本地文件"""
        try:
            safe_path = SecurityPolicy.resolve_safe_path(
                path,
                must_exist=False,
                allowed_roots=self._allowed_roots,
                blocked_patterns=self._blocked_patterns
            )

            safe_path.parent.mkdir(parents=True, exist_ok=True)

            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"📝 Wrote {len(content)} chars to {safe_path}")

            return ExecutionResult(
                ok=True,
                path=str(safe_path),
                target=self.name
            )

        except PermissionError as e:
            return ExecutionResult(
                ok=False,
                error=f"Security Violation: {str(e)}",
                target=self.name
            )
        except Exception as e:
            logger.error(f"Local file write failed: {e}")
            return ExecutionResult(
                ok=False,
                error=str(e),
                target=self.name
            )

    async def file_exists(self, path: str) -> bool:
        """检查本地文件是否存在"""
        try:
            safe_path = SecurityPolicy.resolve_safe_path(
                path,
                must_exist=False,
                allowed_roots=self._allowed_roots,
                blocked_patterns=self._blocked_patterns
            )
            return safe_path.exists()
        except:
            return False

    async def list_directory(self, path: str) -> ExecutionResult:
        """列出本地目录内容"""
        try:
            safe_path = SecurityPolicy.resolve_safe_path(
                path,
                must_exist=False,
                allowed_roots=self._allowed_roots,
                blocked_patterns=self._blocked_patterns
            )

            if not safe_path.exists():
                return ExecutionResult(
                    ok=False,
                    error=f"Path not found: {path}",
                    target=self.name
                )

            items = []
            for item in safe_path.iterdir():
                item_type = "dir" if item.is_dir() else "file"
                items.append(f"{item_type}: {item.name}")

            return ExecutionResult(
                ok=True,
                content="\n".join(items),
                path=str(safe_path),
                target=self.name
            )

        except Exception as e:
            return ExecutionResult(
                ok=False,
                error=str(e),
                target=self.name
            )
