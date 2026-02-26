"""
WinRM 执行器模块
通过 WinRM 连接远程 Windows 机器
"""

import asyncio
import winrm
import base64
from typing import Dict, Any

from .base import BaseExecutor, ExecutionResult
from ..security import SecurityPolicy

import logging

logger = logging.getLogger(__name__)


class WinRMExecutor(BaseExecutor):
    """WinRM 执行器
    通过 WinRM 连接远程 Windows 机器
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

        self.winrm_config = config
        self.session: winrm.Session = None

        self._allowed_roots = config.get("allowed_roots", ["C:/", "D:/"])
        self._blocked_patterns = config.get("blocked_patterns", ["*/Windows/System32/*"])

        self.set_allowed_roots(self._allowed_roots)
        self.set_blocked_patterns(self._blocked_patterns)

    async def connect(self) -> bool:
        """建立 WinRM 连接"""
        try:
            protocol = 'https' if self.winrm_config.get('ssl', True) else 'http'
            endpoint = f"{protocol}://{self.winrm_config.get('host')}:{self.winrm_config.get('port', 5986)}/wsman"

            self.session = winrm.Session(
                endpoint,
                auth=(
                    self.winrm_config.get('username'),
                    self.winrm_config.get('password')
                ),
                server_cert_validation='ignore'
            )

            result = self.session.run_cmd("echo OpenClaw connection test")

            if result.status_code == 0:
                self.connected = True
                logger.info(f"✅ WinRM connected to {self.winrm_config.get('host')}")
                return True
            else:
                logger.warning(f"WinRM connection test failed: {result.std_err.decode()}")
                return False

        except Exception as e:
            logger.error(f"WinRM connection failed: {e}")
            return False

    async def disconnect(self):
        """断开 WinRM 连接"""
        self.session = None
        self.connected = False
        logger.info(f"🔌 WinRM disconnected: {self.name}")

    async def execute_command(self, command: str, timeout: int = 60) -> ExecutionResult:
        """执行远程 WinRM 命令"""
        if not self.connected or not self.session:
            return ExecutionResult(ok=False, error="WinRM not connected", target=self.name)

        try:
            # 安全检查
            if SecurityPolicy.is_dangerous_command(command):
                return ExecutionResult(
                    ok=False,
                    error="Security Violation: Dangerous command detected",
                    target=self.name
                )

            logger.info(f"⚡ Executing WinRM command on {self.name}: {command[:100]}...")

            loop = asyncio.get_event_loop()

            def run_command():
                result = self.session.run_cmd(command, timeout=timeout)
                return (
                    result.std_out.decode('utf-8', errors='ignore'),
                    result.std_err.decode('utf-8', errors='ignore'),
                    result.status_code
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
            logger.error(f"WinRM command execution failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def read_file(self, path: str) -> ExecutionResult:
        """读取远程 WinRM 文件"""
        if not self.connected or not self.session:
            return ExecutionResult(ok=False, error="WinRM not connected", target=self.name)

        try:
            ps_path = path.replace('/', '\\')
            command = f"Get-Content -Path '{ps_path}' -Raw -Encoding UTF8"

            result = await self.execute_command(command)

            if result.ok:
                content = result.stdout

                if len(content) > 2 * 1024 * 1024:
                    return ExecutionResult(ok=False, error="File too large (>2MB)", target=self.name)

                return ExecutionResult(ok=True, content=content, path=path, target=self.name)
            else:
                return result

        except Exception as e:
            logger.error(f"WinRM file read failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入远程 WinRM 文件"""
        if not self.connected or not self.session:
            return ExecutionResult(ok=False, error="WinRM not connected", target=self.name)

        try:
            ps_path = path.replace('/', '\\')
            dir_path = '\\'.join(ps_path.split('\\')[:-1])

            if dir_path:
                mkdir_cmd = f"if (!(Test-Path '{dir_path}')) {{ New-Item -ItemType Directory -Force -Path '{dir_path}' }}"
                await self.execute_command(mkdir_cmd)

            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            write_cmd = (
                f"[System.IO.File]::WriteAllText('{ps_path}', "
                f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{content_b64}')))"
            )

            result = await self.execute_command(write_cmd)

            if result.ok:
                return ExecutionResult(ok=True, path=path, target=self.name)
            else:
                return result

        except Exception as e:
            logger.error(f"WinRM file write failed: {e}")
            return ExecutionResult(ok=False, error=str(e), target=self.name)

    async def file_exists(self, path: str) -> bool:
        """检查远程 WinRM 文件是否存在"""
        if not self.connected or not self.session:
            return False

        try:
            ps_path = path.replace('/', '\\')
            result = await self.execute_command(f"Test-Path '{ps_path}'")
            return result.ok and result.stdout.strip().lower() == 'true'
        except:
            return False

    async def list_directory(self, path: str) -> ExecutionResult:
        """列出远程 WinRM 目录内容"""
        if not self.connected or not self.session:
            return ExecutionResult(ok=False, error="WinRM not connected", target=self.name)

        try:
            ps_path = path.replace('/', '\\')
            command = f"Get-ChildItem -Path '{ps_path}' | Select-Object Name, Mode | Format-Table"

            result = await self.execute_command(command)

            if result.ok:
                return ExecutionResult(ok=True, content=result.stdout, path=path, target=self.name)
            else:
                return result

        except Exception as e:
            return ExecutionResult(ok=False, error=str(e), target=self.name)
