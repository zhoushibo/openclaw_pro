"""
SSH 执行器模块
通过 SSH 连接远程 Linux 机器
"""

import asyncio
import paramiko
from pathlib import Path
from typing import Dict, Any

from .base import BaseExecutor, ExecutionResult
from ..security import SecurityPolicy

import logging
import stat

logger = logging.getLogger(__name__)


class SSHExecutor(BaseExecutor):
    """SSH 执行器
    通过 SSH 连接远程 Linux/Unix 机器
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        self.ssh_config = config
        self.client: paramiko.SSHClient = None
        self.sftp = None

        self._allowed_roots = config.get("allowed_roots", ["/"])
        self._blocked_patterns = config.get("blocked_patterns", ["*/proc/*", "*/sys/*"])

        self.set_allowed_roots(self._allowed_roots)
        self.set_blocked_patterns(self._blocked_patterns)

    async def connect(self) -> bool:
        """建立 SSH 连接"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                'hostname': self.ssh_config.get('host'),
                'port': self.ssh_config.get('port', 22),
                'username': self.ssh_config.get('username'),
                'timeout': 10,
                'banner_timeout': 10
            }

            # 认证方式
            if self.ssh_config.get('private_key_path'):
                key_path = Path(self.ssh_config['private_key_path']).expanduser()
                if key_path.exists():
                    key = paramiko.RSAKey.from_private_key_file(str(key_path))
                    connect_kwargs['pkey'] = key
                    logger.info(f"Using SSH key: {key_path}")
                else:
                    logger.warning(f"SSH key not found: {key_path}")
            elif self.ssh_config.get('password'):
                connect_kwargs['password'] = self.ssh_config['password']

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.connect(**connect_kwargs)
            )

            self.sftp = self.client.open_sftp()
            self.connected = True

            logger.info(f"✅ SSH connected to {self.ssh_config.get('host')}")
            return True

        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return False

    async def disconnect(self):
        """断开 SSH 连接"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
        except Exception as e:
            logger.warning(f"Error during SSH disconnect: {e}")
        finally:
            self.connected = False
            logger.info(f"🔌 SSH disconnected: {self.name}")

    async def execute_command(self, command: str, timeout: int = 60) -> ExecutionResult:
        """执行远程 SSH 命令"""
        if not self.connected or not self.client:
            return ExecutionResult(ok=False, error="SSH not connected", target=self.name)

        try:
            # 安全检查
            if SecurityPolicy.is_dangerous_command(command):
                return ExecutionResult(
                    ok=False,
                    error="Security Violation: Dangerous command detected",
                    target=self.name
                )

            logger.info(f"⚡ Executing SSH command on {self.name}: {command[:100]}...")

            loop = asyncio.get_event_loop()

            def run_command():
                stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
                return (
                    stdout.read().decode('utf-8', errors='ignore'),
                    stderr.read().decode('utf-8', errors='ignore'),
                    stdout.channel.recv_exit_status()
                )

            stdout_str, stderr_str, returncode = await asyncio.wait_for(
                loop.run_in_executor(None, run_command),
                timeout=timeout + 5
            )

            return ExecutionResult(
                ok=True,
                stdout=stdout_str[:2000],
                stderr=stderr_str[:2000],
                returncode=returncode,
                target=self.name
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                ok=False,
                error=f"Command timed out after {timeout}s",
                target=self.name
            )
        except Exception as e:
            logger.error(f"SSH command execution failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def read_file(self, path: str) -> ExecutionResult:
        """读取远程 SSH 文件"""
        if not self.connected or not self.sftp:
            return ExecutionResult(ok=False, error="SSH not connected", target=self.name)

        try:
            logger.info(f"📖 Reading SSH file: {path}")

            loop = asyncio.get_event_loop()

            def read_remote_file():
                with self.sftp.open(path, 'r') as f:
                    return f.read()

            content = await asyncio.wait_for(
                loop.run_in_executor(None, read_remote_file),
                timeout=30
            )

            content_str = content.decode('utf-8', errors='ignore')

            if len(content_str) > 2 * 1024 * 1024:
                return ExecutionResult(ok=False, error="File too large (>2MB)", target=self.name)

            return ExecutionResult(ok=True, content=content_str, path=path, target=self.name)

        except Exception as e:
            logger.error(f"SSH file read failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入远程 SSH 文件"""
        if not self.connected or not self.sftp:
            return ExecutionResult(ok=False, error="SSH not connected", target=self.name)

        try:
            logger.info(f"📝 Writing SSH file: {path} ({len(content)} chars)")

            loop = asyncio.get_event_loop()

            remote_dir = '/'.join(path.split('/')[:-1])
            if remote_dir:
                await self.execute_command(f"mkdir -p {remote_dir}")

            def write_remote_file():
                with self.sftp.open(path, 'w') as f:
                    f.write(content)

            await loop.run_in_executor(None, write_remote_file)

            return ExecutionResult(ok=True, path=path, target=self.name)

        except Exception as e:
            logger.error(f"SSH file write failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def file_exists(self, path: str) -> bool:
        """检查远程 SSH 文件是否存在"""
        if not self.connected or not self.sftp:
            return False

        try:
            self.sftp.stat(path)
            return True
        except:
            return False

    async def list_directory(self, path: str) -> ExecutionResult:
        """列出远程 SSH 目录内容"""
        if not self.connected or not self.sftp:
            return ExecutionResult(ok=False, error="SSH not connected", target=self.name)

        try:
            items = []

            for entry in self.sftp.listdir_attr(path):
                item_type = "dir" if stat.S_ISDIR(entry.st_mode) else "file"
                items.append(f"{item_type}: {entry.filename}")

            return ExecutionResult(ok=True, content="\n".join(items), path=path, target=self.name)

        except Exception as e:
            return ExecutionResult(ok=False, error=str(e), target=self.name)
