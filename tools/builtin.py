"""
内置工具模块
清理重复定义，简化注册逻辑
"""

import json
from typing import Dict, Any

from .base import BaseTool
from .registry import ToolRegistry

import logging

logger = logging.getLogger(__name__)


class ReadFileTool(BaseTool):
    """读取文件工具"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取指定路径的文件内容。支持本地和远程机器。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径 (绝对或相对路径)"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称 (可选，默认本地)",
                    "enum": []
                }
            },
            "required": ["path"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行文件读取"""
        path = kwargs.get("path")
        target = kwargs.get("target", "local")

        if not path:
            return {"ok": False, "error": "path is required"}

        try:
            logger.info(f"📖 Reading file: {path} on {target}")

            executor = ToolRegistry.get_connection_manager().get_executor(target)
            result = await executor.read_file(path)

            response = {
                "ok": result.ok,
                "path": result.path,
                "target": target
            }

            if result.ok:
                response["content"] = result.content
            else:
                response["error"] = result.error

            return response

        except Exception as e:
            logger.error(f"ReadFileTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


class WriteFileTool(BaseTool):
    """写入文件工具"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "写入内容到指定文件。支持本地和远程机器。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径 (绝对或相对路径)"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称 (可选，默认本地)",
                    "enum": []
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行文件写入"""
        path = kwargs.get("path")
        content = kwargs.get("content")
        target = kwargs.get("target", "local")

        if not path:
            return {"ok": False, "error": "path is required"}

        if content is None:
            return {"ok": False, "error": "content is required"}

        try:
            logger.info(f"📝 Writing file: {path} on {target} ({len(content)} chars)")

            executor = ToolRegistry.get_connection_manager().get_executor(target)
            result = await executor.write_file(path, content)

            response = {
                "ok": result.ok,
                "path": result.path,
                "target": target
            }

            if not result.ok:
                response["error"] = result.error

            return response

        except Exception as e:
            logger.error(f"WriteFileTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


class ExecShellTool(BaseTool):
    """执行 Shell 命令工具"""

    @property
    def name(self) -> str:
        return "exec_shell"

    @property
    def description(self) -> str:
        return "在指定机器上执行 Shell 命令。支持本地、SSH 和 WinRM 机器。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称 (可选，默认本地)",
                    "enum": []
                }
            },
            "required": ["command"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行 Shell 命令"""
        command = kwargs.get("command")
        target = kwargs.get("target", "local")

        if not command:
            return {"ok": False, "error": "command is required"}

        # 安全检查
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            "format c:",
            "del /s /q c:\\",
            ":(){ :|:& };:",
            "mkfs",
            "dd if=/dev/zero"
        ]

        for pattern in dangerous_patterns:
            if pattern.lower() in command.lower():
                logger.warning(f"🛡️ Blocked dangerous command: {command}")
                return {
                    "ok": False,
                    "error": "Security Violation: Dangerous command detected"
                }

        try:
            logger.info(f"⚡ Executing command on {target}: {command[:100]}...")

            executor = ToolRegistry.get_connection_manager().get_executor(target)
            result = await executor.execute_command(command)

            response = {
                "ok": result.ok,
                "target": target,
                "command": command[:200]
            }

            if result.ok:
                response["stdout"] = result.stdout
                response["stderr"] = result.stderr
                response["returncode"] = result.returncode
            else:
                response["error"] = result.error

            return response

        except Exception as e:
            logger.error(f"ExecShellTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "command": command[:200],
                "target": target
            }


class ListFilesTool(BaseTool):
    """列出目录文件工具"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "列出指定目录下的文件和子目录。支持本地和远程机器。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径 (可选，默认当前目录)"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称 (可选，默认本地)",
                    "enum": []
                }
            },
            "required": []
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """列出目录内容"""
        path = kwargs.get("path", ".")
        target = kwargs.get("target", "local")

        try:
            executor = ToolRegistry.get_connection_manager().get_executor(target)

            if target == "local" or executor.__class__.__name__ == "LocalExecutor":
                command = f"ls -la {path}"
            else:
                command = f"Get-ChildItem -Path '{path.replace('/', '\\')}' | Format-Table"

            result = await executor.execute_command(command)

            return {
                "ok": result.ok,
                "path": path,
                "target": target,
                "content": result.stdout if result.ok else "",
                "error": result.error if not result.ok else ""
            }

        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


def register_builtin_tools() -> None:
    """
    注册所有内置工具

    必须在 ToolRegistry 初始化后调用
    """
    if not ToolRegistry.is_initialized():
        raise RuntimeError("ToolRegistry must be initialized before registering tools")

    tools = [
        ReadFileTool(),
        WriteFileTool(),
        ExecShellTool(),
        ListFilesTool()
    ]

    ToolRegistry.register_multiple(tools)

    logger.info(f"✅ Registered {len(tools)} built-in tools")
